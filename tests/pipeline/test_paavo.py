import geopandas as gpd
from shapely.geometry import Polygon

from pipeline.models import ValueState
from pipeline.sources.paavo import assign_income_by_point, normalize_median_income


def test_paavo_suppressed_income_is_unknown() -> None:
    assert normalize_median_income({"tr_mtu": -1}).state is ValueState.UNKNOWN


def test_paavo_missing_income_is_unknown() -> None:
    assert normalize_median_income({"tr_mtu": float("nan")}).state is ValueState.UNKNOWN


def test_paavo_income_is_a_known_scalar() -> None:
    value = normalize_median_income({"tr_mtu": 32700})

    assert value.state is ValueState.KNOWN
    assert value.value == 32700


def test_paavo_assigns_income_by_building_representative_point() -> None:
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])], crs=3067)
    areas = gpd.GeoDataFrame({"tr_mtu": [32700]}, geometry=[Polygon([(-1, -1), (3, -1), (3, 3), (-1, 3)])], crs=3067)

    assert assign_income_by_point(buildings, areas)["a"].value == 32700
