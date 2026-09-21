from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from pipeline.models import ValueState
from pipeline.sources.vantaa_property_map import assign_lease_evidence, read_lease_areas


FIXTURE = Path(__file__).parents[1] / "fixtures" / "vantaa_property_map.geojson"


def test_vantaa_reader_selects_only_explicit_lease_areas() -> None:
    areas = read_lease_areas(FIXTURE)

    assert areas.crs.to_epsg() == 3067
    assert areas["tyyppi"].tolist() == ["vuokraalue"]


def test_vantaa_lease_evidence_preserves_uncovered_footprint_as_partial() -> None:
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])], crs=3067)
    areas = gpd.GeoDataFrame({"tyyppi": ["vuokraalue"]}, geometry=[Polygon([(0, 0), (6, 0), (6, 10), (0, 10)])], crs=3067)

    value = assign_lease_evidence(buildings, areas)["a"]

    assert value.state is ValueState.PARTIAL
    assert value.value == "leased"
    assert value.coverage == 0.6
