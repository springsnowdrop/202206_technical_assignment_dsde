"""Shared constants and helpers for Part 1a (population coverage of monitoring stations)."""
from pathlib import Path

import geopandas as gpd
import requests
import shapely

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
CACHE = DATA / "cache"

# ISO2 -> display name, in the order used by the assignment
COUNTRIES = {
    "US": "United States",
    "GB": "United Kingdom",
    "TR": "Turkey",
    "TH": "Thailand",
    "PH": "Philippines",
    "IN": "India",
}

# Distance bands (km) asked for in the assignment: <5, 5-10, 10-50, >50
RADII_KM = [5, 10, 50]

# GPWv4 rev11 population density (persons / km2 of land), 2020, 15 arc-minute grid
POPULATION_TIF = REPO / "data" / "gpw_v4_population_density_rev11_2020_15_min.tif"

NATURAL_EARTH_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"


def _natural_earth(layer: str) -> gpd.GeoDataFrame:
    path = CACHE / f"{layer}.geojson"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(NATURAL_EARTH_URL.format(layer), timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return gpd.read_file(path)


def load_world() -> gpd.GeoDataFrame:
    """Natural Earth 1:10m polygons of all countries (EPSG:4326)."""
    world = _natural_earth("ne_10m_admin_0_countries")
    # ISO_A2 is "-99" for a few countries; ISO_A2_EH is filled in for all of them
    return world.rename(columns={"ISO_A2_EH": "iso2"})[["iso2", "geometry"]]


def load_countries() -> gpd.GeoDataFrame:
    """Land area of the countries of interest (EPSG:4326): Natural Earth 1:10m country
    polygons, minus lakes. Country polygons include large lakes (Great Lakes, Laguna de Bay...)
    and GPW densities are per km2 of land, so keeping them would overstate lakeside populations."""
    world = load_world()
    world = world[world["iso2"].isin(COUNTRIES)].dissolve(by="iso2").reset_index()
    lakes = shapely.union_all(shapely.make_valid(_natural_earth("ne_10m_lakes").geometry.values))
    world["geometry"] = shapely.make_valid(world.geometry.difference(lakes).values)
    return world[["iso2", "geometry"]]
