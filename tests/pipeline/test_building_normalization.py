from __future__ import annotations

import json
from pathlib import Path

from pipeline.build import normalize_buildings


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "buildings.json"


def fixture_records() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text())


def test_national_identifier_is_preferred_and_years_are_preserved() -> None:
    building = normalize_buildings(fixture_records())[0]

    assert building.building_id == "national-100"
    assert building.construction_years == (1940, 1970)
    assert building.house_type == "kerrostalo"
    assert building.is_scored is True


def test_fallback_identifier_is_source_scoped_and_deterministic() -> None:
    records = fixture_records()

    first = normalize_buildings(records)[1]
    second = normalize_buildings(list(reversed(records)))[2]

    assert first.building_id == second.building_id
    assert first.building_id.startswith("hsy_buildings:")
    assert first.is_scored is True


def test_only_completed_residential_buildings_are_scored() -> None:
    buildings = normalize_buildings(fixture_records())

    assert [building.building_id for building in buildings if building.is_scored] == [
        "national-100",
        buildings[1].building_id,
    ]
    assert buildings[2].is_scored is False
    assert buildings[3].is_scored is False


def test_unmapped_house_type_and_missing_residential_use_remain_unknown() -> None:
    building = normalize_buildings(fixture_records())[3]

    assert building.house_type is None
    assert building.residential_use is None
