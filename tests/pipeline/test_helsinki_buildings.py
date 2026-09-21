from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from pipeline.sources.helsinki_buildings import house_types_by_vtj, read_helsinki_buildings


def test_reader_normalizes_official_c_vtj_prt_identifier(tmp_path: Path) -> None:
    snapshot = tmp_path / "helsinki-buildings.geojson"
    gpd.GeoDataFrame(
        {"c_vtj_prt": ["helsinki-1"], "c_rakennusluokka": ["0112"]},
        geometry=[Point(24.9, 60.1)], crs=4326,
    ).to_file(snapshot, driver="GeoJSON")

    types = house_types_by_vtj(read_helsinki_buildings(snapshot))

    assert types == {"helsinki-1": "rivitalo"}
