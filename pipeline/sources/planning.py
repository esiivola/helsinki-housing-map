from __future__ import annotations

from collections.abc import Mapping
import math
from pathlib import Path

import geopandas as gpd

from pipeline.models import BuildingValue, Confidence, ValueKind, ValueMethod, ValueState


def active_plan_properties(plan: Mapping[str, object]) -> dict[str, str | float]:
    fields = {
        "plan_number": _plan_text(plan.get("kaavatunnus")),
        "plan_type": _plan_text(plan.get("tyyppi")),
        "status": _plan_text(plan.get("luokka")),
        "area_m2": _plan_number(plan.get("pintaala")),
        "approval": _plan_text(plan.get("hyvaksymispvm")),
        "source_updated_at": _plan_date(plan.get("paivitetty_tietopalveluun")),
    }
    return {key: value for key, value in fields.items() if value is not None}


def _plan_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in {"", "None", "NaN", "NaT", "<NA>"} else text


def _plan_date(value: object) -> str | None:
    text = _plan_text(value)
    return text[:10] if text else None


def _plan_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_active_plan_areas(path: Path) -> gpd.GeoDataFrame:
    areas = gpd.read_file(path)
    if areas.crs is None:
        raise ValueError("active-plan source has no CRS")
    if "luokka" not in areas:
        raise ValueError("active-plan source is missing luokka")
    return areas.loc[areas["luokka"] == "Vireillä"].copy()


def assign_active_plan_status(buildings: gpd.GeoDataFrame, areas: gpd.GeoDataFrame) -> dict[str, BuildingValue]:
    values = {
        building_id: BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, "no", coverage=1, method=ValueMethod.AGGREGATED, confidence=Confidence.HIGH)
        for building_id in buildings["building_id"]
    }
    matches = gpd.sjoin(buildings[["building_id", "geometry"]], areas, how="inner", predicate="intersects")
    for building_id in matches["building_id"].unique():
        values[building_id] = BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, "yes", coverage=1, method=ValueMethod.AGGREGATED, confidence=Confidence.HIGH)
    return values
