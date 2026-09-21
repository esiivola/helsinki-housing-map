from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from pipeline.models import BuildingRecord


HOUSE_TYPES = frozenset({"omakotitalo", "paritalo", "rivitalo", "kerrostalo"})


def normalize_building(record: Mapping[str, object]) -> BuildingRecord:
    source_id = _required_text(record, "source_id")
    source_record_id = _required_text(record, "source_record_id")
    national_id = _optional_text(record.get("national_building_id"))
    building_id = national_id or _fallback_id(source_id, source_record_id)
    house_type_code = _optional_text(record.get("house_type_code"))
    years = record.get("construction_years", ())

    return BuildingRecord(
        building_id=building_id,
        source_id=source_id,
        municipality=_required_text(record, "municipality"),
        completed=_optional_bool(record.get("completed")),
        residential_use=_optional_bool(record.get("residential_use")),
        house_type=house_type_code if house_type_code in HOUSE_TYPES else None,
        construction_years=tuple(sorted(set(year for year in years if _is_year(year)))),
    )


def _fallback_id(source_id: str, source_record_id: str) -> str:
    digest = sha256(f"{source_id}:{source_record_id}".encode()).hexdigest()
    return f"{source_id}:{digest}"


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = _optional_text(record.get(field))
    if value is None:
        raise ValueError(f"building record has no {field}")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _is_year(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
