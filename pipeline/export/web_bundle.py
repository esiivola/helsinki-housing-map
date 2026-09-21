from __future__ import annotations

import json
import gzip
import math
from dataclasses import asdict
from pathlib import Path

from pipeline.models import LayerValueRecord, ReleaseArtifact, StaticBundle
from pipeline.models import LayerDefinition
from pipeline.export.spatial_tiles import overview_cell, overview_cell_polygon, tile_keys_for_bbox
from shapely.geometry import shape


def export(release: ReleaseArtifact, output_dir: Path, layers: dict[str, LayerDefinition] | None = None) -> StaticBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    attributes_dir = output_dir / "attributes"
    attributes_dir.mkdir(exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": release.schema_version,
        "source_manifest": "sources.json",
        "evidence": "evidence.json",
        "attribute_partitions": ["attributes/Helsinki.json.gz"],
        "audit_report": "audit.json",
    }
    _write(output_dir / "sources.json", [asdict(source) for source in release.sources])
    _write(output_dir / "evidence.json", [asdict(record) for record in release.evidence])
    _write_gzip(
        attributes_dir / "Helsinki.json.gz",
        {
            "buildings": [asdict(building) for building in release.buildings],
            "building_values": [_layer_value_data(record) for record in release.layer_values],
        },
    )
    if layers is not None:
        manifest["layer_catalogue"] = "layers.json"
        manifest["layer_distributions"] = "layer-distributions.json"
        manifest["score_histogram_inputs"] = "score-histogram-inputs.json.gz"
        manifest["geometry_partitions"] = ["geometry/Helsinki.geojson.gz"]
        catalogue = _layer_catalogue(layers, release)
        _write(output_dir / "layers.json", catalogue)
        _write(output_dir / "layer-distributions.json", _layer_distributions(release.layer_values, catalogue))
        _write_gzip(output_dir / "score-histogram-inputs.json.gz", {"version": 1, "building_values": _score_inputs(release.layer_values, [building.building_id for building in release.buildings])})
        _write_gzip(output_dir / "geometry" / "Helsinki.geojson.gz", {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"building_id": building.building_id}, "geometry": {"type": "Polygon", "coordinates": [[[24.939 + index * 0.002, 60.169], [24.9405 + index * 0.002, 60.169], [24.9405 + index * 0.002, 60.1705], [24.939 + index * 0.002, 60.1705], [24.939 + index * 0.002, 60.169]]]}}
                for index, building in enumerate(release.buildings)
            ],
        })
    _write(output_dir / "manifest.json", manifest)
    _write(output_dir / "audit.json", _audit_data(release))
    return StaticBundle(manifest)


def export_hsy_attributes(
    release: ReleaseArtifact,
    output_dir: Path,
    geometry_by_municipality: dict[str, list[dict[str, object]]],
    layers: dict[str, LayerDefinition],
    basemap: dict[str, object] | None = None,
    overlays: dict[str, dict[str, object]] | None = None,
) -> StaticBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    attributes_dir = output_dir / "attributes"
    attributes_dir.mkdir(exist_ok=True)
    geometry_dir = output_dir / "geometry"
    geometry_dir.mkdir(exist_ok=True)
    partitions = sorted({building.municipality for building in release.buildings})
    manifest = {
        "schema_version": "1.1.0",
        "source_manifest": "sources.json",
        "evidence": "evidence.json",
        "layer_catalogue": "layers.json",
        "attribute_partitions": [f"attributes/{municipality}.json.gz" for municipality in partitions],
        "geometry_partitions": [f"geometry/{municipality}.geojson.gz" for municipality in partitions],
        "audit_report": "audit.json",
        "layer_distributions": "layer-distributions.json",
        "score_histogram_inputs": "score-histogram-inputs.json.gz",
        "spatial_partitions": _spatial_partitions(geometry_by_municipality, {}, _overview_tiers()),
    }
    _write(output_dir / "manifest.json", manifest)
    _write(output_dir / "sources.json", [asdict(source) for source in release.sources])
    _write(output_dir / "evidence.json", [asdict(record) for record in release.evidence])
    catalogue = _layer_catalogue(layers, release)
    _write(output_dir / "layers.json", catalogue)
    _write(output_dir / "layer-distributions.json", _layer_distributions(release.layer_values, catalogue))
    _write_gzip(output_dir / "score-histogram-inputs.json.gz", {"version": 1, "building_values": _score_inputs(release.layer_values, [building.building_id for building in release.buildings])})
    for municipality in partitions:
        building_ids = {
            building.building_id
            for building in release.buildings
            if building.municipality == municipality
        }
        _write_gzip(
            attributes_dir / f"{municipality}.json.gz",
            {
                "buildings": [
                    asdict(building)
                    for building in release.buildings
                    if building.building_id in building_ids
                ],
                "building_values": [
                    _layer_value_data(record)
                    for record in release.layer_values
                    if record.building_id in building_ids
                ],
            },
        )
        _write_gzip(
            geometry_dir / f"{municipality}.geojson.gz",
            {"type": "FeatureCollection", "features": geometry_by_municipality[municipality]},
        )
    layer_tile_keys = _write_building_tiles(release, output_dir, geometry_by_municipality)
    overview_tiers = _write_overviews(release, output_dir, geometry_by_municipality)
    manifest["spatial_partitions"] = _spatial_partitions(geometry_by_municipality, layer_tile_keys, overview_tiers)
    _write(output_dir / "manifest.json", manifest)
    _validate_tile_pairs(output_dir)
    if basemap is not None:
        _write_gzip(output_dir / "background" / "osm.geojson.gz", basemap)
    if overlays:
        manifest["overlays"] = {overlay_id: f"overlays/{overlay_id}.geojson.gz" for overlay_id in overlays}
        for overlay_id, data in overlays.items():
            _write_gzip(output_dir / "overlays" / f"{overlay_id}.geojson.gz", data)
        _write(output_dir / "manifest.json", manifest)
    audit = _audit_data(release)
    audit["static_asset_metrics"] = _asset_metrics(output_dir)
    _write(output_dir / "audit.json", audit)
    return StaticBundle(manifest)


def _overview_tiers() -> list[dict[str, object]]:
    return [
        {"min_zoom": 10, "max_zoom": 10, "cell_size_m": 1000, "tile_zoom": 10, "geometry_path_template": "overview/1000m/tiles/10/{x}/{y}.geojson.gz", "layer_path_template": "overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz"},
        {"min_zoom": 11, "max_zoom": 12, "cell_size_m": 500, "tile_zoom": 11, "geometry_path_template": "overview/500m/tiles/11/{x}/{y}.geojson.gz", "layer_path_template": "overview/500m/layers/{layer_id}/11/{x}/{y}.json.gz"},
        {"min_zoom": 13, "max_zoom": 14, "cell_size_m": 250, "tile_zoom": 12, "geometry_path_template": "overview/250m/tiles/12/{x}/{y}.geojson.gz", "layer_path_template": "overview/250m/layers/{layer_id}/12/{x}/{y}.json.gz"},
    ]


def _spatial_partitions(geometry_by_municipality: dict[str, list[dict[str, object]]], layer_tile_keys: dict[str, list[str]], overview_tiers: list[dict[str, object]]) -> dict[str, object]:
    return {
        "scheme": "webmercator",
        "format": "geojson-gzip",
        "building_tier": {
            "min_zoom": 15,
            "tile_zoom": 16,
            "geometry_path_template": "tiles/geometry/16/{x}/{y}.geojson.gz",
            "core_attribute_path_template": "tiles/core/16/{x}/{y}.json.gz",
            "layer_attribute_path_template": "tiles/layers/{layer_id}/16/{x}/{y}.json.gz",
            "layer_tile_keys": layer_tile_keys,
            "feature_id_property": "building_id",
            "buffer_tiles": 1,
            "tile_keys": sorted({
                f"{x}/{y}"
                for features in geometry_by_municipality.values()
                for feature in features
                for x, y in tile_keys_for_bbox(shape(feature["geometry"]).bounds, 16)
            }),
        },
        "overview_tiers": overview_tiers,
    }


def _write_building_tiles(
    release: ReleaseArtifact,
    output_dir: Path,
    geometry_by_municipality: dict[str, list[dict[str, object]]],
) -> dict[str, list[str]]:
    geometry_by_id = {
        str(feature["properties"]["building_id"]): feature
        for features in geometry_by_municipality.values()
        for feature in features
    }
    buildings_by_id = {building.building_id: asdict(building) for building in release.buildings}
    values_by_id: dict[str, list[dict[str, object]]] = {}
    for value in release.layer_values:
        values_by_id.setdefault(value.building_id, []).append(_layer_value_data(value))
    by_tile: dict[tuple[int, int], list[str]] = {}
    for building_id, feature in geometry_by_id.items():
        for tile in tile_keys_for_bbox(shape(feature["geometry"]).bounds, 16):
            by_tile.setdefault(tile, []).append(building_id)
    layer_tile_keys: dict[str, list[str]] = {}
    for (x, y), building_ids in sorted(by_tile.items()):
        ordered_ids = sorted(building_ids)
        _write_gzip(
            output_dir / "tiles" / "geometry" / "16" / str(x) / f"{y}.geojson.gz",
            {"type": "FeatureCollection", "features": [geometry_by_id[building_id] for building_id in ordered_ids]},
        )
        _write_gzip(
            output_dir / "tiles" / "core" / "16" / str(x) / f"{y}.json.gz",
            {"buildings": [buildings_by_id[building_id] for building_id in ordered_ids], "building_values": [value for building_id in ordered_ids for value in values_by_id[building_id] if value["layer_id"] == "building_year"]},
        )
        for layer_id in sorted({value["layer_id"] for building_id in ordered_ids for value in values_by_id[building_id]}):
            values = [value for building_id in ordered_ids for value in values_by_id[building_id] if value["layer_id"] == layer_id and value["state"] in {"known", "partial"}]
            if not values:
                continue
            _write_gzip(
                output_dir / "tiles" / "layers" / layer_id / "16" / str(x) / f"{y}.json.gz",
                {"building_values": values},
            )
            layer_tile_keys.setdefault(layer_id, []).append(f"{x}/{y}")
    return layer_tile_keys


def _write_overviews(
    release: ReleaseArtifact,
    output_dir: Path,
    geometry_by_municipality: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    geometry_by_id = {
        str(feature["properties"]["building_id"]): feature
        for features in geometry_by_municipality.values()
        for feature in features
    }
    records_by_building_and_layer: dict[str, dict[str, LayerValueRecord]] = {}
    for record in release.layer_values:
        records_by_building_and_layer.setdefault(record.building_id, {})[record.layer_id] = record
    layer_ids = sorted({record.layer_id for record in release.layer_values})
    tiers = _overview_tiers()
    for tier in tiers:
        size_m = int(tier["cell_size_m"])
        tile_zoom = int(tier["tile_zoom"])
        cells: dict[tuple[int, int], list[str]] = {}
        for building_id, feature in geometry_by_id.items():
            point = shape(feature["geometry"]).representative_point()
            if not math.isfinite(point.x) or not math.isfinite(point.y) or not -180 <= point.x <= 180 or not -90 <= point.y <= 90:
                continue
            cells.setdefault(overview_cell(point.x, point.y, size_m), []).append(building_id)
        geometry_by_tile: dict[tuple[int, int], list[dict[str, object]]] = {}
        layer_cells_by_tile: dict[str, dict[tuple[int, int], list[dict[str, object]]]] = {
            layer_id: {} for layer_id in layer_ids
        }
        for (x, y), building_ids in sorted(cells.items()):
            cell_id = f"{x}/{y}"
            geometry = {
                "type": "Feature",
                "properties": {"cell_id": cell_id, "building_count": len(building_ids)},
                "geometry": {"type": "Polygon", "coordinates": [overview_cell_polygon(x, y, size_m)]},
            }
            tile_keys = tile_keys_for_bbox(shape(geometry["geometry"]).bounds, tile_zoom)
            for layer_id in layer_ids:
                records = [records_by_building_and_layer.get(building_id, {}).get(layer_id) for building_id in building_ids]
                known_records = [record for record in records if record is not None]
                state_counts: dict[str, int] = {}
                for record in known_records:
                    state = record.value.state.value
                    state_counts[state] = state_counts.get(state, 0) + 1
                summary = _overview_summaries(known_records, building_ids).get(layer_id)
                score_inputs = [
                    None if record is None else {"state": record.value.state.value, "value": record.value.value, "values": list(record.value.values)}
                    for record in records
                ]
                cell = {"cell_id": cell_id, "state_counts": state_counts, "summary": summary, "score_inputs": score_inputs}
                for tile in tile_keys:
                    layer_cells_by_tile[layer_id].setdefault(tile, []).append(cell)
            for tile in tile_keys:
                geometry_by_tile.setdefault(tile, []).append(geometry)
        tier["tile_keys"] = [f"{x}/{y}" for x, y in sorted(geometry_by_tile)]
        for (x, y), geometry_features in sorted(geometry_by_tile.items()):
            _write_gzip(
                output_dir / "overview" / f"{size_m}m" / "tiles" / str(tile_zoom) / str(x) / f"{y}.geojson.gz",
                {"type": "FeatureCollection", "features": geometry_features},
            )
            for layer_id in layer_ids:
                _write_gzip(
                    output_dir / "overview" / f"{size_m}m" / "layers" / layer_id / str(tile_zoom) / str(x) / f"{y}.json.gz",
                    {"version": 1, "cells": layer_cells_by_tile[layer_id][(x, y)]},
                )
    return tiers


def _overview_summaries(records: tuple[LayerValueRecord, ...] | list[LayerValueRecord], building_ids: list[str]) -> dict[str, dict[str, float | str]]:
    numeric: dict[str, list[float]] = {}
    categorical: dict[str, list[str]] = {}
    ids = set(building_ids)
    for record in records:
        if record.building_id not in ids or record.value.state not in {"known", "partial"}:
            continue
        value = record.value.value
        numeric_values = [float(item) for item in record.value.values if isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            numeric.setdefault(record.layer_id, []).append(float(value))
        elif numeric_values:
            numeric_values.sort()
            middle = len(numeric_values) // 2
            numeric.setdefault(record.layer_id, []).append(numeric_values[middle] if len(numeric_values) % 2 else (numeric_values[middle - 1] + numeric_values[middle]) / 2)
        elif isinstance(value, str):
            categorical.setdefault(record.layer_id, []).append(value)
        else:
            categories = sorted({item for item in record.value.values if isinstance(item, str)})
            if categories:
                categorical.setdefault(record.layer_id, []).append(categories[0] if len(categories) == 1 else "mixed")
    summaries: dict[str, dict[str, float | str]] = {}
    for layer_id, values in numeric.items():
        values.sort()
        middle = len(values) // 2
        summaries[layer_id] = {
            "min": values[0],
            "median": values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2,
            "max": values[-1],
        }
    for layer_id, values in categorical.items():
        counts = {value: values.count(value) for value in set(values)}
        highest = max(counts.values())
        modes = [value for value, count in counts.items() if count == highest]
        summaries[layer_id] = {"value": modes[0] if len(modes) == 1 else "mixed", "mode_share": highest / len(values)}
    return summaries


def _score_inputs(records: tuple[LayerValueRecord, ...] | list[LayerValueRecord], building_ids: list[str]) -> list[dict[str, dict[str, object]]]:
    by_building: dict[str, dict[str, dict[str, object]]] = {building_id: {} for building_id in building_ids}
    for record in records:
        if record.building_id not in by_building:
            continue
        value = record.value
        by_building[record.building_id][record.layer_id] = {
            "state": value.state.value,
            "value": value.value,
            "values": list(value.values),
        }
    return [by_building[building_id] for building_id in building_ids]


def _layer_catalogue(layers: dict[str, LayerDefinition], release: ReleaseArtifact) -> list[dict[str, object]]:
    records_by_layer: dict[str, list[LayerValueRecord]] = {}
    for record in release.layer_values:
        records_by_layer.setdefault(record.layer_id, []).append(record)
    catalogue = []
    for layer_id in sorted(layers):
        layer = layers[layer_id]
        item = asdict(layer)
        if layer.kind.value == "numeric" and layer.visualization_range is not None:
            item["visualization_breaks"] = _visualization_breaks(records_by_layer.get(layer_id, []), layer.visualization_range, layer_id)
        catalogue.append(item)
    return catalogue


_HISTOGRAM_BINS = 40


def linear_histogram(sorted_values: list[float], bin_count: int = _HISTOGRAM_BINS) -> dict[str, object]:
    """Bucket known values into equally wide bins on a linear value axis.

    The axis is anchored on the 1st..99th percentile, then each end is snapped out
    to the true minimum/maximum when that extreme sits within half the
    inter-percentile spread of the fence. This reveals meaningful extremes -- e.g.
    the 0 m walk distances or the fastest bike times, which are real and belong on
    the axis -- while still rejecting far outliers and sentinel/garbage values
    (``building_year`` carries 1 and 999999999). Values outside the resulting span
    are dropped from the bars rather than piled into the edge bins, so the edges
    show real local density instead of a spurious tail spike; ``counts`` therefore
    describes the in-range window and can sum to less than ``known_count`` (which
    stays the full population). This keeps the x-axis undistorted (unlike the
    percentile ``visualization_breaks`` used for colour).
    """
    known_count = len(sorted_values)
    true_low, true_high = sorted_values[0], sorted_values[-1]
    p_low = _quantile(sorted_values, 0.01)
    p_high = _quantile(sorted_values, 0.99)
    guard = 0.5 * (p_high - p_low)
    low = true_low if guard > 0 and (p_low - true_low) <= guard else p_low
    high = true_high if guard > 0 and (true_high - p_high) <= guard else p_high
    if high <= low:
        low, high = true_low, true_high
    if high <= low:
        high = low + 1.0
    width = (high - low) / bin_count
    counts = [0] * bin_count
    for value in sorted_values:
        if value < low or value > high:
            continue
        index = int((value - low) / width) if width else 0
        counts[min(max(index, 0), bin_count - 1)] += 1
    return {"counts": counts, "known_count": known_count, "min": round(low, 6), "max": round(high, 6)}


def _layer_distributions(records: tuple[LayerValueRecord, ...] | list[LayerValueRecord], catalogue: list[dict[str, object]]) -> dict[str, object]:
    distributions = []
    for layer in catalogue:
        if layer["kind"] != "numeric" or not isinstance(layer.get("visualization_breaks"), (list, tuple)):
            continue
        breaks = layer["visualization_breaks"]
        if len(breaks) < 2:
            continue
        known = sorted(value for record in records if record.layer_id == layer["layer_id"] and record.value.state in {"known", "partial"} for value in [_numeric_value(record)] if value is not None)
        if not known:
            distributions.append({"layer_id": layer["layer_id"], "counts": [0] * 40, "known_count": 0, "min": float(breaks[0]), "max": float(breaks[-1])})
            continue
        distributions.append({"layer_id": layer["layer_id"], **linear_histogram(known)})
    return {"version": 1, "distributions": distributions}


def _visualization_breaks(records: tuple[LayerValueRecord, ...] | list[LayerValueRecord], fallback_range: tuple[float, float], layer_id: str = "") -> tuple[float, ...]:
    values = sorted(value for record in records if record.value.state in {"known", "partial"} for value in [_numeric_value(record)] if value is not None)
    if len(values) < 2 or values[0] == values[-1]:
        lower, upper = fallback_range
        return tuple(lower + (upper - lower) * percentile for percentile in _visualization_percentiles(layer_id))
    if layer_id.startswith("transit_workplace_") and layer_id.endswith("_median_boarding"):
        return tuple(dict.fromkeys(values))
    breaks = tuple(dict.fromkeys(_quantile(values, percentile) for percentile in _visualization_percentiles(layer_id)))
    return breaks if len(breaks) > 1 else _visualization_breaks([], fallback_range, layer_id)


def _visualization_percentiles(layer_id: str) -> tuple[float, ...]:
    if layer_id == "income_median_eur":
        return (0.02, 0.15, 0.36, 0.56, 0.72, 0.84, 0.92)
    if layer_id != "building_year":
        return (0.02, 0.08, 0.16, 0.28, 0.44, 0.64, 0.85)
    return (0.02, 0.12, 0.28, 0.44, 0.60, 0.76, 0.92)


def _numeric_value(record: LayerValueRecord) -> float | None:
    value = record.value.value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    values = sorted(float(item) for item in record.value.values if isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item))
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def _quantile(values: list[float], percentile: float) -> float:
    index = (len(values) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    return round(values[lower] + (values[upper] - values[lower]) * (index - lower), 6)


def _validate_tile_pairs(output_dir: Path) -> None:
    geometry_root = output_dir / "tiles" / "geometry" / "16"
    for geometry_path in geometry_root.rglob("*.geojson.gz"):
        relative = geometry_path.relative_to(geometry_root)
        core_path = output_dir / "tiles" / "core" / "16" / relative.with_suffix("")
        core_path = core_path.with_suffix(".json.gz")
        if not core_path.is_file():
            raise ValueError(f"missing core tile for {relative}")
        geometry = json.loads(gzip.decompress(geometry_path.read_bytes()))
        core = json.loads(gzip.decompress(core_path.read_bytes()))
        geometry_ids = {feature["properties"]["building_id"] for feature in geometry["features"]}
        core_ids = {building["building_id"] for building in core["buildings"]}
        if geometry_ids != core_ids:
            raise ValueError(f"mismatched core tile IDs in {relative}")


def _layer_value_data(record: LayerValueRecord) -> dict[str, object]:
    value = record.value
    finite = not isinstance(value.value, float) or math.isfinite(value.value)
    return {
        "building_id": record.building_id,
        "layer_id": record.layer_id,
        "state": value.state if finite else "unknown",
        "kind": value.kind,
        "value": value.value if finite else None,
        "values": value.values,
        "distribution": value.distribution,
        "coverage": value.coverage if finite else 0,
        "evidence_ids": value.evidence_ids if finite else (),
        "method": value.method,
        "confidence": value.confidence,
    }


def _asset_metrics(output_dir: Path) -> dict[str, int]:
    compressed = list(output_dir.rglob("*.gz"))
    geometry_tiles = list((output_dir / "tiles" / "geometry" / "16").rglob("*.geojson.gz"))
    attribute_tiles = list((output_dir / "tiles" / "core" / "16").rglob("*.json.gz")) + list((output_dir / "tiles" / "layers").rglob("*.json.gz"))
    return {
        "compressed_bytes": sum(path.stat().st_size for path in compressed),
        "compressed_file_count": len(compressed),
        "building_tile_count": len(geometry_tiles),
        "largest_geometry_tile_bytes": max((path.stat().st_size for path in geometry_tiles), default=0),
        "largest_attribute_tile_bytes": max((path.stat().st_size for path in attribute_tiles), default=0),
    }


def _audit_data(release: ReleaseArtifact) -> dict[str, object]:
    municipalities: dict[str, int] = {}
    states: dict[str, int] = {}
    states_by_municipality: dict[str, dict[str, int]] = {}
    states_by_layer: dict[str, dict[str, int]] = {}
    states_by_municipality_and_layer: dict[str, dict[str, dict[str, int]]] = {}
    municipalities_by_building = {building.building_id: building.municipality for building in release.buildings}
    for building in release.buildings:
        municipalities[building.municipality] = municipalities.get(building.municipality, 0) + 1
    for record in release.layer_values:
        state = record.value.state.value
        states[state] = states.get(state, 0) + 1
        layer_states = states_by_layer.setdefault(record.layer_id, {})
        layer_states[state] = layer_states.get(state, 0) + 1
        municipality = municipalities_by_building[record.building_id]
        municipal_states = states_by_municipality.setdefault(municipality, {})
        municipal_states[state] = municipal_states.get(state, 0) + 1
        municipal_layer_states = states_by_municipality_and_layer.setdefault(municipality, {}).setdefault(record.layer_id, {})
        municipal_layer_states[state] = municipal_layer_states.get(state, 0) + 1
    return {
        "building_count_by_municipality": municipalities,
        "evidence_count": len(release.evidence),
        "layer_value_state_counts": states,
        "layer_value_state_counts_by_municipality": states_by_municipality,
        "layer_value_state_counts_by_layer": states_by_layer,
        "layer_value_state_counts_by_municipality_and_layer": states_by_municipality_and_layer,
    }


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _write_gzip(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(value, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
