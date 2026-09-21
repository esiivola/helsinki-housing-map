from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from pipeline.sources.vantaa_buildings import house_types_by_vtj


def test_maps_official_vantaa_building_classes_by_vtj(tmp_path: Path) -> None:
    snapshot = tmp_path / "vantaa-buildings.geojson"
    gpd.GeoDataFrame(
        {"vtj_prt": ["a", "b", "c"], "kayttotarkoitus": ["0111 Paritalot", "0121 Asuinkerrostalot", "1911 Talousrakennukset"]},
        geometry=[Point(25, 60), Point(25.1, 60), Point(25.2, 60)], crs=4326,
    ).to_file(snapshot, driver="GeoJSON")

    assert house_types_by_vtj(snapshot) == {"a": "paritalo", "b": "kerrostalo"}
