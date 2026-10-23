"""Collect air quality monitoring station locations for the countries of interest.

Two sources are supported:

* ``crea``   - CREA's air quality platform (api.energyandcleanair.org), the dataset the
               assignment refers to.
* ``crea-india`` - CREA's India station table from its public bucket (India only), used to
               cross-check the OpenAQ list.
* ``openaq`` - OpenAQ's public S3 archive (s3://openaq-data-archive), one of the upstream
               sources CREA aggregates. The archive has no station index, so we list every
               location folder, count its daily files per year since OPENAQ_FIRST_YEAR and
               read lat/lon from its most recent one. Used when the CREA API is not reachable.

Output: part1a/data/stations_<source>.csv with one row per station
        (source, id, name, lat, lon, iso2, [parameters, days_<year>...]).

Usage:  python part1a/stations.py --source openaq
"""
import argparse
import ast
import csv
import gzip
import io
import re
import threading
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import geopandas as gpd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common import CACHE, COUNTRIES, DATA, load_world

CREA_API = "https://api.energyandcleanair.org/stations"
CREA_BUCKET = "https://storage.googleapis.com/crea-public/"
CREA_BUCKET_LIST = "https://storage.googleapis.com/storage/v1/b/crea-public/o"
OPENAQ_BUCKET = "https://openaq-data-archive.s3.amazonaws.com/"
OPENAQ_PREFIX = "records/csv.gz/"
# Only years from this one onward are crawled (coordinates + number of reporting days)
OPENAQ_FIRST_YEAR = 2020

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        s = requests.Session()
        retry = Retry(total=6, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=4))
        _local.session = s
    return _local.session


# --------------------------------------------------------------------------- CREA
def fetch_crea() -> pd.DataFrame:
    r = requests.get(
        CREA_API,
        params={"country": ",".join(COUNTRIES), "level": "station", "format": "json"},
        timeout=300,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json()["data"])
    # coordinates come as {"longitude": .., "latitude": ..}
    coords = df["coordinates"].apply(pd.Series)
    return pd.DataFrame({
        "source": "crea:" + df["source"].astype(str),
        "id": df["id"],
        "name": df["name"],
        "lat": coords["latitude"],
        "lon": coords["longitude"],
        "iso2": df["country_id"],
        "last_updated": df.get("last_updated"),
    })


def fetch_crea_india() -> pd.DataFrame:
    """CREA's India station table, as cached in its public bucket by the India snapshot
    reports. Only covers India: used to cross-check the OpenAQ station list."""
    r = requests.get(CREA_BUCKET_LIST, timeout=60, params={
        "prefix": "plots/india_snapshots/", "delimiter": "/", "fields": "prefixes"})
    r.raise_for_status()
    for folder in sorted(r.json()["prefixes"], reverse=True):  # snapshot folders are named YYYY-MM
        resp = requests.get(f"{CREA_BUCKET}{folder}cache/stations.csv", timeout=60)
        if resp.ok:
            break
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    coords = df["coordinates"].apply(ast.literal_eval).apply(pd.Series)
    print(f"CREA India stations: {folder}cache/stations.csv")
    return pd.DataFrame({
        "source": "crea:" + df["source"],
        "id": df["id"],
        "name": df["name"],
        "lat": coords["latitude"],
        "lon": coords["longitude"],
        "last_updated": df["last_updated"],
    })


# --------------------------------------------------------------------------- OpenAQ
def _s3_list(prefix: str, delimiter: str | None = None, start_after: str | None = None
             ) -> tuple[list[str], list[str]]:
    """Return (keys, common prefixes) under ``prefix``, following pagination."""
    keys, prefixes, token = [], [], None
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if delimiter:
            params["delimiter"] = delimiter
        if start_after:
            params["start-after"] = start_after
        if token:
            params["continuation-token"] = token
        r = _session().get(OPENAQ_BUCKET, params=params, timeout=60)
        r.raise_for_status()
        keys += re.findall(r"<Key>(.*?)</Key>", r.text)
        prefixes += re.findall(r"<Prefix>(.*?)</Prefix>", r.text)[1:]  # first one echoes `prefix`
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", r.text)
        if not m:
            return keys, prefixes
        token = m.group(1)


def _openaq_location(location_id: str) -> dict | None:
    # One daily file per key: .../locationid=<id>/year=<y>/month=<m>/location-<id>-<yyyymmdd>.csv.gz
    base = f"{OPENAQ_PREFIX}locationid={location_id}/"
    keys, _ = _s3_list(base, start_after=f"{base}year={OPENAQ_FIRST_YEAR}")
    if not keys:
        return None
    days = Counter(int(re.search(r"/year=(\d+)/", k).group(1)) for k in keys)

    raw = _session().get(OPENAQ_BUCKET + keys[-1], timeout=60).content  # latest daily file
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode("utf-8"))))
    if not rows:
        return None
    return {
        "source": "openaq",
        "id": location_id,
        "name": rows[0]["location"],
        "lat": float(rows[0]["lat"]),
        "lon": float(rows[0]["lon"]),
        # older files call the parameter column "measurand"
        "parameters": "|".join(sorted({r.get("parameter") or r["measurand"] for r in rows})),
        **{f"days_{y}": n for y, n in sorted(days.items())},
    }


def fetch_openaq(workers: int = 64) -> pd.DataFrame:
    cache = CACHE / "openaq_locations.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"id": str})

    _, prefixes = _s3_list(OPENAQ_PREFIX, delimiter="/")
    ids = [p.rstrip("/").split("=")[-1] for p in prefixes]
    print(f"OpenAQ archive: {len(ids)} locations")

    records = []
    for attempt in range(2):  # second pass retries the locations that failed (connection resets)
        failed = []
        with ThreadPoolExecutor(workers) as pool:
            futures = {pool.submit(_openaq_location, i): i for i in ids}
            for n, fut in enumerate(as_completed(futures), 1):
                try:
                    if (rec := fut.result()) is not None:
                        records.append(rec)
                except Exception as e:  # keep going, report at the end
                    failed.append((futures[fut], repr(e)))
                if n % 2000 == 0:
                    print(f"  {n}/{len(ids)} locations scanned, {len(records)} active since {OPENAQ_FIRST_YEAR}")
        if not failed:
            break
        print(f"  {len(failed)} locations failed, e.g. {failed[:3]}")
        ids = [i for i, _ in failed]

    df = pd.DataFrame(records)
    day_cols = sorted(c for c in df.columns if c.startswith("days_"))
    df[day_cols] = df[day_cols].fillna(0).astype(int)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def assign_country(df: pd.DataFrame, max_deg: float = 0.05) -> pd.DataFrame:
    """Tag stations with the ISO2 code of the country they are in - or, for coastal sites just
    outside the 1:10m coastline, of the nearest country within ``max_deg`` (~5 km) - and keep
    the countries of interest. Matching against all countries keeps e.g. a station in Windsor
    (Canada) from being snapped to the US."""
    pts = gpd.GeoDataFrame(df.drop(columns="iso2", errors="ignore").reset_index(drop=True),
                           geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    with warnings.catch_warnings():  # distances in degrees are fine for this tolerance
        warnings.simplefilter("ignore", UserWarning)
        joined = gpd.sjoin_nearest(pts, load_world(), max_distance=max_deg, how="inner")
    joined = joined[~joined.index.duplicated()]  # ties on shared borders
    return pd.DataFrame(joined[joined["iso2"].isin(COUNTRIES)].drop(columns=["geometry", "index_right"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["crea", "crea-india", "openaq"], default="openaq")
    args = parser.parse_args()

    fetch = {"crea": fetch_crea, "crea-india": fetch_crea_india, "openaq": fetch_openaq}[args.source]
    df = fetch()
    df = assign_country(df.dropna(subset=["lat", "lon"]))
    out = DATA / f"stations_{args.source}.csv"
    df.sort_values(["iso2", "id"]).to_csv(out, index=False)
    print(f"{len(df)} stations written to {out.relative_to(DATA.parent.parent)}")
    print(df["iso2"].value_counts().reindex(list(COUNTRIES), fill_value=0).to_string())


if __name__ == "__main__":
    main()
