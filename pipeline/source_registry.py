from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from pipeline.models import SourceManifest


def load_source_registry(path: Path) -> dict[str, SourceManifest]:
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, Mapping) or not isinstance(document.get("sources"), list):
        raise ValueError("source registry must contain a sources list")

    registry: dict[str, SourceManifest] = {}
    for item in document["sources"]:
        if not isinstance(item, Mapping):
            raise ValueError("source registry contains a non-mapping source")
        source = SourceManifest(**dict(item))
        if source.source_id in registry:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        registry[source.source_id] = source
    return registry
