from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from pipeline.sources.espoo_buildings import house_types_by_vtj


def test_maps_official_espoo_building_classes_by_vtj(tmp_path: Path) -> None:
    snapshot = tmp_path / "espoo-buildings.geojson"
    gpd.GeoDataFrame(
        {"PYSYVARAKENNUSTUNNUS": ["a", "b", "other"], "KAYTTOTARKOITUS_KOODI": ["0111", "0121", "0513"]},
        geometry=[Point(25, 60), Point(25.1, 60), Point(25.2, 60)], crs=4326,
    ).to_file(snapshot, driver="GeoJSON")

    assert house_types_by_vtj(snapshot) == {"a": "paritalo", "b": "kerrostalo"}


def test_rejects_espoo_snapshot_missing_join_or_class_field(tmp_path: Path) -> None:
    snapshot = tmp_path / "espoo-buildings.geojson"
    gpd.GeoDataFrame({"PYSYVARAKENNUSTUNNUS": ["a"]}, geometry=[Point(25, 60)], crs=4326).to_file(snapshot, driver="GeoJSON")

    with pytest.raises(ValueError, match="KAYTTOTARKOITUS_KOODI"):
        house_types_by_vtj(snapshot)
