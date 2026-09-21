from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon, box

from pipeline.models import ValueState
from pipeline.sources.green_cover import green_cover_300m, main_cycle_route_access_m


def _complete(snapshot: Path) -> None:
    snapshot.with_suffix(".geojson.complete.json").write_text('{"version":2,"size":0,"bbox":[24.0,59.0,26.0,61.0]}')


def test_green_cover_uses_the_area_within_each_building_300m_buffer(tmp_path: Path) -> None:
    snapshot = tmp_path / "vegetation.geojson"
    gpd.GeoDataFrame(geometry=[box(24.89, 60.165, 24.91, 60.175)], crs=4326).to_file(snapshot, driver="GeoJSON")
    _complete(snapshot)
    buildings = gpd.GeoDataFrame({"building_id": ["a", "b"]}, geometry=[Point(24.9, 60.17), Point(24.92, 60.17)], crs=4326)

    values = green_cover_300m(buildings, [snapshot])

    assert values["a"].value == 100
    assert values["b"].value == 0


def test_green_cover_marks_buildings_outside_the_downloaded_coverage_unknown(tmp_path: Path) -> None:
    snapshot = tmp_path / "vegetation.geojson"
    gpd.GeoDataFrame(geometry=[], crs=4326).to_file(snapshot, driver="GeoJSON")
    snapshot.with_suffix(".geojson.complete.json").write_text('{"version":2,"size":0,"bbox":[24.8,60.1,25.0,60.3]}')
    buildings = gpd.GeoDataFrame({"building_id": ["west"]}, geometry=[Point(24.7, 60.2)], crs=4326)

    value = green_cover_300m(buildings, [snapshot])["west"]

    assert value.state is ValueState.UNKNOWN
    assert value.value is None
    assert snapshot.with_suffix(".gpkg").is_file()


def test_green_cover_repairs_invalid_source_polygons_before_union(tmp_path: Path) -> None:
    snapshot = tmp_path / "vegetation.geojson"
    invalid = Polygon([(24.89, 60.16), (24.91, 60.18), (24.89, 60.18), (24.91, 60.16), (24.89, 60.16)])
    gpd.GeoDataFrame(geometry=[invalid], crs=4326).to_file(snapshot, driver="GeoJSON")
    _complete(snapshot)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.17)], crs=4326)

    assert green_cover_300m(buildings, [snapshot])["a"].value is not None


def test_green_cover_reuses_completed_tile_checkpoint(tmp_path: Path, monkeypatch) -> None:
    snapshot = tmp_path / "vegetation.geojson"
    gpd.GeoDataFrame(geometry=[box(24.89, 60.165, 24.91, 60.175)], crs=4326).to_file(snapshot, driver="GeoJSON")
    _complete(snapshot)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.17)], crs=4326)
    checkpoint_dir = tmp_path / "checkpoints"

    expected = green_cover_300m(buildings, [snapshot], checkpoint_dir)
    monkeypatch.setattr("pipeline.sources.green_cover._read_window", lambda *_: (_ for _ in ()).throw(AssertionError("completed tile was recomputed")))

    assert green_cover_300m(buildings, [snapshot], checkpoint_dir) == expected


def test_green_cover_recomputes_a_checkpoint_when_a_snapshot_changes(tmp_path: Path, monkeypatch) -> None:
    snapshot = tmp_path / "vegetation.geojson"
    gpd.GeoDataFrame(geometry=[box(24.89, 60.165, 24.91, 60.175)], crs=4326).to_file(snapshot, driver="GeoJSON")
    _complete(snapshot)
    buildings = gpd.GeoDataFrame({"building_id": ["a"]}, geometry=[Point(24.9, 60.17)], crs=4326)
    checkpoint_dir = tmp_path / "checkpoints"
    green_cover_300m(buildings, [snapshot], checkpoint_dir)
    stamp = snapshot.stat()
    os.utime(snapshot, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1))
    from pipeline.sources import green_cover
    original = green_cover._read_window
    calls = 0

    def observed_read_window(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(green_cover, "_read_window", observed_read_window)
    green_cover_300m(buildings, [snapshot], checkpoint_dir)

    assert calls == 1


def test_main_cycle_route_access_uses_the_nearest_route_geometry(tmp_path: Path) -> None:
    snapshot = tmp_path / "routes.geojson"
    gpd.GeoDataFrame(geometry=[LineString([(100, -100), (100, 100)])], crs=3067).to_file(snapshot, driver="GeoJSON")
    buildings = gpd.GeoDataFrame({"building_id": ["a"], "kunta": ["091"]}, geometry=[Point(0, 0)], crs=3067)

    assert main_cycle_route_access_m(buildings, snapshot)["a"].value == 100


def test_main_cycle_route_access_is_unknown_outside_helsinki(tmp_path: Path) -> None:
    snapshot = tmp_path / "routes.geojson"
    gpd.GeoDataFrame(geometry=[LineString([(100, -100), (100, 100)])], crs=3067).to_file(snapshot, driver="GeoJSON")
    buildings = gpd.GeoDataFrame({"building_id": ["espoo"], "kunta": ["049"]}, geometry=[Point(0, 0)], crs=3067)

    value = main_cycle_route_access_m(buildings, snapshot)["espoo"]

    assert value.state is ValueState.UNKNOWN
    assert value.value is None
