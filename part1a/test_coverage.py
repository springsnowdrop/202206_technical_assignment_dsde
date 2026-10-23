"""Checks of the coverage geometry on a synthetic case with a known answer:
a uniformly populated 2 x 2 degree square on the equator and one station inside it.

Run with:  pytest part1a
"""
import numpy as np
import pytest
import shapely
from rasterio.transform import Affine

import coverage as cv

TRANSFORM = Affine(0.25, 0, -180, 0, -0.25, 90)  # same grid as the GPWv4 15' raster
SQUARE = shapely.box(10, -1, 12, 1)
DENSITY = 100.0
AREA = cv.EARTH_RADIUS_KM ** 2 * np.radians(2) * 2 * np.sin(np.radians(1))


@pytest.fixture(scope="module")
def density():
    d = np.ma.masked_array(np.zeros((720, 1440), dtype="float32"), mask=False)
    d[356:364, 760:768] = DENSITY  # rows/cols of lat -1..1, lon 10..12
    return d


def share_within(hist, km):
    return hist[:round(km / cv.BIN_KM)].sum() / hist.sum()


def test_total_population_is_density_times_area(density):
    hist = cv.population_by_distance(density, TRANSFORM, SQUARE, np.array([[11.0, 0.0]]))
    assert hist.sum() == pytest.approx(DENSITY * AREA, rel=1e-9)


def test_share_within_radius_matches_disc_area(density):
    rng = np.random.default_rng(0)
    errors = {5: [], 10: [], 50: []}
    for _ in range(10):
        station = np.array([[rng.uniform(10.6, 11.4), rng.uniform(-0.4, 0.4)]])
        hist = cv.population_by_distance(density, TRANSFORM, SQUARE, station)
        for km in errors:
            errors[km].append(share_within(hist, km) / (np.pi * km ** 2 / AREA) - 1)
    # ~1 km sub-cells: a few % off for a single station at 5 km, unbiased on average
    for km, err in errors.items():
        assert abs(np.mean(err)) < 0.01
        assert np.max(np.abs(err)) < 0.05


def test_no_station_puts_everyone_beyond_last_band(density):
    hist = cv.population_by_distance(density, TRANSFORM, SQUARE, np.empty((0, 2)))
    assert share_within(hist, cv.MAX_KM) == 0


def test_low_cost_classification():
    assert cv.is_low_cost({"pm1", "pm25", "relativehumidity", "temperature", "um003"})
    assert cv.is_low_cost({"pm25", "humidity", "temperature"})
    assert not cv.is_low_cost({"pm25"})
    assert cv.is_low_cost({"no2", "pm10", "pm25", "pressure", "relativehumidity", "temperature"})
    assert not cv.is_low_cost({"co", "no2", "o3", "pm25", "relativehumidity", "temperature"})
