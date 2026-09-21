from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

import geopandas as gpd


PROPERTY_IDENTIFIER = re.compile(
    r"(?<!\d)(?:0?91)\s*[-–—]\s*(\d{1,3})\s*[-–—]\s*(\d{1,4})\s*[-–—]\s*(\d{1,4})(?!\d)"
)
VTJ_PRT_IDENTIFIER = re.compile(r"(?<![0-9A-Z])\d{9}[0-9A-Z](?![0-9A-Z])")
LEASE_LANGUAGE = re.compile(r"\bvuokra\w*", re.IGNORECASE)
LAND_LANGUAGE = re.compile(r"\b(?:maa-alue|maanvuokra|tontt\w*|kiinteist\w*|korttel\w*)", re.IGNORECASE)
CITY_LANGUAGE = re.compile(r"\bHelsingin kaupung\w*", re.IGNORECASE)


def extract_property_ids(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"091{district.zfill(3)}{block.zfill(4)}{lot.zfill(4)}"
            for district, block, lot in PROPERTY_IDENTIFIER.findall(text)
        )
    )


def extract_vtj_prt_ids(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(VTJ_PRT_IDENTIFIER.findall(text.upper())))


def is_city_land_lease_candidate(subject: str, decision_text: str) -> bool:
    text = f"{subject}\n{decision_text}"
    return bool(
        LEASE_LANGUAGE.search(text)
        and LAND_LANGUAGE.search(text)
        and CITY_LANGUAGE.search(text)
    )


def normalized_decision_record(
    issue_id: str, decision_date: str | None, subject: str, decision_text: str
) -> dict[str, object] | None:
    if not is_city_land_lease_candidate(subject, decision_text):
        return None
    property_ids = extract_property_ids(decision_text)
    vtj_prt_ids = extract_vtj_prt_ids(decision_text)
    if not property_ids and not vtj_prt_ids:
        return None
    return {
        "issue_id": issue_id,
        "decision_date": decision_date,
        "source_url": f"https://paatokset.hel.fi/fi/asia/{issue_id.lower()}",
        "property_ids": list(property_ids),
        "vtj_prt_ids": list(vtj_prt_ids),
    }


def matching_buildings_by_decision(
    decisions: Iterable[Mapping[str, object]], buildings: gpd.GeoDataFrame
) -> dict[str, set[str]]:
    required = {"kiitun", "vtj_prt", "raktun"}
    missing = required.difference(buildings.columns)
    if missing:
        raise ValueError(f"HSY buildings are missing {sorted(missing)[0]}")

    by_property: dict[str, set[str]] = defaultdict(set)
    by_vtj: dict[str, set[str]] = defaultdict(set)
    for row in buildings[["kiitun", "vtj_prt", "raktun"]].itertuples(index=False):
        kiitun, vtj_prt, raktun = row
        building_id = vtj_prt if isinstance(vtj_prt, str) and vtj_prt else raktun
        if not isinstance(building_id, str) or not building_id:
            continue
        if isinstance(kiitun, str) and kiitun:
            by_property[kiitun].add(building_id)
        if isinstance(vtj_prt, str) and vtj_prt:
            by_vtj[vtj_prt].add(building_id)

    result: dict[str, set[str]] = {}
    for decision in decisions:
        issue_id = decision.get("issue_id")
        if not isinstance(issue_id, str) or not issue_id:
            continue
        buildings_for_decision: set[str] = set()
        for property_id in decision.get("property_ids", []):
            if isinstance(property_id, str):
                buildings_for_decision.update(by_property[property_id])
        for vtj_prt_id in decision.get("vtj_prt_ids", []):
            if isinstance(vtj_prt_id, str):
                buildings_for_decision.update(by_vtj[vtj_prt_id])
        result[issue_id] = buildings_for_decision
    return result
