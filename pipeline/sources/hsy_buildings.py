from __future__ import annotations

from collections.abc import Set
from numbers import Integral, Real
from pathlib import Path

import geopandas as gpd

from pipeline.layers.buildings import normalize_building
from pipeline.models import BuildingRecord


def read_hsy_buildings(
    path: Path, required_fields: Set[str], source_crs: int | None = None
) -> gpd.GeoDataFrame:
    buildings = gpd.read_parquet(path) if path.suffix == ".parquet" else gpd.read_file(path)
    if source_crs is not None:
        buildings = buildings.set_crs(source_crs, allow_override=True)
    missing = sorted(required_fields.difference(buildings.columns))
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if buildings.crs is None:
        raise ValueError("HSY buildings source has no CRS")
    if buildings.geometry.is_empty.any():
        raise ValueError("HSY buildings source contains empty geometry")
    return buildings


def project_hsy_buildings(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return buildings.to_crs(3067)


def deduplicate_hsy_buildings(buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    seen: set[tuple[str, bytes]] = set()
    kept = []
    for index, row in buildings.iterrows():
        building_id = row["vtj_prt"] if isinstance(row["vtj_prt"], str) and row["vtj_prt"] else row["raktun"]
        if not isinstance(building_id, str) or not building_id:
            kept.append(index)
            continue
        key = (building_id, row.geometry.wkb)
        if key not in seen:
            seen.add(key)
            kept.append(index)
    return buildings.loc[kept].copy()


def normalize_hsy_buildings(buildings: gpd.GeoDataFrame) -> list[BuildingRecord]:
    municipalities = {"091": "Helsinki", "049": "Espoo", "092": "Vantaa", "235": "Kauniainen"}
    records = []
    for row in buildings.itertuples(index=False):
        value = row._asdict()
        records.append(
            normalize_building(
                {
                    "source_id": "hsy_buildings",
                    "source_record_id": value["raktun"] or value["vtj_prt"],
                    "national_building_id": value["vtj_prt"],
                    "municipality": municipalities.get(value["kunta"], "unknown"),
                    "completed": True,
                    "residential_use": value["kayttarks"] == "Asuinrakennus",
                    "house_type_code": None,
                    "construction_years": _construction_year(value["kavu"]),
                }
            )
        )
    return records


def _construction_year(value: object) -> list[int]:
    if isinstance(value, bool):
        return []
    if isinstance(value, Integral):
        return [int(value)]
    if isinstance(value, Real) and value.is_integer():
        return [int(value)]
    return []
