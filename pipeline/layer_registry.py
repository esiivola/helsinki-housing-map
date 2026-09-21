from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from pipeline.models import LayerDefinition, LayerKind
from pipeline.models import SourceManifest


def load_layer_registry(path: Path) -> dict[str, LayerDefinition]:
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, Mapping) or not isinstance(document.get("layers"), list):
        raise ValueError("layer registry must contain a layers list")

    registry: dict[str, LayerDefinition] = {}
    for item in document["layers"]:
        if not isinstance(item, Mapping):
            raise ValueError("layer registry contains a non-mapping layer")
        layer = LayerDefinition(**dict(item))
        _validate_layer(layer)
        if layer.layer_id in registry:
            raise ValueError(f"duplicate layer_id: {layer.layer_id}")
        registry[layer.layer_id] = layer
    return registry


def validate_layer_sources(
    layers: Mapping[str, LayerDefinition], sources: Mapping[str, SourceManifest]
) -> None:
    for layer in layers.values():
        missing = sorted(set(layer.source_ids).difference(sources))
        if missing:
            raise ValueError(f"layer {layer.layer_id} references unknown source: {missing[0]}")


def _validate_layer(layer: LayerDefinition) -> None:
    if layer.kind is LayerKind.NUMERIC and layer.allowed_categories:
        raise ValueError("numeric layer cannot define categories")
    if layer.kind is LayerKind.NUMERIC and (layer.visualization_range is None or len(layer.visualization_range) != 2 or layer.visualization_range[0] >= layer.visualization_range[1]):
        raise ValueError("numeric layer must define an ascending visualization range")
    if layer.kind is LayerKind.CATEGORICAL and layer.visualization_range is not None:
        raise ValueError("categorical layer cannot define a visualization range")
    if "unknown" in layer.allowed_categories:
        raise ValueError("unknown cannot be accepted")
