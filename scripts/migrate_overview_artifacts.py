from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def migrate(release_dir: Path) -> None:
    manifest_path = release_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    spatial = manifest.get("spatial_partitions")
    if not isinstance(spatial, dict):
        raise ValueError("release has no spatial partitions")
    tiers = spatial.get("overview_tiers")
    if not isinstance(tiers, list):
        raise ValueError("release has no overview tiers")
    if tiers and ("geometry_path" in tiers[0] or "geometry_path_template" in tiers[0]):
        return
    layers = json.loads((release_dir / str(manifest["layer_catalogue"])).read_text())
    layer_ids = [layer.get("layer_id") for layer in layers if isinstance(layer, dict)]
    if not all(isinstance(layer_id, str) for layer_id in layer_ids):
        raise ValueError("release has an invalid layer catalogue")

    migrated: list[dict[str, object]] = []
    old_paths: list[Path] = []
    for tier in tiers:
        if not isinstance(tier, dict) or not isinstance(tier.get("path"), str) or not isinstance(tier.get("cell_size_m"), int):
            raise ValueError("release has invalid legacy overview metadata")
        cell_size = tier["cell_size_m"]
        geometry_path = f"overview/{cell_size}m/geometry.geojson.gz"
        layer_template = f"overview/{cell_size}m/layers/{{layer_id}}.json.gz"
        expected = [release_dir / geometry_path, *(release_dir / layer_template.replace("{layer_id}", layer_id) for layer_id in layer_ids)]
        if not all(path.is_file() for path in expected):
            _split_overview(release_dir / tier["path"], release_dir, geometry_path, layer_template, layer_ids)
        migrated.append({
            "min_zoom": tier.get("min_zoom"),
            "max_zoom": tier.get("max_zoom"),
            "cell_size_m": cell_size,
            "geometry_path": geometry_path,
            "layer_path_template": layer_template,
        })
        old_paths.append(release_dir / tier["path"])

    spatial["overview_tiers"] = migrated
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n")
    for path in old_paths:
        path.unlink(missing_ok=True)


def _split_overview(source_path: Path, release_dir: Path, geometry_path: str, layer_template: str, layer_ids: list[str]) -> None:
    overview = json.loads(gzip.decompress(source_path.read_bytes()))
    features = overview.get("features")
    if not isinstance(features, list):
        raise ValueError(f"invalid overview artifact {source_path}")
    geometry_features: list[dict[str, object]] = []
    layer_cells: dict[str, list[dict[str, object]]] = {layer_id: [] for layer_id in layer_ids}
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict) or not isinstance(feature.get("geometry"), dict):
            raise ValueError(f"invalid overview feature in {source_path}")
        properties = feature["properties"]
        building_count = properties.get("building_count")
        inputs = properties.get("score_inputs")
        if not isinstance(building_count, int) or not isinstance(inputs, list) or len(inputs) != building_count:
            raise ValueError(f"invalid overview values in {source_path}")
        cell_id = str(index)
        geometry_features.append({"type": "Feature", "properties": {"cell_id": cell_id, "building_count": building_count}, "geometry": feature["geometry"]})
        states = properties.get("layer_state_counts", {})
        summaries = properties.get("layer_summaries", {})
        for layer_id in layer_ids:
            state_counts = states.get(layer_id, {}) if isinstance(states, dict) else {}
            summary = summaries.get(layer_id) if isinstance(summaries, dict) else None
            layer_cells[layer_id].append({
                "cell_id": cell_id,
                "state_counts": state_counts,
                "summary": summary,
                "score_inputs": [values.get(layer_id) if isinstance(values, dict) else None for values in inputs],
            })
    _write_gzip_json(release_dir / geometry_path, {"type": "FeatureCollection", "features": geometry_features})
    for layer_id, cells in layer_cells.items():
        _write_gzip_json(release_dir / layer_template.replace("{layer_id}", layer_id), {"version": 1, "cells": cells})


def _write_gzip_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split legacy overview artifacts into compact geometry and layer files.")
    parser.add_argument("release_dir", type=Path)
    migrate(parser.parse_args().release_dir)
