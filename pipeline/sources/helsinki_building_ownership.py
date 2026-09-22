from __future__ import annotations

import csv
from pathlib import Path

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


CLASSIFICATIONS = {"kaupunki": "city", "muu omistaja": "non_city"}


def read_building_ownership(path: Path) -> dict[str, BuildingValue]:
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["building_id", "luokka"]:
            raise ValueError("Helsinki building ownership snapshot requires building_id,luokka header")
        values: dict[str, BuildingValue] = {}
        for row in reader:
            building_id = (row["building_id"] or "").strip()
            classification = (row["luokka"] or "").strip()
            if not building_id:
                raise ValueError("Helsinki building ownership snapshot has an empty building_id")
            if classification not in CLASSIFICATIONS:
                raise ValueError(f"Helsinki building ownership snapshot has unsupported class: {classification}")
            if building_id in values:
                if values[building_id].value != CLASSIFICATIONS[classification]:
                    raise ValueError(f"Helsinki building ownership snapshot has conflicting class: {building_id}")
                continue
            values[building_id] = BuildingValue(
                state=ValueState.KNOWN,
                kind=ValueKind.SCALAR,
                value=CLASSIFICATIONS[classification],
                coverage=1,
                method=ValueMethod.DERIVED,
                confidence=Confidence.HIGH if classification == "kaupunki" else Confidence.LOW,
            )
    return values
