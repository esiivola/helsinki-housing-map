from __future__ import annotations

import json
from pathlib import Path

from pipeline.sources.ptv import classify_health_location, classify_wellbeing_location, classify_wellbeing_service_classes, extract_health_destinations
from pipeline.sources.service_map import extract_education_destinations


def _feature(properties: dict[str, object], x: float, y: float) -> dict[str, object]:
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Point", "coordinates": [x, y]}}


def _snapshot(path: Path, features: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def test_service_map_groups_only_actual_education_service_units(tmp_path: Path) -> None:
    path = _snapshot(tmp_path / "service-map.geojson", [
        _feature({"name_fi": "Päiväkoti Testi", "service_fi": "suomenkielinen päivähoito"}, 24.9, 60.1),
        _feature({"service_fi": "perhepäivähoidon ohjausalueet"}, 24.91, 60.1),
        _feature({"service_fi": "suomenkielinen perusopetus luokille 1-6"}, 24.92, 60.1),
        _feature({"service_fi": "suomenkielinen perusopetus luokille 7-9"}, 24.93, 60.1),
        _feature({"service_fi": "suomenkielinen lukiokoulutus"}, 24.94, 60.1),
        _feature({"service_fi": "aikuisten lukiokoulutus"}, 24.95, 60.1),
        _feature({"service_fi": "ammatillinen peruskoulutus"}, 24.96, 60.1),
        _feature({"service_fi": "ammatillinen lisäkoulutus"}, 24.97, 60.1),
    ])

    grouped = extract_education_destinations(path)

    assert {group: len(points) for group, points in grouped.items()} == {
        "daycare": 1,
        "primary_school": 1,
        "lower_secondary_school": 1,
        "upper_secondary_school": 1,
        "vocational_school": 1,
    }
    assert all(str(points.crs).upper() == "EPSG:4326" for points in grouped.values())
    assert grouped["daycare"].iloc[0]["name"] == "Päiväkoti Testi"


def test_ptv_health_snapshot_keeps_only_supported_groups(tmp_path: Path) -> None:
    path = _snapshot(tmp_path / "health.geojson", [
        _feature({"health_group": "mehilainen", "name": "Mehiläinen Testi"}, 24.9, 60.1),
        _feature({"health_group": "health_centre"}, 24.91, 60.1),
        _feature({"health_group": "not-a-group"}, 24.92, 60.1),
    ])

    grouped = extract_health_destinations(path)

    assert len(grouped["mehilainen"]) == 1
    assert len(grouped["health_centre"]) == 1
    assert len(grouped["terveystalo"]) == 0
    assert grouped["mehilainen"].iloc[0]["name"] == "Mehiläinen Testi"
    assert grouped["health_centre"].iloc[0]["name"] == "Terveyskeskus"


def test_ptv_classification_uses_provider_type_before_generic_healthcare_names() -> None:
    named = {"organizationType": "Company", "languageVersions": {"fi": {"name": "Mehiläinen"}}}
    public = {"organizationType": "Municipality", "languageVersions": {"fi": {"name": "Helsingin kaupunki"}}}
    company = {"organizationType": "Company", "languageVersions": {"fi": {"name": "Lääkärikeskus Oy"}}}

    assert classify_health_location(named, {"languageVersions": {"fi": {"name": "Terveysasema"}}}) == "mehilainen"
    assert classify_health_location(public, {"languageVersions": {"fi": {"name": "Kalasataman terveysasema"}}}) == "health_centre"
    assert classify_health_location(company, {"languageVersions": {"fi": {"name": "Klinikka"}}}) == "other_private_clinic"
    assert classify_health_location({"organizationType": "RegionalOrganization", "languageVersions": {"fi": {"name": "HUS-yhtymä"}}}, {"languageVersions": {"fi": {"name": "Meilahden sairaala"}}}) == "university_or_central_hospital"


def test_ptv_service_links_classify_wellbeing_categories_from_documented_service_classes() -> None:
    organization = {"organizationType": "Municipality", "languageVersions": {"fi": {"name": "Helsingin kaupunki"}}}
    channel = {"languageVersions": {"fi": {"name": "Palvelupiste"}}}

    assert classify_wellbeing_location(organization, channel, ("dental_care",)) == {"dental_care"}
    assert classify_wellbeing_location(organization, channel, ("maternity_and_child_health_clinic",)) == {"maternity_and_child_health_clinic"}
    assert classify_wellbeing_location(organization, channel, ("mental_health_and_substance_use_services",)) == {"mental_health_and_substance_use_services"}
    assert classify_wellbeing_location(organization, channel, ("social_services",)) == {"social_services"}
    assert classify_wellbeing_service_classes(("P5.10", "P4.4")) == {"dental_care", "social_services"}
