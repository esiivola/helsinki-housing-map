import gzip
import json
import subprocess
from pathlib import Path


def test_migrates_legacy_overviews_without_rebuilding_source_layers(tmp_path: Path) -> None:
    (tmp_path / "overview").mkdir()
    (tmp_path / "layers.json").write_text(json.dumps([{"layer_id": "income"}]))
    legacy = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"building_count": 2, "layer_state_counts": {"income": {"known": 1, "unknown": 1}}, "layer_summaries": {"income": {"median": 42000}}, "score_inputs": [{"income": {"state": "known", "value": 42000, "values": []}}, {"income": {"state": "unknown", "value": None, "values": []}}]}, "geometry": {"type": "Point", "coordinates": [24.9, 60.2]}}]}
    (tmp_path / "overview" / "1000m.geojson.gz").write_bytes(gzip.compress(json.dumps(legacy).encode(), mtime=0))
    (tmp_path / "manifest.json").write_text(json.dumps({"layer_catalogue": "layers.json", "spatial_partitions": {"overview_tiers": [{"min_zoom": 10, "max_zoom": 10, "cell_size_m": 1000, "path": "overview/1000m.geojson.gz"}]}}))

    subprocess.run([".venv/bin/python", "scripts/migrate_overview_artifacts.py", str(tmp_path)], check=True)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    tier = manifest["spatial_partitions"]["overview_tiers"][0]
    assert tier["geometry_path"] == "overview/1000m/geometry.geojson.gz"
    assert not (tmp_path / "overview" / "1000m.geojson.gz").exists()
    geometry = json.loads(gzip.decompress((tmp_path / tier["geometry_path"]).read_bytes()))
    layer = json.loads(gzip.decompress((tmp_path / tier["layer_path_template"].replace("{layer_id}", "income")).read_bytes()))
    assert geometry["features"][0]["properties"] == {"cell_id": "0", "building_count": 2}
    assert layer["cells"][0]["score_inputs"][0]["value"] == 42000


def test_leaves_tiled_overviews_unchanged(tmp_path: Path) -> None:
    manifest = {"layer_catalogue": "layers.json", "spatial_partitions": {"overview_tiers": [{"min_zoom": 10, "max_zoom": 10, "cell_size_m": 1000, "tile_zoom": 10, "geometry_path_template": "overview/1000m/tiles/10/{x}/{y}.geojson.gz", "layer_path_template": "overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz", "tile_keys": ["1/2"]}]}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    subprocess.run([".venv/bin/python", "scripts/migrate_overview_artifacts.py", str(tmp_path)], check=True)

    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest
