from __future__ import annotations

from pathlib import Path

import geopandas as gpd


HEALTH_SERVICE_GROUPS = (
    "health_centre", "dental_care", "maternity_and_child_health_clinic", "mental_health_and_substance_use_services",
    "university_or_central_hospital", "mehilainen", "terveystalo", "pihlajalinna", "other_private_clinic", "social_services",
)
WELLBEING_SERVICE_CLASS_GROUPS = {
    "dental_care": ("P5.10",),
    "maternity_and_child_health_clinic": ("P5.2",),
    "mental_health_and_substance_use_services": ("P5.7",),
    "social_services": ("P4", "P4.1", "P4.2", "P4.3", "P4.4", "P4.5", "P4.6", "P4.7", "P4.8", "P4.9", "P4.10", "P4.11", "P4.12", "P4.13", "P4.14"),
}
PTV_GROUP_LABELS = {
    "health_centre": "Terveyskeskus",
    "dental_care": "Hammashoito",
    "maternity_and_child_health_clinic": "Neuvola",
    "mental_health_and_substance_use_services": "Mielenterveys- ja päihdepalvelu",
    "university_or_central_hospital": "Yliopisto- tai keskussairaala",
    "mehilainen": "Mehiläinen",
    "terveystalo": "Terveystalo",
    "pihlajalinna": "Pihlajalinna",
    "other_private_clinic": "Yksityinen lääkäriasema",
    "social_services": "Sosiaalipalvelu",
}


def extract_health_destinations(path: Path) -> dict[str, gpd.GeoDataFrame]:
    locations = gpd.read_file(path)
    if locations.crs is None:
        raise ValueError("PTV healthcare snapshot has no CRS")
    if "health_group" not in locations:
        raise ValueError("PTV healthcare snapshot is missing health_group")
    columns = ["health_group", "geometry", "name"] if "name" in locations else ["health_group", "geometry"]
    points = locations.loc[locations.geometry.notna() & ~locations.geometry.is_empty, columns].copy().to_crs(4326)
    points["name"] = points["name"].fillna("").astype(str) if "name" in points else ""
    points["name"] = points["name"].where(points["name"].str.strip().ne(""), points["health_group"].map(PTV_GROUP_LABELS).fillna(points["health_group"]))
    points["geometry"] = points.geometry.representative_point()
    return {
        group: points.loc[points["health_group"] == group, ["name", "geometry"]].copy()
        for group in HEALTH_SERVICE_GROUPS
    }


def classify_health_location(organization: dict[str, object], channel: dict[str, object]) -> str | None:
    organization_name = _finnish_name(organization).casefold()
    channel_name = _finnish_name(channel).casefold()
    name = f"{organization_name} {channel_name}"
    if "mehiläinen" in name:
        return "mehilainen"
    if "terveystalo" in name:
        return "terveystalo"
    if "pihlajalinna" in name:
        return "pihlajalinna"
    if "yliopistollinen sairaala" in name or "yliopistosairaala" in name or "keskussairaala" in name or ("hus" in organization_name and "sairaala" in channel_name):
        return "university_or_central_hospital"
    if organization.get("organizationType") != "Company" and ("terveysasema" in name or "terveyskeskus" in name):
        return "health_centre"
    if organization.get("organizationType") == "Company" and any(token in name for token in ("lääkäri", "terveys", "klinikka", "sairaala")):
        return "other_private_clinic"
    return None


def classify_wellbeing_location(organization: dict[str, object], channel: dict[str, object], service_groups: tuple[str, ...]) -> set[str]:
    groups = {group for group in (classify_health_location(organization, channel),) if group is not None}
    groups.update(service_groups)
    return groups


def classify_wellbeing_service_classes(service_classes: tuple[str, ...]) -> set[str]:
    return {group for group, codes in WELLBEING_SERVICE_CLASS_GROUPS.items() if set(service_classes).intersection(codes)}


def _finnish_name(item: dict[str, object]) -> str:
    versions = item.get("languageVersions")
    if not isinstance(versions, dict):
        return ""
    finnish = versions.get("fi")
    return str(finnish.get("name", "")) if isinstance(finnish, dict) else ""
