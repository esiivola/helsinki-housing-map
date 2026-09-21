from __future__ import annotations

from pathlib import Path

import geopandas as gpd


EDUCATION_SERVICE_GROUPS = ("daycare", "primary_school", "lower_secondary_school", "upper_secondary_school", "vocational_school")


def extract_education_destinations(path: Path) -> dict[str, gpd.GeoDataFrame]:
    units = gpd.read_file(path)
    if units.crs is None:
        raise ValueError("Service Map snapshot has no CRS")
    if "service_fi" not in units:
        raise ValueError("Service Map snapshot is missing service_fi")
    services = units["service_fi"].fillna("").map(_normalise)
    columns = ["geometry", "name_fi"] if "name_fi" in units else ["geometry"]
    points = units.loc[units.geometry.notna() & ~units.geometry.is_empty, columns].copy().to_crs(4326)
    points["service_fi"] = services.loc[points.index]
    points["name"] = points["name_fi"].fillna(points["service_fi"]).astype(str) if "name_fi" in points else points["service_fi"]
    points["geometry"] = points.geometry.representative_point()
    return {
        group: points.loc[_service_group_mask(points["service_fi"], group), ["name", "geometry"]].copy()
        for group in EDUCATION_SERVICE_GROUPS
    }


def _service_group_mask(services, group: str):
    if group == "daycare":
        return services.str.contains("päivähoito") & ~services.str.contains("asiakaspalvelu|ohjausalue|leikkitoiminta|esiopetus|perhepäivähoito")
    if group == "primary_school":
        return services.str.contains("perusopetus luokille 1-6")
    if group == "lower_secondary_school":
        return services.str.contains("perusopetus luokille 7-9")
    if group == "upper_secondary_school":
        return services.str.endswith("lukiokoulutus") & ~services.str.contains("aikuisten|asiakaspalvelu|ohjaus")
    if group == "vocational_school":
        return (services.str.contains("ammatillinen peruskoulutus") | services.str.endswith("ammatillinen koulutus")) & ~services.str.contains("lisäkoulutus|asiakaspalvelu|ohjaus|opiskelija|myymälä")
    raise ValueError(f"Unknown education service group: {group}")


def _normalise(value: object) -> str:
    return str(value).strip().casefold()
