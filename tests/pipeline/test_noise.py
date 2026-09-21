from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from pipeline.models import ValueState
from pipeline.sources.noise import assign_noise_upper_by_intersection, read_noise_zones


FIXTURE = Path(__file__).parents[1] / "fixtures" / "helsinki_noise_2022.geojson"


def test_noise_reader_keeps_only_published_numeric_zone_upper_bounds() -> None:
    zones = read_noise_zones(FIXTURE)

    assert zones.crs.to_epsg() == 3067
    assert zones["db_hi"].tolist() == [55]


def test_noise_reader_rejects_missing_upper_bound_field(tmp_path: Path) -> None:
    invalid = tmp_path / "noise.geojson"
    invalid.write_text(FIXTURE.read_text().replace('"db_hi"', '"missing"'))

    with pytest.raises(ValueError, match="db_hi"):
        read_noise_zones(invalid)


def test_noise_upper_bound_uses_the_highest_intersecting_zone_and_keeps_coverage() -> None:
    buildings = gpd.GeoDataFrame(
        {"building_id": ["a"]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])],
        crs=3067,
    )
    zones = gpd.GeoDataFrame(
        {"db_hi": [50, 60]},
        geometry=[Polygon([(0, 0), (6, 0), (6, 10), (0, 10)]), Polygon([(6, 0), (8, 0), (8, 10), (6, 10)])],
        crs=3067,
    )

    value = assign_noise_upper_by_intersection(buildings, zones)["a"]

    assert value.state is ValueState.PARTIAL
    assert value.value == 60
    assert value.coverage == 0.8


def test_noise_upper_bound_keeps_a_zero_area_building_unknown() -> None:
    buildings = gpd.GeoDataFrame(
        {"building_id": ["zero"]},
        geometry=[Polygon([(0, 0), (1, 0), (2, 0), (0, 0)])],
        crs=3067,
    )
    zones = gpd.GeoDataFrame(
        {"db_hi": [55]},
        geometry=[Polygon([(-1, -1), (3, -1), (3, 1), (-1, 1), (-1, -1)])],
        crs=3067,
    )

    value = assign_noise_upper_by_intersection(buildings, zones)["zero"]

    assert value.state is ValueState.UNKNOWN


def test_noise_upper_bound_does_not_use_duplicate_building_ids_as_geometry_keys() -> None:
    buildings = gpd.GeoDataFrame(
        {"building_id": ["duplicate", "duplicate"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])],
        crs=3067,
    )
    zones = gpd.GeoDataFrame({"db_hi": [55]}, geometry=[Polygon([(-1, -1), (4, -1), (4, 2), (-1, 2), (-1, -1)])], crs=3067)

    assert assign_noise_upper_by_intersection(buildings, zones)["duplicate"].value == 55
