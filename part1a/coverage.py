"""Share of each country's population living within 5, 10 and 50 km of an air quality
monitoring station, and beyond.

Method
------
* Population: GPWv4 2020 population density (persons / km2 of land) on a 0.25 deg grid.
  Each grid cell is split into OVERSAMPLE x OVERSAMPLE sub-cells (~1 km with the default 25)
  that inherit the cell's density. Sub-cells whose centre is outside the country's land
  polygon (Natural Earth 1:10m, lakes removed) are dropped, which handles coasts, lakes and
  borders; the
  population of a sub-cell is density x its area on the sphere.
* Distance: great-circle distance from each sub-cell centre to the nearest station of the
  same country (KD-tree on 3-D unit vectors).
* Population is accumulated in BIN_KM-wide distance bins, from which the band shares
  (<5, 5-10, 10-50, >50 km) and the cumulative curves are derived.

Outputs (part1a/results/):
  coverage.csv            one row per country x distance band (population, share)
  coverage_cumulative.csv cumulative share of population vs distance to nearest station

Usage:  python part1a/coverage.py --stations part1a/data/stations_openaq.csv --year 2025
"""
import argparse

import numpy as np
import pandas as pd
import rasterio
import shapely
from scipy.spatial import cKDTree

from common import COUNTRIES, DATA, POPULATION_TIF, RADII_KM, RESULTS, load_countries

EARTH_RADIUS_KM = 6371.0088
OVERSAMPLE = 25
BIN_KM = 0.1
MAX_KM = 2000  # distances beyond this go into the last bin
CHUNK_CELLS = 2000

# OpenAQ does not say which locations are low-cost sensors; their parameter list does.
# Particle counts, PM1 and VOC come from optical/low-cost sensors only. Met parameters are
# reported by sensor boards but also by some reference stations (e.g. CPCB), so they only
# point to a low-cost sensor when no gaseous pollutant is measured.
LOW_COST_ONLY = {"pm1", "um003", "um005", "um010", "um025", "um050", "um100", "voc"}
MET = {"humidity", "relativehumidity", "temperature", "pressure"}
GASES = {"co", "no", "no2", "nox", "o3", "so2"}


def is_low_cost(parameters: set) -> bool:
    return bool(parameters & LOW_COST_ONLY) or bool(parameters & MET) and not parameters & GASES


def select_stations(stations: pd.DataFrame, year: int, min_days: int, reference_only: bool) -> pd.DataFrame:
    """Stations active in ``year``: at least ``min_days`` reporting days when the number of
    days is known (OpenAQ), otherwise last update on or after the start of ``year`` (CREA)."""
    df = stations
    if f"days_{year}" in df:
        df = df[df[f"days_{year}"] >= min_days]
    elif "last_updated" in df:
        df = df[pd.to_datetime(df["last_updated"], errors="coerce") >= pd.Timestamp(year, 1, 1)]
    if reference_only and "parameters" in df:
        params = df["parameters"].fillna("").str.split("|").apply(set)
        df = df[~params.apply(is_low_cost)]
    return df


def _to_xyz(lon, lat):
    lon, lat = np.radians(lon), np.radians(lat)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def _chord_to_km(chord):
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.clip(chord / 2, 0, 1))


def population_by_distance(density, transform, geom, stations_lonlat):
    """Histogram of the population living in ``geom`` by distance (km) to the nearest station."""
    res = transform.a
    x0, y0 = transform.c, round(transform.f, 6)
    nrows, ncols = density.shape

    # Raster cells overlapping the country's bounding box, populated ones only
    minx, miny, maxx, maxy = geom.bounds
    r0, r1 = max(int(np.floor((y0 - maxy) / res)), 0), min(int(np.ceil((y0 - miny) / res)), nrows)
    c0, c1 = max(int(np.floor((minx - x0) / res)), 0), min(int(np.ceil((maxx - x0) / res)), ncols)
    rows, cols = np.mgrid[r0:r1, c0:c1]
    dens = density[r0:r1, c0:c1]
    keep = ~np.ma.getmaskarray(dens) & (dens.filled(0) > 0)
    rows, cols, dens = rows[keep], cols[keep], dens.data[keep].astype(float)
    left, top = x0 + cols * res, y0 - rows * res

    shapely.prepare(geom)
    boxes = shapely.box(left, top - res, left + res, top)
    touches = shapely.intersects(geom, boxes)
    inside = shapely.covers(geom, boxes)
    left, top, dens, inside = left[touches], top[touches], dens[touches], inside[touches]

    tree = cKDTree(_to_xyz(*stations_lonlat.T)) if len(stations_lonlat) else None
    nbins = int(MAX_KM / BIN_KM) + 1
    hist = np.zeros(nbins)

    step = res / OVERSAMPLE
    offsets = (np.arange(OVERSAMPLE) + 0.5) * step
    for i in range(0, len(left), CHUNK_CELLS):
        sl = slice(i, i + CHUNK_CELLS)
        lon = left[sl, None, None] + offsets[None, None, :]          # (n, 1, k)
        lat = top[sl, None, None] - offsets[None, :, None]           # (n, k, 1)
        area = (EARTH_RADIUS_KM ** 2 * np.radians(step)
                * (np.sin(np.radians(lat + step / 2)) - np.sin(np.radians(lat - step / 2))))
        shape = (len(dens[sl]), OVERSAMPLE, OVERSAMPLE)
        lon, lat = np.broadcast_to(lon, shape).ravel(), np.broadcast_to(lat, shape).ravel()
        pop = np.broadcast_to(dens[sl, None, None] * area, shape).ravel()

        # Sub-cells of cells straddling a coast or border: keep those inside the country
        mask = np.repeat(inside[sl], OVERSAMPLE * OVERSAMPLE)
        partial = ~mask
        mask[partial] = shapely.contains_xy(geom, lon[partial], lat[partial])
        lon, lat, pop = lon[mask], lat[mask], pop[mask]

        if tree is None:  # no station: everyone is beyond the last bin
            idx = np.full(len(pop), nbins - 1)
        else:
            dist_km = _chord_to_km(tree.query(_to_xyz(lon, lat))[0])
            idx = np.minimum((dist_km / BIN_KM).astype(int), nbins - 1)
        hist += np.bincount(idx, weights=pop, minlength=nbins)
    return hist


def summarise(hists: dict, stations: pd.DataFrame):
    edges = [0, *RADII_KM, np.inf]
    labels = [f"< {RADII_KM[0]} km",
              *[f"{a}-{b} km" for a, b in zip(RADII_KM[:-1], RADII_KM[1:])],
              f"> {RADII_KM[-1]} km"]
    bands, cumulative = [], []
    for iso2, hist in hists.items():
        total = hist.sum()
        for lo, hi, label in zip(edges[:-1], edges[1:], labels):
            # bin i holds distances in [i, i + 1) * BIN_KM; the last bin also holds the overflow
            pop = hist[round(lo / BIN_KM):None if np.isinf(hi) else round(hi / BIN_KM)].sum()
            bands.append({"iso2": iso2, "country": COUNTRIES[iso2], "band": label,
                          "population": pop, "share": pop / total,
                          "n_stations": int((stations["iso2"] == iso2).sum())})
        cum = np.cumsum(hist) / total
        for d in np.arange(0.5, 200.01, 0.5):
            cumulative.append({"iso2": iso2, "country": COUNTRIES[iso2], "distance_km": d,
                               "share_within": cum[int(round(d / BIN_KM)) - 1]})
    return pd.DataFrame(bands), pd.DataFrame(cumulative)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stations", default=str(DATA / "stations_openaq.csv"))
    parser.add_argument("--year", type=int, default=2025, help="keep stations active this year (OpenAQ only)")
    parser.add_argument("--min-days", type=int, default=30, help="minimum reporting days in --year")
    parser.add_argument("--include-low-cost", action="store_true", help="also count low-cost sensors")
    parser.add_argument("--countries", nargs="+", default=list(COUNTRIES), choices=list(COUNTRIES))
    parser.add_argument("--suffix", default="", help="appended to output file names")
    args = parser.parse_args()

    stations = pd.read_csv(args.stations, dtype={"id": str})
    stations = select_stations(stations, args.year, args.min_days, not args.include_low_cost)
    stations.to_csv(RESULTS / f"stations_used{args.suffix}.csv", index=False)

    with rasterio.open(POPULATION_TIF) as src:
        density, transform = src.read(1, masked=True), src.transform
    countries = load_countries().set_index("iso2")

    hists = {}
    for iso2 in args.countries:
        name = COUNTRIES[iso2]
        st = stations.loc[stations["iso2"] == iso2, ["lon", "lat"]].to_numpy()
        hists[iso2] = population_by_distance(density, transform, countries.geometry[iso2], st)
        print(f"{name:15s} {len(st):5d} stations  population {hists[iso2].sum() / 1e6:8.1f} M")

    bands, cumulative = summarise(hists, stations)
    bands.to_csv(RESULTS / f"coverage{args.suffix}.csv", index=False)
    cumulative.to_csv(RESULTS / f"coverage_cumulative{args.suffix}.csv", index=False)
    print(bands.pivot(index="country", columns="band", values="share")
          .reindex(index=[COUNTRIES[c] for c in args.countries], columns=bands["band"].unique())
          .map("{:.1%}".format).to_string())


if __name__ == "__main__":
    main()
