from pathlib import Path

import numpy as np
import pytest
import geopandas as gpd
from shapely.geometry import Polygon

from pipeline.sources.hsy_buildings import deduplicate_hsy_buildings, normalize_hsy_buildings, project_hsy_buildings, read_hsy_buildings
from pipeline.sources.helsinki_buildings import building_facts_by_vtj, house_types_by_vtj, read_helsinki_buildings


FIXTURE = Path(__file__).parents[1] / "fixtures" / "hsy_buildings.geojson"


def test_hsy_adapter_reads_configured_required_fields_and_crs() -> None:
    buildings = read_hsy_buildings(FIXTURE, {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"})

    assert buildings.crs.to_epsg() == 4326
    assert len(buildings) == 1


def test_hsy_adapter_can_apply_the_configured_source_crs() -> None:
    buildings = read_hsy_buildings(FIXTURE, {"vtj_prt"}, source_crs=3879)

    assert buildings.crs.to_epsg() == 3879


def test_hsy_adapter_reports_schema_drift() -> None:
    with pytest.raises(ValueError, match="missing required fields: national_building_id"):
        read_hsy_buildings(FIXTURE, {"national_building_id"})


def test_hsy_buildings_are_explicitly_projected_for_area_work() -> None:
    buildings = read_hsy_buildings(FIXTURE, {"vtj_prt"})

    projected = project_hsy_buildings(buildings)

    assert projected.crs.to_epsg() == 3067
    assert projected.geometry.area.iloc[0] > 0


def test_hsy_live_fields_map_to_building_contract_without_inventing_house_type() -> None:
    source = read_hsy_buildings(FIXTURE, {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"})

    building = normalize_hsy_buildings(source)[0]

    assert building.building_id == "fixture-1"
    assert building.municipality == "Helsinki"
    assert building.construction_years == (1970,)
    assert building.residential_use is True
    assert building.house_type is None


def test_hsy_adapter_keeps_numpy_construction_years() -> None:
    source = read_hsy_buildings(FIXTURE, {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"})
    source.loc[0, "kavu"] = np.int64(1970)

    building = normalize_hsy_buildings(source)[0]

    assert building.construction_years == (1970,)


def test_hsy_adapter_keeps_integer_valued_float_construction_years() -> None:
    source = read_hsy_buildings(FIXTURE, {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"})
    source.loc[0, "kavu"] = 1970.0

    building = normalize_hsy_buildings(source)[0]

    assert building.construction_years == (1970,)


def test_hsy_adapter_deduplicates_identical_source_polygons_for_one_building() -> None:
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    source = gpd.GeoDataFrame(
        {"vtj_prt": ["a", "a"], "raktun": ["r", "r"], "kunta": ["091", "091"]},
        geometry=[polygon, polygon],
        crs=4326,
    )

    result = deduplicate_hsy_buildings(source)

    assert len(result) == 1


def test_helsinki_building_classes_map_to_release_house_types_without_conflicts() -> None:
    registry = gpd.GeoDataFrame(
        {"vtj_prt": ["one", "two", "row", "flat-low", "flat", "other", "flat"], "c_rakennusluokka": ["0110", "0111", "0112", "0120", "0121", "0130", "0121"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])] * 7,
        crs=4326,
    )

    assert house_types_by_vtj(registry) == {
        "one": "omakotitalo", "two": "paritalo", "row": "rivitalo", "flat-low": "kerrostalo", "flat": "kerrostalo",
    }


def test_helsinki_building_class_conflicts_and_schema_drift_remain_unknown(tmp_path: Path) -> None:
    registry = gpd.GeoDataFrame(
        {"vtj_prt": ["conflict", "conflict"], "c_rakennusluokka": ["0110", "0111"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])] * 2,
        crs=4326,
    )

    assert house_types_by_vtj(registry) == {}
    path = tmp_path / "missing-field.geojson"
    registry.drop(columns="c_rakennusluokka").to_file(path, driver="GeoJSON")
    with pytest.raises(ValueError, match="c_rakennusluokka"):
        read_helsinki_buildings(path)


def test_helsinki_building_facts_map_known_codes_and_preserve_conflicts_as_unknown() -> None:
    registry = gpd.GeoDataFrame(
        {
            "vtj_prt": ["flat", "flat", "conflict", "conflict", "no-lift"],
            "c_hissi": ["x", None, "x", "x", None],
            "c_lammtapa": ["1", "1", "2", "3", "1"],
            "c_poltaine": ["9", "9", "1", "1", "1"],
            "i_kerrlkm": [7, 7, 2, 2, 1],
            "i_asuinhuoneistojen_lkm": [42, 42, 8, 8, 1],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])] * 5,
        crs=4326,
    )
    facts = building_facts_by_vtj(registry)

    assert facts["flat"].elevator == "yes"
    assert facts["flat"].heating_method == "water_central"
    assert facts["flat"].heating_energy_source == "ground_source_heat"
    assert facts["flat"].storey_count == 7
    assert facts["flat"].dwelling_count == 42
    assert facts["conflict"].heating_method is None
    assert facts["no-lift"].elevator is None


def test_helsinki_building_facts_missing_fields_remain_unknown() -> None:
    registry = gpd.GeoDataFrame(
        {"vtj_prt": ["one"], "c_rakennusluokka": ["0121"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])],
        crs=4326,
    )

    assert building_facts_by_vtj(registry) == {}
