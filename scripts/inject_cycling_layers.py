"""Publish the cycling effective-time layers into the shipped web data.

A full `hsy-release` rebuild would regenerate every layer (and needs the transit and
green-cover inputs to be present, or it would silently drop those layers). These
layers are additive and derive only from the OSM extract, so this writes just their
files, reusing the pipeline's own tiling, cell and serialisation helpers so the
result is structurally identical to what a release build would produce:

* ``tiles/layers/<layer>/16/{x}/{y}.json.gz``       -- per-building values (zoom 15+)
* ``overview/<size>m/layers/<layer>/<z>/{x}/{y}.json.gz`` -- grid summaries (zoom 10-14)
* the layer catalogue, the manifest's ``layer_tile_keys`` and the distributions

Run it after ``data/work/cycling/compute_cycling_metrics.py``.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd
import yaml
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.export.web_bundle import (
    _asset_metrics,
    _layer_value_data,
    _overview_summaries,
    _overview_tiers,
    _visualization_breaks,
    _write,
    _write_gzip,
    linear_histogram,
    overview_cell,
    overview_cell_polygon,
    tile_keys_for_bbox,
)
from pipeline.models import BuildingValue, Confidence, LayerValueRecord, ValueKind, ValueMethod, ValueState

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data"
METRICS = ROOT / "data" / "work" / "cycling" / "cycling_metrics_all_buildings.parquet"
EVIDENCE_ID = "hsl-osm-routing"
VISUALIZATION_RANGE = (0, 120)


def load_geometry() -> dict[str, object]:
    geometry: dict[str, object] = {}
    for partition in sorted((DATA / "geometry").glob("*.geojson.gz")):
        with gzip.open(partition, "rt") as handle:
            for feature in json.load(handle)["features"]:
                geometry[str(feature["properties"]["building_id"])] = shape(feature["geometry"])
    return geometry


def record_for(building_id: str, layer_id: str, value: float | None) -> LayerValueRecord:
    known = value is not None and value == value
    return LayerValueRecord(building_id, layer_id, BuildingValue(
        ValueState.KNOWN if known else ValueState.UNKNOWN, ValueKind.SCALAR,
        float(value) if known else None, coverage=1 if known else 0,
        evidence_ids=(EVIDENCE_ID,) if known else (),
        method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM,
    ))


def main() -> int:
    frame = pd.read_parquet(METRICS)
    geometry = load_geometry()
    # The layer ids must match exactly what pipeline/build.py emits, or the next
    # real release would create them afresh and orphan whatever is written here.
    routing = yaml.safe_load((ROOT / "pipeline" / "config" / "routing.yaml").read_text())
    names = {str(item["id"]): str(item["name"]) for item in routing["workplace_destinations"]}
    names["rautatieasema"] = str(routing["central_destination"]["name"])
    columns = {
        f"bike_workplace_{column.removesuffix('_effective_min')}_effective_min": column
        for column in frame.columns if column.endswith("_effective_min")
    }
    layer_ids = sorted(columns)
    print(f"{len(frame):,} buildings, {len(layer_ids)} layers, {len(geometry):,} geometries", flush=True)

    building_tiles: dict[tuple[int, int], list[str]] = {}
    for building_id, shape_ in geometry.items():
        for tile in tile_keys_for_bbox(shape_.bounds, 16):
            building_tiles.setdefault(tile, []).append(building_id)
    points = {building_id: shape_.representative_point() for building_id, shape_ in geometry.items()}
    tiers = _overview_tiers()

    manifest = json.loads((DATA / "manifest.json").read_text())
    catalogue = json.loads((DATA / "layers.json").read_text())
    known_layers = {layer["layer_id"] for layer in catalogue}
    tier_keys = manifest["spatial_partitions"]["overview_tiers"]

    for layer_id in layer_ids:
        destination = layer_id.removeprefix("bike_workplace_").removesuffix("_effective_min")
        values = dict(zip(frame["building_id"], frame[columns[layer_id]], strict=True))
        records = {bid: record_for(bid, layer_id, values.get(bid)) for bid in geometry}

        written = []
        for (x, y), ids in sorted(building_tiles.items()):
            _write_gzip(
                DATA / "tiles" / "layers" / layer_id / "16" / str(x) / f"{y}.json.gz",
                {"building_values": [_layer_value_data(records[bid]) for bid in sorted(ids)]},
            )
            written.append(f"{x}/{y}")
        manifest["spatial_partitions"]["building_tier"]["layer_tile_keys"][layer_id] = written

        for tier_index, tier in enumerate(tiers):
            size_m, tile_zoom = int(tier["cell_size_m"]), int(tier["tile_zoom"])
            cells: dict[tuple[int, int], list[str]] = {}
            for building_id, point in points.items():
                cells.setdefault(overview_cell(point.x, point.y, size_m), []).append(building_id)
            by_tile: dict[tuple[int, int], list[dict[str, object]]] = {}
            for (cx, cy), ids in sorted(cells.items()):
                chosen = [records[bid] for bid in ids]
                state_counts: dict[str, int] = {}
                for record in chosen:
                    state = record.value.state.value
                    state_counts[state] = state_counts.get(state, 0) + 1
                cell = {
                    "cell_id": f"{cx}/{cy}",
                    "state_counts": state_counts,
                    "summary": _overview_summaries(chosen, ids).get(layer_id),
                    "score_inputs": [
                        {"state": r.value.state.value, "value": r.value.value, "values": list(r.value.values)}
                        for r in chosen
                    ],
                }
                bounds = shape({"type": "Polygon", "coordinates": [overview_cell_polygon(cx, cy, size_m)]}).bounds
                for tile in tile_keys_for_bbox(bounds, tile_zoom):
                    by_tile.setdefault(tile, []).append(cell)
            for (x, y), cell_list in sorted(by_tile.items()):
                _write_gzip(
                    DATA / "overview" / f"{size_m}m" / "layers" / layer_id / str(tile_zoom) / str(x) / f"{y}.json.gz",
                    {"version": 1, "cells": cell_list},
                )
            assert tier_keys[tier_index]["cell_size_m"] == size_m

        if layer_id not in known_layers:
            scored = [record for record in records.values() if record.value.state is ValueState.KNOWN]
            catalogue.append({
                "layer_id": layer_id,
                "finnish_label": f"Pyörämatkan kesto: {names.get(destination, destination)}",
                "description": f"Pyörämatkan koettu kesto kohteeseen {names.get(destination, destination)}: ajoaika sekä liikennevalojen, käännösten ja hitaan pinnoitteen viive.",
                "kind": "numeric", "unit": "min", "formatter": "integer",
                "allowed_categories": [], "allowed_min": 0, "allowed_max": None,
                "default_enabled": False, "default_weight": 1,
                "visualization_scale": "sequential", "visualization_range": list(VISUALIZATION_RANGE),
                "visualization_breaks": list(_visualization_breaks(scored, VISUALIZATION_RANGE, layer_id)),
                "methodology": "Reitti valitaan koettua aikaa minimoiden: ajoaika (hidas pinnoite ja jalankulkijoiden kanssa jaettu väylä 0,65x), 30 s per liikennevalo, 10 s per käännös ja 2 s per valo-ohjaamaton suojatie. Perustuu CROW- ja Fietsbalans-kriteereihin; käännösten määrä on kalibroitu BRouter-reitittimeen (1,2x).",
                "caveat_ids": ["routing-origin-fallback", "osm-completeness"],
                "source_ids": ["hsl_osm_extract"],
            })
        print(f"  {layer_id}: {len(written):,} building tiles", flush=True)

    catalogue.sort(key=lambda layer: layer["layer_id"])
    _write(DATA / "layers.json", catalogue)
    _write(DATA / "manifest.json", manifest)

    distributions = json.loads((DATA / "layer-distributions.json").read_text())
    existing = {item["layer_id"] for item in distributions["distributions"]}
    for layer_id in layer_ids:
        if layer_id in existing:
            continue
        known = sorted(float(v) for v in frame[columns[layer_id]] if v == v)
        if known:
            distributions["distributions"].append({"layer_id": layer_id, **linear_histogram(known)})
    distributions["distributions"].sort(key=lambda item: item["layer_id"])
    _write(DATA / "layer-distributions.json", distributions)
    print(f"catalogue {len(catalogue)} layers, distributions {len(distributions['distributions'])}")

    sync_attribute_partitions(manifest, frame, columns, {layer["layer_id"] for layer in catalogue})
    return 0


def sync_attribute_partitions(
    manifest: dict[str, object],
    frame: pd.DataFrame,
    columns: dict[str, str],
    catalogue_ids: set[str],
) -> None:
    """Bring the per-municipality attribute partitions and the audit report in line.

    A release build writes every layer value into these partitions, so `verify-release`
    rejects a partition that carries a value for a layer the catalogue no longer lists.
    Rewriting them here keeps this script's output identical to a real build: values for
    dropped layers go, the cycling values arrive, and the audit is recounted from the
    partitions the same way `_audit_data` counts them from the release artefact.
    """
    values = {layer_id: dict(zip(frame["building_id"], frame[column], strict=True)) for layer_id, column in columns.items()}
    municipalities: dict[str, str] = {}
    states: dict[str, int] = {}
    by_municipality: dict[str, dict[str, int]] = {}
    by_layer: dict[str, dict[str, int]] = {}
    by_municipality_and_layer: dict[str, dict[str, dict[str, int]]] = {}
    building_counts: dict[str, int] = {}

    for partition in manifest["attribute_partitions"]:
        path = DATA / str(partition)
        with gzip.open(path, "rt") as handle:
            payload = json.load(handle)
        ids = [str(building["building_id"]) for building in payload["buildings"]]
        municipality = str(payload["buildings"][0]["municipality"])
        building_counts[municipality] = len(ids)
        for building_id in ids:
            municipalities[building_id] = municipality
        kept = [value for value in payload["building_values"] if value["layer_id"] in catalogue_ids]
        dropped = len(payload["building_values"]) - len(kept)
        present = {value["layer_id"] for value in kept}
        added = [
            _layer_value_data(record_for(building_id, layer_id, values[layer_id].get(building_id)))
            for layer_id in sorted(values)
            if layer_id not in present  # re-running must not duplicate what is already there
            for building_id in ids
        ]
        payload["building_values"] = kept + added
        _write_gzip(path, payload)
        print(f"  {partition}: -{dropped:,} stale, +{len(added):,} cycling, {len(payload['building_values']):,} total", flush=True)
        for value in payload["building_values"]:
            state, layer_id = str(value["state"]), str(value["layer_id"])
            states[state] = states.get(state, 0) + 1
            by_layer.setdefault(layer_id, {})[state] = by_layer.setdefault(layer_id, {}).get(state, 0) + 1
            by_municipality.setdefault(municipality, {})[state] = by_municipality.setdefault(municipality, {}).get(state, 0) + 1
            municipal_layer = by_municipality_and_layer.setdefault(municipality, {}).setdefault(layer_id, {})
            municipal_layer[state] = municipal_layer.get(state, 0) + 1

    audit = json.loads((DATA / "audit.json").read_text())
    audit.update({
        "building_count_by_municipality": building_counts,
        "layer_value_state_counts": states,
        "layer_value_state_counts_by_municipality": by_municipality,
        "layer_value_state_counts_by_layer": by_layer,
        "layer_value_state_counts_by_municipality_and_layer": by_municipality_and_layer,
        "static_asset_metrics": _asset_metrics(DATA),
    })
    _write(DATA / "audit.json", audit)
    print(f"audit reconciled over {sum(states.values()):,} layer values")


if __name__ == "__main__":
    raise SystemExit(main())
