"""Regenerate web/public/data/layer-distributions.json from the built attribute
partitions, using the pipeline's linear_histogram so the shipped data matches
what a full pipeline build would produce. One-off helper for the histogram
redesign (fine linear bins instead of the old 7 percentile bins)."""
from __future__ import annotations

import gc
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.export.web_bundle import linear_histogram  # noqa: E402

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "web" / "public" / "data"
MUNICIPALITIES = ("Helsinki", "Espoo", "Vantaa", "Kauniainen")


def numeric_value(record: dict) -> float | None:
    value = record.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    values = sorted(float(item) for item in (record.get("values") or []) if isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item))
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def main() -> int:
    catalogue = json.loads((DATA / "layers.json").read_text())
    numeric_layers = {
        layer["layer_id"]: layer["visualization_breaks"]
        for layer in catalogue
        if layer["kind"] == "numeric" and isinstance(layer.get("visualization_breaks"), list) and len(layer["visualization_breaks"]) >= 2
    }
    numeric_set = set(numeric_layers)
    values_by_layer: dict[str, list[float]] = {layer_id: [] for layer_id in numeric_layers}

    for municipality in MUNICIPALITIES:
        path = DATA / "attributes" / f"{municipality}.json.gz"
        print(f"reading {path.name}…", flush=True)
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            partition = json.load(handle)
        for record in partition.get("building_values", []):
            layer_id = record.get("layer_id")
            if layer_id in numeric_set and record.get("state") in {"known", "partial"}:
                value = numeric_value(record)
                if value is not None:
                    values_by_layer[layer_id].append(value)
        del partition
        gc.collect()

    distributions = []
    for layer_id, breaks in numeric_layers.items():
        known = sorted(values_by_layer[layer_id])
        if not known:
            distributions.append({"layer_id": layer_id, "counts": [0] * 40, "known_count": 0, "min": float(breaks[0]), "max": float(breaks[-1])})
        else:
            distributions.append({"layer_id": layer_id, **linear_histogram(known)})

    (DATA / "layer-distributions.json").write_text(json.dumps({"version": 1, "distributions": distributions}, separators=(",", ":")))
    print(f"wrote {len(distributions)} distributions", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
