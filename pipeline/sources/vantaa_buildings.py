from __future__ import annotations

from pathlib import Path

import geopandas as gpd


HOUSE_TYPE_BY_BUILDING_CLASS = {
    "0110": "omakotitalo",
    "0111": "paritalo",
    "0112": "rivitalo",
    "0120": "kerrostalo",
    "0121": "kerrostalo",
}


def house_types_by_vtj(path: Path) -> dict[str, str]:
    buildings = gpd.read_file(path)
    missing = {"vtj_prt", "kayttotarkoitus"}.difference(buildings.columns)
    if missing:
        raise ValueError(f"Vantaa buildings source missing fields: {', '.join(sorted(missing))}")
    types: dict[str, str] = {}
    conflicts: set[str] = set()
    for row in buildings[["vtj_prt", "kayttotarkoitus"]].itertuples(index=False):
        building_id = row.vtj_prt
        house_type = HOUSE_TYPE_BY_BUILDING_CLASS.get(str(row.kayttotarkoitus)[:4])
        if not isinstance(building_id, str) or house_type is None:
            continue
        if building_id in types and types[building_id] != house_type:
            conflicts.add(building_id)
        else:
            types[building_id] = house_type
    return {building_id: house_type for building_id, house_type in types.items() if building_id not in conflicts}
