from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from pathlib import Path

import geopandas as gpd


HOUSE_TYPE_BY_BUILDING_CLASS = {
    "0110": "omakotitalo",
    "0111": "paritalo",
    "0112": "rivitalo",
    "0120": "kerrostalo",
    "0121": "kerrostalo",
}

HEATING_METHOD_BY_CODE = {
    "1": "water_central",
    "2": "air_central",
    "3": "direct_electric",
    "4": "stove",
    "5": "no_fixed_heating",
}

HEATING_ENERGY_SOURCE_BY_CODE = {
    "1": "district_or_local_heat",
    "2": "light_fuel_oil",
    "3": "heavy_fuel_oil",
    "4": "electricity",
    "5": "gas",
    "6": "coal_or_coke",
    "7": "wood",
    "8": "peat",
    "9": "ground_source_heat",
    "10": "other",
}

BUILDING_FACT_FIELDS = {
    "vtj_prt",
    "c_hissi",
    "c_lammtapa",
    "c_poltaine",
    "i_kerrlkm",
    "i_asuinhuoneistojen_lkm",
}


@dataclass(frozen=True)
class HelsinkiBuildingFacts:
    elevator: str | None
    heating_method: str | None
    heating_energy_source: str | None
    storey_count: int | None
    dwelling_count: int | None


def read_helsinki_buildings(path: Path) -> gpd.GeoDataFrame:
    buildings = gpd.read_parquet(path) if path.suffix == ".parquet" else gpd.read_file(path)
    building_id_field = "vtj_prt" if "vtj_prt" in buildings.columns else "c_vtj_prt"
    missing = {building_id_field, "c_rakennusluokka"}.difference(buildings.columns)
    if missing:
        raise ValueError(f"Helsinki buildings source missing fields: {', '.join(sorted(missing))}")
    return buildings.rename(columns={building_id_field: "vtj_prt"})


def house_types_by_vtj(buildings: gpd.GeoDataFrame) -> dict[str, str]:
    house_types: dict[str, str] = {}
    conflicts: set[str] = set()
    for row in buildings[["vtj_prt", "c_rakennusluokka"]].itertuples(index=False):
        building_id = row.vtj_prt
        house_type = HOUSE_TYPE_BY_BUILDING_CLASS.get(row.c_rakennusluokka)
        if not isinstance(building_id, str) or not house_type:
            continue
        existing = house_types.get(building_id)
        if existing is not None and existing != house_type:
            conflicts.add(building_id)
        else:
            house_types[building_id] = house_type
    return {building_id: house_type for building_id, house_type in house_types.items() if building_id not in conflicts}


def building_facts_by_vtj(buildings: gpd.GeoDataFrame) -> dict[str, HelsinkiBuildingFacts]:
    if not BUILDING_FACT_FIELDS.issubset(buildings.columns):
        return {}
    facts: dict[str, HelsinkiBuildingFacts] = {}
    conflicts: dict[str, set[str]] = {}
    for row in buildings[list(BUILDING_FACT_FIELDS)].itertuples(index=False):
        building_id = row.vtj_prt
        if not isinstance(building_id, str):
            continue
        fact = HelsinkiBuildingFacts(
            elevator="yes" if row.c_hissi == "x" else None,
            heating_method=HEATING_METHOD_BY_CODE.get(str(row.c_lammtapa)),
            heating_energy_source=HEATING_ENERGY_SOURCE_BY_CODE.get(str(row.c_poltaine)),
            storey_count=_nonnegative_integer(row.i_kerrlkm),
            dwelling_count=_nonnegative_integer(row.i_asuinhuoneistojen_lkm),
        )
        previous = facts.get(building_id)
        if previous is None:
            facts[building_id] = fact
            continue
        for field in HelsinkiBuildingFacts.__dataclass_fields__:
            if getattr(previous, field) is not None and getattr(fact, field) is not None and getattr(previous, field) != getattr(fact, field):
                conflicts.setdefault(building_id, set()).add(field)
        facts[building_id] = HelsinkiBuildingFacts(
            **{
                field: None if field in conflicts.get(building_id, set()) else getattr(previous, field) or getattr(fact, field)
                for field in HelsinkiBuildingFacts.__dataclass_fields__
            }
        )
    return facts


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, Real) or not float(value).is_integer() or value < 0:
        return None
    return int(value)
