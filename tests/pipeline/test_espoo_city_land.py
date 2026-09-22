from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from pipeline.models import Confidence, ValueState
from pipeline.sources.espoo_city_land import assign_city_owner_coverage, assign_city_owner_evidence, read_city_land_areas


def test_reader_keeps_city_land_geometry(tmp_path: Path) -> None:
    snapshot = tmp_path / "city-land.geojson"
    gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])], crs=3067).to_file(snapshot, driver="GeoJSON")

    areas = read_city_land_areas(snapshot)

    assert len(areas) == 1
    assert areas.crs.to_epsg() == 3067


def test_city_owner_evidence_requires_full_building_footprint_coverage() -> None:
    buildings = gpd.GeoDataFrame(
        {"building_id": ["city", "partial", "other"]},
        geometry=[
            Polygon([(0, 0), (4, 0), (4, 4), (0, 4)]),
            Polygon([(3, 0), (7, 0), (7, 4), (3, 4)]),
            Polygon([(10, 0), (14, 0), (14, 4), (10, 4)]),
        ],
        crs=3067,
    )
    areas = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])], crs=3067)

    values = assign_city_owner_evidence(buildings, areas)

    assert values["city"].state is ValueState.KNOWN
    assert values["city"].value == "city"
    assert values["partial"].state is ValueState.UNKNOWN
    assert values["partial"].value is None
    assert values["other"].state is ValueState.KNOWN
    assert values["other"].value == "non_city"
    assert values["other"].confidence is Confidence.LOW


def test_city_owner_coverage_preserves_partial_city_land_evidence() -> None:
    buildings = gpd.GeoDataFrame(
        {"building_id": ["partial"]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])], crs=3067,
    )
    areas = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (6, 0), (6, 10), (0, 10)])], crs=3067)

    value = assign_city_owner_coverage(buildings, areas)["partial"]

    assert value.state is ValueState.PARTIAL
    assert value.value == "city_owned"
    assert value.coverage == 0.6
