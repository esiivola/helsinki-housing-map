from __future__ import annotations

import gzip
import json
import os
from pathlib import Path


def verify_release(output_dir: Path) -> dict[str, int]:
    manifest = json.loads((output_dir / "manifest.json").read_text())
    for field in ("source_manifest", "evidence", "layer_catalogue", "layer_distributions", "audit_report"):
        path = manifest.get(field)
        if not isinstance(path, str) or not (output_dir / path).is_file():
            raise ValueError(f"missing release artifact for {field}")
    score_inputs_path = manifest.get("score_histogram_inputs")
    if score_inputs_path is not None:
        if not isinstance(score_inputs_path, str) or not (output_dir / score_inputs_path).is_file():
            raise ValueError("missing score histogram inputs")
        score_inputs = _read_json(output_dir / score_inputs_path)
        if not isinstance(score_inputs, dict) or score_inputs.get("version") != 1 or not isinstance(score_inputs.get("building_values"), list):
            raise ValueError("invalid score histogram inputs")
    layers = _read_json(output_dir / str(manifest["layer_catalogue"]))
    distributions = _read_json(output_dir / str(manifest["layer_distributions"]))
    if not isinstance(layers, list) or not isinstance(distributions, dict) or distributions.get("version") != 1 or not isinstance(distributions.get("distributions"), list):
        raise ValueError("invalid release metadata")
    _verify_layer_sources(_read_json(output_dir / str(manifest["source_manifest"])), layers)
    _verify_distributions(distributions["distributions"], layers)
    _verify_attribute_integrity(output_dir, manifest)
    spatial = manifest.get("spatial_partitions")
    if not isinstance(spatial, dict):
        return {"building_tile_count": 0}
    layer_ids = [layer.get("layer_id") for layer in layers if isinstance(layer, dict)]
    if not all(isinstance(layer_id, str) for layer_id in layer_ids):
        raise ValueError("invalid layer catalogue")
    for tier in spatial.get("overview_tiers", []):
        if (
            not isinstance(tier, dict)
            or not all(isinstance(tier.get(field), int) for field in ("min_zoom", "max_zoom", "cell_size_m", "tile_zoom"))
            or not isinstance(tier.get("geometry_path_template"), str)
            or not isinstance(tier.get("layer_path_template"), str)
            or not isinstance(tier.get("tile_keys"), list)
        ):
            raise ValueError("invalid overview metadata")
        for key in tier["tile_keys"]:
            if not isinstance(key, str) or len(key.split("/")) != 2:
                raise ValueError("invalid overview tile key")
            x, y = key.split("/")
            geometry_path = tier["geometry_path_template"].replace("{x}", x).replace("{y}", y)
            if not (output_dir / geometry_path).is_file():
                raise ValueError(f"missing indexed overview geometry tile {key}")
            for layer_id in layer_ids:
                path = tier["layer_path_template"].replace("{layer_id}", layer_id).replace("{x}", x).replace("{y}", y)
                if not (output_dir / path).is_file():
                    raise ValueError(f"missing overview layer tile {layer_id}/{key}")
    building = spatial.get("building_tier")
    if not isinstance(building, dict):
        raise ValueError("missing building tile metadata")
    keys = building.get("tile_keys")
    geometry_template = building.get("geometry_path_template")
    if not isinstance(keys, list) or not isinstance(geometry_template, str):
        raise ValueError("invalid building tile metadata")
    for key in keys:
        if not isinstance(key, str) or len(key.split("/")) != 2:
            raise ValueError("invalid building tile key")
        x, y = key.split("/")
        if not (output_dir / geometry_template.replace("{x}", x).replace("{y}", y)).is_file():
            raise ValueError(f"missing indexed building tile {key}")
    core_template = building.get("core_attribute_path_template")
    layer_template = building.get("layer_attribute_path_template")
    if core_template is not None or layer_template is not None:
        if not isinstance(core_template, str) or not isinstance(layer_template, str):
            raise ValueError("invalid split tile metadata")
        availability = building.get("layer_tile_keys")
        if not isinstance(availability, dict):
            raise ValueError("invalid layer tile availability")
        for key in keys:
            x, y = key.split("/")
            if not (output_dir / core_template.replace("{x}", x).replace("{y}", y)).is_file():
                raise ValueError(f"missing indexed core tile {key}")
        for layer_id in layer_ids:
            expected = availability.get(layer_id, [])
            if not isinstance(expected, list) or not all(isinstance(key, str) for key in expected):
                raise ValueError("invalid layer tile availability")
            directory = layer_template.replace("{layer_id}", layer_id).split("/{x}/", 1)[0]
            missing = set(expected) - _layer_tile_keys(output_dir / directory)
            if missing:
                raise ValueError(f"missing indexed layer tile {layer_id}/{min(missing)}")
    return {"building_tile_count": len(keys)}


def _verify_layer_sources(sources: object, layers: list[object]) -> None:
    if not isinstance(sources, list):
        raise ValueError("invalid source manifest")
    source_ids = {source.get("source_id") for source in sources if isinstance(source, dict)}
    if None in source_ids:
        raise ValueError("source manifest is missing identifiers")
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get("layer_id"), str):
            raise ValueError("invalid layer catalogue")
        layer_sources = layer.get("source_ids", [])
        if not isinstance(layer_sources, list) or not all(isinstance(source_id, str) for source_id in layer_sources):
            raise ValueError("invalid layer source references")
        missing = sorted(set(layer_sources).difference(source_ids))
        if missing:
            raise ValueError(f"layer {layer['layer_id']} references unknown source {missing[0]}")


def _verify_attribute_integrity(output_dir: Path, manifest: dict[str, object]) -> None:
    partitions = manifest.get("attribute_partitions", [])
    if not isinstance(partitions, list) or not all(isinstance(path, str) for path in partitions):
        raise ValueError("invalid attribute partition metadata")
    if not partitions:
        return
    sources = _read_json(output_dir / str(manifest["source_manifest"]))
    evidence = _read_json(output_dir / str(manifest["evidence"]))
    layers = _read_json(output_dir / str(manifest["layer_catalogue"]))
    audit = _read_json(output_dir / str(manifest["audit_report"]))
    if not all(isinstance(value, list) for value in (sources, evidence, layers)) or not isinstance(audit, dict):
        raise ValueError("invalid release metadata")
    source_ids = {item.get("source_id") for item in sources if isinstance(item, dict)}
    evidence_ids = {item.get("evidence_id") for item in evidence if isinstance(item, dict)}
    layer_ids = {item.get("layer_id") for item in layers if isinstance(item, dict)}
    if None in source_ids or None in evidence_ids or None in layer_ids:
        raise ValueError("release metadata is missing identifiers")
    if any(item.get("source_id") not in source_ids for item in evidence if isinstance(item, dict)):
        raise ValueError("evidence references an unknown source")

    buildings: dict[str, str] = {}
    values: list[dict[str, object]] = []
    for partition in partitions:
        payload = _read_json(output_dir / partition)
        if not isinstance(payload, dict) or not isinstance(payload.get("buildings"), list) or not isinstance(payload.get("building_values"), list):
            raise ValueError(f"invalid attribute partition {partition}")
        for building in payload["buildings"]:
            if not isinstance(building, dict) or not isinstance(building.get("building_id"), str) or not isinstance(building.get("municipality"), str):
                raise ValueError(f"invalid building in {partition}")
            building_id = building["building_id"]
            if building_id in buildings:
                raise ValueError(f"duplicate building ID {building_id}")
            buildings[building_id] = building["municipality"]
        for value in payload["building_values"]:
            if not isinstance(value, dict):
                raise ValueError(f"invalid layer value in {partition}")
            values.append(value)
    for value in values:
        building_id = value.get("building_id")
        layer_id = value.get("layer_id")
        if building_id not in buildings or layer_id not in layer_ids:
            raise ValueError("layer value references an unknown building or layer")
        if value.get("state") not in {"known", "partial", "unknown"}:
            raise ValueError("invalid layer value state")
        if not all(evidence_id in evidence_ids for evidence_id in value.get("evidence_ids", [])):
            raise ValueError("layer value references unknown evidence")
    _verify_audit(audit, buildings, values, len(evidence))


def _verify_distributions(distributions: list[object], layers: list[object]) -> None:
    numeric = {
        layer.get("layer_id"): layer.get("visualization_breaks")
        for layer in layers
        if isinstance(layer, dict) and layer.get("kind") == "numeric"
    }
    found: set[str] = set()
    for item in distributions:
        if not isinstance(item, dict) or not isinstance(item.get("layer_id"), str) or not isinstance(item.get("counts"), list) or not isinstance(item.get("known_count"), int):
            raise ValueError("invalid layer distribution")
        layer_id = item["layer_id"]
        counts = item["counts"]
        breaks = numeric.get(layer_id)
        low, high = item.get("min"), item.get("max")
        number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        if layer_id in found or not isinstance(breaks, list) or len(counts) < 1 or any(not isinstance(count, int) or count < 0 for count in counts) or sum(counts) > item["known_count"] or not number(low) or not number(high) or high < low:
            raise ValueError("invalid layer distribution")
        found.add(layer_id)
    if found != set(numeric):
        raise ValueError("missing numeric layer distribution")


def _read_json(path: Path) -> object:
    try:
        content = gzip.decompress(path.read_bytes()).decode() if path.suffix == ".gz" else path.read_text()
        return json.loads(content)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact {path.name}") from error


def _layer_tile_keys(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    keys: set[str] = set()
    with os.scandir(directory) as x_entries:
        for x_entry in x_entries:
            if not x_entry.is_dir():
                continue
            with os.scandir(x_entry.path) as y_entries:
                for y_entry in y_entries:
                    if y_entry.is_file() and y_entry.name.endswith(".json.gz"):
                        keys.add(f"{x_entry.name}/{y_entry.name.removesuffix('.json.gz')}")
    return keys


def _verify_audit(audit: dict[str, object], buildings: dict[str, str], values: list[dict[str, object]], evidence_count: int) -> None:
    building_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    municipality_counts: dict[str, dict[str, int]] = {}
    layer_counts: dict[str, dict[str, int]] = {}
    municipality_layer_counts: dict[str, dict[str, dict[str, int]]] = {}
    for municipality in buildings.values():
        building_counts[municipality] = building_counts.get(municipality, 0) + 1
    for value in values:
        state = str(value["state"])
        layer_id = str(value["layer_id"])
        municipality = buildings[str(value["building_id"])]
        state_counts[state] = state_counts.get(state, 0) + 1
        municipality_counts.setdefault(municipality, {})[state] = municipality_counts.setdefault(municipality, {}).get(state, 0) + 1
        layer_counts.setdefault(layer_id, {})[state] = layer_counts.setdefault(layer_id, {}).get(state, 0) + 1
        municipality_layer_counts.setdefault(municipality, {}).setdefault(layer_id, {})[state] = municipality_layer_counts.setdefault(municipality, {}).setdefault(layer_id, {}).get(state, 0) + 1
    expected = {
        "building_count_by_municipality": building_counts,
        "evidence_count": evidence_count,
        "layer_value_state_counts": state_counts,
        "layer_value_state_counts_by_municipality": municipality_counts,
        "layer_value_state_counts_by_layer": layer_counts,
        "layer_value_state_counts_by_municipality_and_layer": municipality_layer_counts,
    }
    for field, value in expected.items():
        if audit.get(field) != value:
            raise ValueError(f"audit does not reconcile {field}")
