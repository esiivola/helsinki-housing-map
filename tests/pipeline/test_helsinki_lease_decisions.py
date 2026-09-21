import geopandas as gpd
from shapely.geometry import Point

from pipeline.sources.helsinki_lease_decisions import (
    extract_property_ids,
    extract_vtj_prt_ids,
    is_city_land_lease_candidate,
    matching_buildings_by_decision,
)


def test_extracts_and_normalizes_helsinki_property_identifiers() -> None:
    text = "kiinteistöstä 91-437-1-14 ja tontin 91-45-144-2 asuntotarkoituksiin"

    assert extract_property_ids(text) == ("09143700010014", "09104501440002")


def test_extracts_national_building_identifiers_without_confusing_property_ids() -> None:
    text = "Rakennustunnukset 103276294B ja 103276295C, kiinteistö 91-45-144-2."

    assert extract_vtj_prt_ids(text) == ("103276294B", "103276295C")


def test_requires_lease_and_land_language_for_candidate() -> None:
    assert is_city_land_lease_candidate(
        "Vuokraus, maa-alue", "Helsingin kaupungin kiinteistöstä 91-437-1-14 asuntotarkoituksiin."
    )
    assert not is_city_land_lease_candidate("Vuokraus", "Asunnon vuokraaminen työntekijälle.")
    assert not is_city_land_lease_candidate("Kiinteistö", "Helsingin kaupungin kiinteistöstä luovutetaan alue.")


def test_maps_property_and_vtj_identifiers_to_all_matching_hsy_buildings() -> None:
    buildings = gpd.GeoDataFrame(
        {
            "kiitun": ["09143700010014", "09143700010014", "09104501440002"],
            "vtj_prt": ["one", "two", "103276294B"],
            "raktun": ["r-one", "r-two", "r-three"],
        },
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)], crs=4326,
    )
    decisions = [
        {"issue_id": "HEL-ONE", "property_ids": ["09143700010014"], "vtj_prt_ids": []},
        {"issue_id": "HEL-TWO", "property_ids": [], "vtj_prt_ids": ["103276294B"]},
    ]

    matched = matching_buildings_by_decision(decisions, buildings)

    assert matched == {
        "HEL-ONE": {"one", "two"},
        "HEL-TWO": {"103276294B"},
    }
