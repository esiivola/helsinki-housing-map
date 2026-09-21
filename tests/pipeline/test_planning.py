from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from pipeline.sources.planning import active_plan_properties, assign_active_plan_status, read_active_plan_areas


def test_active_plans_mark_intersecting_buildings_yes_and_other_helsinki_buildings_no() -> None:
    buildings = gpd.GeoDataFrame({"building_id": ["yes", "no"]}, geometry=[Polygon([(0, 0), (2, 0), (2, 2), (0, 0)]), Polygon([(4, 0), (5, 0), (5, 1), (4, 0)])], crs=3067)
    areas = gpd.GeoDataFrame({"luokka": ["Vireillä"]}, geometry=[Polygon([(1, 0), (3, 0), (3, 2), (1, 0)])], crs=3067)

    values = assign_active_plan_status(buildings, areas)

    assert values["yes"].value == "yes"
    assert values["no"].value == "no"


def test_active_plans_reader_requires_status_and_crs(tmp_path: Path) -> None:
    path = tmp_path / "plans.geojson"
    gpd.GeoDataFrame({"luokka": ["Vireillä", "Voimassa"]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]), Polygon([(2, 0), (3, 0), (3, 1), (2, 0)])], crs=3067).to_file(path, driver="GeoJSON")

    assert len(read_active_plan_areas(path)) == 1


def test_active_plan_properties_keep_only_public_popup_details() -> None:
    properties = active_plan_properties({
        "id": 8,
        "tyyppi": "Kaava",
        "kaavatunnus": "12990",
        "luokka": "Vireillä",
        "pintaala": 7297.97007,
        "hyvaksymispvm": "kylk 27.1.2026",
        "paivitetty_tietopalveluun": "2026-08-28 00:00:00",
        "datanomistaja": "Helsinki/KAMI",
    })

    assert properties == {
        "plan_number": "12990",
        "plan_type": "Kaava",
        "status": "Vireillä",
        "area_m2": 7297.97007,
        "approval": "kylk 27.1.2026",
        "source_updated_at": "2026-08-28",
    }
