from __future__ import annotations

import json
import gzip
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.build import _workplace_layers, build_hsy_release, complete_workplace_transit_destinations, load_transit_batches, load_workplace_transit_batches
from pipeline.export.web_bundle import _layer_distributions, _layer_value_data, _overview_summaries, _score_inputs, _visualization_breaks, linear_histogram
from pipeline.models import BuildingValue, Confidence, LayerValueRecord, SourceManifest, ValueKind, ValueMethod, ValueState


FIXTURE = Path(__file__).parents[1] / "fixtures" / "hsy_buildings.geojson"
PAAVO_FIXTURE = Path(__file__).parents[1] / "fixtures" / "paavo_areas.geojson"
NOISE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "helsinki_noise_2022.geojson"
OSM_FIXTURE = Path(__file__).parents[1] / "fixtures" / "osm_destinations.osm"
GROCERY_STORE_LAYERS = {f"grocery_store_{group}_walk_m" for group in ("prisma", "k_citymarket", "lidl", "s_market", "k_supermarket", "sale", "k_market", "alepa", "other_supermarket", "other_grocery")}


def _helsinki_buildings_fixture(path: Path) -> Path:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"vtj_prt": "fixture-1", "c_rakennusluokka": "0121", "c_hissi": "x", "c_lammtapa": "1", "c_poltaine": "9", "i_kerrlkm": 7, "i_asuinhuoneistojen_lkm": 42}, "geometry": {"type": "Polygon", "coordinates": [[[24.9, 60.1], [24.91, 60.1], [24.91, 60.11], [24.9, 60.11], [24.9, 60.1]]]}}]}))
    return path


def _helsinki_building_ownership_fixture(path: Path) -> Path:
    path.write_text("building_id,luokka\nfixture-1,kaupunki\n")
    return path


def test_non_finite_layer_value_exports_as_explicit_unknown() -> None:
    record = LayerValueRecord("fixture-1", "grocery_walk_m", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, float("nan"), coverage=1, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM))

    assert _layer_value_data(record)["state"] == "unknown"
    assert _layer_value_data(record)["value"] is None


def test_overview_summaries_use_numeric_medians_and_categorical_modes() -> None:
    records = [
        LayerValueRecord("a", "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, 20)),
        LayerValueRecord("b", "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, 40)),
        LayerValueRecord("c", "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, 100)),
        LayerValueRecord("a", "land_owner_class", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, "city")),
        LayerValueRecord("b", "land_owner_class", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, "city")),
        LayerValueRecord("c", "land_owner_class", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, "non_city")),
        LayerValueRecord("a", "building_year", BuildingValue(ValueState.KNOWN, ValueKind.MULTI, None, values=(1990, 2010))),
    ]

    assert _overview_summaries(records, ["a", "b", "c"]) == {
        "income_median_eur": {"min": 20, "median": 40, "max": 100},
        "building_year": {"min": 2000, "median": 2000, "max": 2000},
        "land_owner_class": {"value": "city", "mode_share": 2 / 3},
    }


def test_visualization_breaks_use_the_published_value_distribution() -> None:
    records = [
        LayerValueRecord(str(index), "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, value))
        for index, value in enumerate((0, 10, 20, 30, 100))
    ]

    assert _visualization_breaks(records, (0, 100), "income_median_eur") == (0.8, 6, 14.4, 22.4, 28.8, 55.2, 77.6)
    assert _visualization_breaks(records, (0, 100), "grocery_walk_m") == (0.8, 3.2, 6.4, 11.2, 17.6, 25.6, 58)
    boarding_records = [
        LayerValueRecord(str(index), "transit_workplace_rautatieasema_median_boarding", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, value))
        for index, value in enumerate((1, 1, 2, 3, 4))
    ]
    assert _visualization_breaks(boarding_records, (0, 4), "transit_workplace_rautatieasema_median_boarding") == (1, 2, 3, 4)


def test_linear_histogram_snaps_to_true_extremes_when_close() -> None:
    # p1=1, p99=99, but the true min (0) and max (100) sit within half the
    # inter-percentile spread of the fence, so the axis snaps out to them and no
    # value is dropped -- the true minimum and maximum are shown.
    result = linear_histogram([float(value) for value in range(0, 101)], bin_count=10)

    assert len(result["counts"]) == 10
    assert sum(result["counts"]) == 101
    assert result["known_count"] == 101
    assert result["min"] == 0.0 and result["max"] == 100.0


def test_linear_histogram_keeps_the_fence_against_sentinel_outliers() -> None:
    # A dense body of real values with a low sentinel (1) and a high sentinel
    # (999999999), as building_year carries. Both sit far beyond half the
    # inter-percentile spread, so the axis stays on the p1/p99 fence and the
    # sentinels are dropped from the bars.
    values = [1.0] + [float(1900 + (index % 120)) for index in range(600)] + [999999999.0]
    result = linear_histogram(sorted(values), bin_count=10)

    assert result["known_count"] == 602
    assert 1900.0 <= result["min"] <= 1902.0
    assert 2018.0 <= result["max"] <= 2020.0
    # Both sentinels (and the sliver of bulk beyond the fence) are dropped; the
    # axis never stretches to 1 or 999999999.
    assert 585 <= sum(result["counts"]) <= 595


def test_layer_distribution_bins_values_linearly_and_reports_its_span() -> None:
    records = [
        LayerValueRecord(str(index), "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, value))
        for index, value in enumerate((0, 10, 20, 30, 100))
    ]

    distribution = _layer_distributions(records, [{"layer_id": "income_median_eur", "kind": "numeric", "visualization_breaks": (0.8, 6, 14.4, 22.4, 28.8, 55.2, 77.6)}])["distributions"][0]
    assert distribution["layer_id"] == "income_median_eur"
    assert distribution["known_count"] == 5
    assert len(distribution["counts"]) == 40
    # 0 and 100 are within half the inter-percentile spread of p1/p99, so the axis
    # snaps to the true span and every value is shown.
    assert sum(distribution["counts"]) == 5
    assert distribution["min"] == 0.0 and distribution["max"] == 100.0


def test_layer_distribution_keeps_an_all_unknown_numeric_layer_explicit() -> None:
    distribution = _layer_distributions([], [{"layer_id": "storey_count", "kind": "numeric", "visualization_breaks": (0, 20)}])["distributions"]

    assert distribution == [{"layer_id": "storey_count", "counts": [0] * 40, "known_count": 0, "min": 0.0, "max": 20.0}]


def test_overview_score_inputs_keep_building_values_together() -> None:
    records = [
        LayerValueRecord("a", "building_year", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, 1980)),
        LayerValueRecord("a", "income_median_eur", BuildingValue(ValueState.KNOWN, ValueKind.SCALAR, 50_000)),
    ]

    assert _score_inputs(records, ["a"]) == [{"building_year": {"state": "known", "value": 1980, "values": []}, "income_median_eur": {"state": "known", "value": 50_000, "values": []}}]


def test_transit_batches_preserve_partial_values_and_missing_buildings_as_unknown(tmp_path: Path) -> None:
    (tmp_path / "transit-0000.json").write_text(json.dumps({"values": {"a": {"state": "partial", "value": 42, "coverage": 22 / 23}}}))

    values = load_transit_batches(tmp_path, ["a", "b"])

    assert values["a"].state is ValueState.PARTIAL
    assert values["a"].value == 42
    assert values["b"].state is ValueState.UNKNOWN


def test_transit_sample_batches_derive_the_current_maximum_value(tmp_path: Path) -> None:
    pq.write_table(
        pa.table({
            "building_id": ["a", "a", "a"],
            "departure_time": ["07:00", "07:15", "07:30"],
            "state": ["known", "unknown", "known"],
            "duration_seconds": [1_800, None, 2_400],
            "transfers": [0, None, 1],
            "walk_seconds": [120, None, 240],
        }),
        tmp_path / "transit-0000.parquet",
    )

    values = load_transit_batches(tmp_path, ["a", "b"])

    assert values["a"].state is ValueState.PARTIAL
    assert values["a"].value == 40
    assert values["a"].coverage == 2 / 3
    assert values["b"].state is ValueState.UNKNOWN


def test_workplace_batches_emit_time_boarding_and_first_walk_medians(tmp_path: Path) -> None:
    ready = tmp_path / "ruoholahti"
    ready.mkdir()
    pq.write_table(pa.table({"building_id": ["a", "a", "a"], "departure_time": ["07:00", "07:15", "07:30"], "state": ["known", "known", "known"], "duration_seconds": [1_800, 2_400, 3_600], "boardings": [1, 2, 2], "first_boarding_walk_m": [100, 300, 500]}), ready / "transit-0000.parquet")

    values = load_workplace_transit_batches(tmp_path, ["ruoholahti", "pasila"], ["a", "b"])

    assert values["ruoholahti"]["min"]["a"].value == 30
    assert values["ruoholahti"]["median"]["a"].value == 40
    assert values["ruoholahti"]["max"]["a"].value == 60
    assert values["ruoholahti"]["median_boarding"]["a"].value == 2
    assert values["_all"]["median_first_boarding_walk_m"]["a"].value == 300
    assert values["ruoholahti"]["min"]["b"].state is ValueState.UNKNOWN
    assert values["pasila"]["min"]["a"].state is ValueState.UNKNOWN


def test_workplace_batch_loading_does_not_scan_the_building_id_list_for_each_sample(tmp_path: Path) -> None:
    directory = tmp_path / "ruoholahti"
    directory.mkdir()
    pq.write_table(pa.table({"building_id": ["a"], "departure_time": ["07:00"], "state": ["known"], "duration_seconds": [1_800], "boardings": [1], "first_boarding_walk_m": [100]}), directory / "transit-0000.parquet")

    class BuildingIds(list[str]):
        def __contains__(self, item: object) -> bool:
            raise AssertionError("batch loading must use a set for sample membership")

    values = load_workplace_transit_batches(tmp_path, ["ruoholahti"], BuildingIds(["a"]))

    assert values["ruoholahti"]["median"]["a"].value == 30


def test_only_complete_workplace_destinations_are_published(tmp_path: Path) -> None:
    ready = tmp_path / "ruoholahti"
    ready.mkdir()
    pq.write_table(pa.table({"building_id": ["a", "a", "b", "b"], "departure_time": ["07:00", "07:15", "07:00", "07:15"], "state": ["known", "known", "known", "known"], "duration_seconds": [1_800, 2_400, 2_100, 2_700]}), ready / "transit-0000.parquet")
    incomplete = tmp_path / "aviapolis"
    incomplete.mkdir()
    pq.write_table(pa.table({"building_id": ["a", "a"], "departure_time": ["07:00", "07:15"], "state": ["known", "known"], "duration_seconds": [1_800, 2_400]}), incomplete / "transit-0000.parquet")

    assert complete_workplace_transit_destinations(tmp_path, ["ruoholahti", "aviapolis"], ["a", "b"], 2) == {"ruoholahti"}


def test_workplace_completion_rejects_an_old_itinerary_detail_version(tmp_path: Path) -> None:
    ready = tmp_path / "ruoholahti"
    ready.mkdir()
    table = pa.table({"building_id": ["a", "a"], "departure_time": ["07:00", "07:01"]})
    table = table.replace_schema_metadata({b"transit_parameters": json.dumps({"samples": ["07:00", "07:01"], "itinerary_detail_version": 3}).encode()})
    pq.write_table(table, ready / "transit-0000.parquet")

    assert complete_workplace_transit_destinations(tmp_path, ["ruoholahti"], ["a"], 2, itinerary_detail_version=4) == set()


def test_incomplete_workplace_transit_destination_keeps_its_bike_layer_only() -> None:
    layers = _workplace_layers(
        [{"id": "ruoholahti", "name": "Ruoholahti"}, {"id": "aviapolis", "name": "Aviapolis"}],
        {"ruoholahti"},
    )

    assert "bike_workplace_aviapolis_effective_min" in layers
    assert "transit_workplace_aviapolis_median_min" not in layers
    assert "transit_workplace_ruoholahti_median_min" in layers
    assert "transit_workplace_ruoholahti_median_boarding" in layers
    assert "transit_workplace_median_first_boarding_walk_m" not in layers


def test_complete_workplace_layers_include_the_combined_first_walk_metric() -> None:
    layers = _workplace_layers(
        [{"id": "ruoholahti", "name": "Ruoholahti"}, {"id": "aviapolis", "name": "Aviapolis"}],
        {"ruoholahti", "aviapolis"},
    )

    assert "transit_workplace_median_first_boarding_walk_m" in layers
    assert layers["transit_workplace_median_first_boarding_walk_m"].finnish_label == "Aamumatka: kävelymatka ensimmäiselle pysäkille"


def test_hsy_release_exports_only_residential_buildings_and_year_evidence(tmp_path: Path) -> None:
    active_plans = tmp_path / "active-plans.geojson"
    active_plans.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"luokka": "Vireillä", "kaavatunnus": "12990", "tyyppi": "Kaava", "pintaala": 7298, "hyvaksymispvm": "kylk 27.1.2026", "paivitetty_tietopalveluun": "2026-08-28"}, "geometry": {"type": "Polygon", "coordinates": [[[24.8, 60.0], [25.0, 60.0], [25.0, 60.2], [24.8, 60.2], [24.8, 60.0]]]}}]}))
    build_hsy_release(
        FIXTURE,
        tmp_path,
        _source_manifest(),
        paavo_snapshot=PAAVO_FIXTURE,
        paavo_source_manifest=_paavo_source_manifest(),
        noise_snapshot=NOISE_FIXTURE,
        noise_source_manifest=_noise_source_manifest(),
        night_noise_snapshot=NOISE_FIXTURE,
        night_noise_source_manifest=_night_noise_source_manifest(),
        osm_snapshot=OSM_FIXTURE,
        osm_source_manifest=_osm_source_manifest(),
        helsinki_buildings_snapshot=_helsinki_buildings_fixture(tmp_path / "helsinki-buildings.geojson"),
        helsinki_buildings_source_manifest=_helsinki_buildings_source_manifest(),
        helsinki_building_ownership_snapshot=_helsinki_building_ownership_fixture(tmp_path / "building_ownership.csv"),
        helsinki_building_ownership_source_manifest=_helsinki_building_ownership_source_manifest(),
        active_plans_snapshot=active_plans,
        active_plans_source_manifest=_active_plans_source_manifest(),
        source_crs=4326,
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    attributes = json.loads(
        gzip.decompress((tmp_path / "attributes" / "Helsinki.json.gz").read_bytes())
    )

    assert manifest["attribute_partitions"] == ["attributes/Helsinki.json.gz"]
    assert manifest["layer_catalogue"] == "layers.json"
    assert manifest["layer_distributions"] == "layer-distributions.json"
    assert manifest["score_histogram_inputs"] == "score-histogram-inputs.json.gz"
    histogram_inputs = json.loads(gzip.decompress((tmp_path / "score-histogram-inputs.json.gz").read_bytes()))
    assert histogram_inputs["version"] == 1
    assert len(histogram_inputs["building_values"]) == len(attributes["buildings"])
    distributions = json.loads((tmp_path / "layer-distributions.json").read_text())
    assert distributions["version"] == 1
    assert any(item["layer_id"] == "income_median_eur" for item in distributions["distributions"])
    layers = json.loads((tmp_path / "layers.json").read_text())
    assert next(layer for layer in layers if layer["layer_id"] == "land_owner_class")["source_ids"] == ["helsinki_building_ownership"]
    assert {layer["layer_id"] for layer in layers} >= {
        "building_year", "house_type", "elevator", "heating_method", "heating_energy_source", "storey_count", "dwelling_count", "land_owner_class", "noise_day_upper_db", "noise_night_upper_db",
        "forest_walk_m", "shore_walk_m", "daycare_walk_m", "school_walk_m", "healthcare_walk_m", "library_walk_m",
        *GROCERY_STORE_LAYERS, "income_median_eur",
    }
    # Every workplace destination carries both a travel-time and a cycling-ease layer.
    assert {layer["layer_id"] for layer in layers if layer["layer_id"].startswith("bike_workplace_")} == {
        f"bike_workplace_{destination}_{metric}"
        for destination in ("ruoholahti", "keilaniemi", "kamppi", "pasila", "kalasatama", "tapiola", "leppavaara", "aviapolis", "tikkurila", "myyrmaki", "rautatieasema")
        for metric in ("effective_min",)
    }
    assert manifest["geometry_partitions"] == ["geometry/Helsinki.geojson.gz"]
    assert manifest["overlays"] == {
        "active-plans": "overlays/active-plans.geojson.gz",
        "service-destinations": "overlays/service-destinations.geojson.gz",
    }
    assert manifest["spatial_partitions"]["building_tier"]["tile_zoom"] == 16
    assert manifest["spatial_partitions"]["building_tier"]["min_zoom"] == 15
    assert manifest["spatial_partitions"]["building_tier"]["tile_keys"]
    assert manifest["spatial_partitions"]["building_tier"]["geometry_path_template"] == "tiles/geometry/16/{x}/{y}.geojson.gz"
    assert (tmp_path / "tiles" / "geometry" / "16").is_dir()
    assert not (tmp_path / "tiles" / "attributes" / "16").exists()
    assert (tmp_path / "tiles" / "core" / "16").is_dir()
    assert (tmp_path / "tiles" / "core" / "16").is_dir()
    assert (tmp_path / "tiles" / "layers" / "building_year" / "16").is_dir()
    overview_tier = manifest["spatial_partitions"]["overview_tiers"][0]
    assert overview_tier["tile_zoom"] == 10
    assert overview_tier["geometry_path_template"] == "overview/1000m/tiles/10/{x}/{y}.geojson.gz"
    assert overview_tier["layer_path_template"] == "overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz"
    assert overview_tier["tile_keys"]
    assert (tmp_path / "overview" / "1000m" / "tiles" / "10").is_dir()
    assert (tmp_path / "overview" / "500m" / "tiles" / "11").is_dir()
    assert (tmp_path / "overview" / "250m" / "tiles" / "12").is_dir()
    assert (tmp_path / "overview" / "500m" / "layers" / "income_median_eur" / "11").is_dir()
    assert (tmp_path / "background" / "osm.geojson.gz").is_file()
    overlay = json.loads(gzip.decompress((tmp_path / "overlays" / "active-plans.geojson.gz").read_bytes()))
    assert overlay["features"][0]["properties"] == {
        "plan_number": "12990",
        "plan_type": "Kaava",
        "status": "Vireillä",
        "area_m2": 7298.0,
        "approval": "kylk 27.1.2026",
        "source_updated_at": "2026-08-28",
    }
    assert overlay["features"][0]["geometry"]["type"] == "Polygon"
    service_destinations = json.loads(gzip.decompress((tmp_path / "overlays" / "service-destinations.geojson.gz").read_bytes()))
    assert {
        "type": "Feature",
        "properties": {"layer_id": "grocery_store_prisma_walk_m", "name": "Prisma Tripla"},
        "geometry": {"type": "Point", "coordinates": [24.92991, 60.19846]},
    } in service_destinations["features"]
    geometry = json.loads(gzip.decompress((tmp_path / "geometry" / "Helsinki.geojson.gz").read_bytes()))
    assert geometry["features"][0]["properties"] == {"building_id": "fixture-1"}
    assert attributes["buildings"] == [
        {
            "building_id": "fixture-1",
            "completed": True,
            "construction_years": [1970],
            "house_type": None,
            "municipality": "Helsinki",
            "residential_use": True,
            "source_id": "hsy_buildings",
        }
    ]
    assert attributes["building_values"][0]["values"] == [1970]
    assert attributes["building_values"][0]["evidence_ids"] == ["hsy-building-characteristics"]
    assert attributes["building_values"][1] == {
        "building_id": "fixture-1",
        "confidence": "high",
        "coverage": 1,
        "distribution": {},
        "evidence_ids": ["helsinki-building-class"],
        "kind": "scalar",
        "layer_id": "house_type",
        "method": "direct",
        "state": "known",
        "value": "kerrostalo",
        "values": [],
    }
    facts = {value["layer_id"]: value for value in attributes["building_values"]}
    assert facts["elevator"]["value"] == "yes"
    assert facts["heating_method"]["value"] == "water_central"
    assert facts["heating_energy_source"]["value"] == "ground_source_heat"
    assert facts["storey_count"]["value"] == 7
    assert facts["dwelling_count"]["value"] == 42
    assert facts["dwelling_count"]["evidence_ids"] == ["helsinki-building-facts"]
    assert facts["land_owner_class"]["value"] == "city"
    assert facts["land_owner_class"]["evidence_ids"] == ["helsinki-building-ownership"]
    income = next(value for value in attributes["building_values"] if value["layer_id"] == "income_median_eur")
    assert income["value"] == 32700
    assert income["evidence_ids"] == ["paavo-postal-area-income"]
    noise = next(value for value in attributes["building_values"] if value["layer_id"] == "noise_day_upper_db")
    assert noise["value"] == 55
    assert noise["evidence_ids"] == ["helsinki-noise-day-upper-bound"]
    night_noise = next(value for value in attributes["building_values"] if value["layer_id"] == "noise_night_upper_db")
    assert night_noise["value"] == 55
    assert night_noise["evidence_ids"] == ["helsinki-noise-night-upper-bound"]
    sources = json.loads((tmp_path / "sources.json").read_text())
    assert {source["source_id"] for source in sources} == {"hsy_buildings", "helsinki_buildings", "helsinki_building_ownership", "paavo_income", "helsinki_noise_2022", "helsinki_noise_night_2022", "helsinki_active_plans", "hsl_osm_extract"}
    assert all(set(layer["source_ids"]) <= {source["source_id"] for source in sources} for layer in layers)
    assert {value["layer_id"] for value in attributes["building_values"]} >= {
        "building_year", "house_type", "elevator", "heating_method", "heating_energy_source", "storey_count", "dwelling_count", "land_owner_class", "noise_day_upper_db", "noise_night_upper_db",
        "forest_walk_m", "shore_walk_m", "daycare_walk_m", "school_walk_m", "healthcare_walk_m", "library_walk_m",
        *GROCERY_STORE_LAYERS, "income_median_eur",
    }
    assert "katu" not in json.dumps(attributes)
    audit = json.loads((tmp_path / "audit.json").read_text())
    assert audit["performance"]["release_build_seconds"] >= 0
    assert audit["static_asset_metrics"]["building_tile_count"] >= 1
    assert audit["static_asset_metrics"]["largest_attribute_tile_bytes"] > 0
    assert audit["static_asset_metrics"]["compressed_bytes"] > 0
    assert audit["layer_value_state_counts_by_layer"]["income_median_eur"]["known"] == 1
    assert audit["layer_value_state_counts_by_municipality_and_layer"]["Helsinki"]["income_median_eur"]["known"] == 1
    assert audit["layer_value_state_counts_by_municipality_and_layer"]["Helsinki"]["house_type"]["known"] == 1
    assert audit["layer_value_state_counts_by_municipality_and_layer"]["Helsinki"]["dwelling_count"]["known"] == 1
    assert audit["layer_value_state_counts_by_municipality_and_layer"]["Helsinki"]["noise_night_upper_db"]["partial"] == 1


def test_hsy_release_requires_espoo_city_land_snapshot_and_provenance_together(tmp_path: Path) -> None:
    try:
        build_hsy_release(
            FIXTURE, tmp_path, _source_manifest(), PAAVO_FIXTURE, _paavo_source_manifest(), NOISE_FIXTURE,
            _noise_source_manifest(), OSM_FIXTURE,
            _osm_source_manifest(), source_crs=4326, espoo_city_land_snapshot=tmp_path / "city-land.geojson",
        )
    except ValueError as error:
        assert str(error) == "Espoo city-land snapshot and source manifest must be provided together"
    else:
        raise AssertionError("expected city-land provenance validation failure")


def test_hsy_release_requires_helsinki_ownership_snapshot_and_provenance_together(tmp_path: Path) -> None:
    try:
        build_hsy_release(
            FIXTURE, tmp_path, _source_manifest(), PAAVO_FIXTURE, _paavo_source_manifest(), NOISE_FIXTURE,
            _noise_source_manifest(), OSM_FIXTURE,
            _osm_source_manifest(), source_crs=4326, helsinki_building_ownership_snapshot=tmp_path / "building_ownership.csv",
        )
    except ValueError as error:
        assert str(error) == "Helsinki building ownership snapshot and source manifest must be provided together"
    else:
        raise AssertionError("expected ownership provenance validation failure")


def test_hsy_release_publishes_service_group_background_layers_only_with_snapshots(tmp_path: Path) -> None:
    service_map = tmp_path / "service-map.geojson"
    service_map.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"service_fi": "suomenkielinen päivähoito"}, "geometry": {"type": "Point", "coordinates": [24.9, 60.1]}},
        {"type": "Feature", "properties": {"service_fi": "suomenkielinen perusopetus luokille 1-6"}, "geometry": {"type": "Point", "coordinates": [24.9, 60.1]}},
    ]}))
    healthcare = tmp_path / "ptv-health.geojson"
    healthcare.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"health_group": "health_centre"}, "geometry": {"type": "Point", "coordinates": [24.9, 60.1]}},
        {"type": "Feature", "properties": {"health_group": "mehilainen"}, "geometry": {"type": "Point", "coordinates": [24.9, 60.1]}},
    ]}))
    service_manifest = SourceManifest("service_map_education", "Service Map", "https://example.test/service-map", "https://creativecommons.org/licenses/by/4.0/", "CC-BY-4.0", "Service Map", "2026-09-09T12:00:00+03:00", "2026-09-09", "Metro", "sha256:fixture", "fixture", ("fixture",), "allowed", "fixture")
    ptv_manifest = SourceManifest("ptv_healthcare", "PTV", "https://example.test/ptv", "https://creativecommons.org/publicdomain/zero/1.0/", "CC0-1.0", "PTV", "2026-09-09T12:00:00+03:00", "2026-09-09", "Metro", "sha256:fixture", "fixture", ("fixture",), "allowed", "fixture")

    build_hsy_release(FIXTURE, tmp_path, _source_manifest(), PAAVO_FIXTURE, _paavo_source_manifest(), NOISE_FIXTURE, _noise_source_manifest(), OSM_FIXTURE, _osm_source_manifest(), source_crs=4326, service_map_snapshot=service_map, service_map_source_manifest=service_manifest, ptv_health_snapshot=healthcare, ptv_health_source_manifest=ptv_manifest)

    layers = {layer["layer_id"]: layer for layer in json.loads((tmp_path / "layers.json").read_text())}
    values = json.loads(gzip.decompress((tmp_path / "attributes" / "Helsinki.json.gz").read_bytes()))["building_values"]
    assert {
        "education_service_daycare_walk_m", "education_service_primary_school_walk_m",
        "health_service_health_centre_walk_m", "health_service_mehilainen_walk_m",
        "health_service_dental_care_walk_m", "health_service_maternity_and_child_health_clinic_walk_m",
        "health_service_mental_health_and_substance_use_services_walk_m", "health_service_social_services_walk_m",
    } <= set(layers)
    assert layers["education_service_daycare_walk_m"]["visible"] is False
    assert layers["health_service_mehilainen_walk_m"]["visible"] is False
    assert layers["daycare_walk_m"]["visible"] is False
    assert layers["school_walk_m"]["visible"] is False
    assert layers["healthcare_walk_m"]["visible"] is False
    assert {"service_map_education", "ptv_healthcare"} <= {source["source_id"] for source in json.loads((tmp_path / "sources.json").read_text())}
    assert {"service-map-education-destination", "hsl-osm-routing"} <= set(next(value for value in values if value["layer_id"] == "education_service_daycare_walk_m")["evidence_ids"])


def _source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="hsy_buildings",
        name="HSY metropolitan buildings",
        source_url="https://example.test/hsy",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        licence_id="CC-BY-4.0",
        attribution="HSY",
        retrieved_at="2026-08-26T23:15:17+03:00",
        vintage="2026-08-26",
        coverage="Helsinki, Espoo, Vantaa, Kauniainen",
        checksum="sha256:fixture",
        processing_method="direct normalization",
        caveats=("fixture",),
        redistribution_decision="allowed",
        rationale="Open licence confirmed",
    )


def _helsinki_buildings_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="helsinki_buildings", name="Helsinki buildings", source_url="https://example.test/helsinki-buildings",
        licence_url="https://creativecommons.org/licenses/by/4.0/", licence_id="CC-BY-4.0", attribution="Helsingin kaupunki",
        retrieved_at="2026-08-30T12:00:00+03:00", vintage="2026-08-30", coverage="Helsinki", checksum="sha256:fixture",
        processing_method="VTJ-PRT join and Building Classification 2018 mapping", caveats=("fixture",), redistribution_decision="allowed", rationale="Open licence confirmed",
    )


def _helsinki_building_ownership_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="helsinki_building_ownership", name="Helsinki building ownership classification",
        source_url="https://example.test/helsinki-ownership", licence_url="https://example.test/licence",
        licence_id="derived", attribution="Fixture", retrieved_at="2026-09-22T12:00:00+03:00",
        vintage="2026-09-22", coverage="Helsinki", checksum="sha256:fixture",
        processing_method="fixture", caveats=("fixture",), redistribution_decision="derived_only",
        rationale="Only derived values are published.",
    )


def _active_plans_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="helsinki_active_plans", name="Helsinki active plans", source_url="https://example.test/plans",
        licence_url="https://creativecommons.org/licenses/by/4.0/", licence_id="CC-BY-4.0", attribution="Helsingin kaupunki",
        retrieved_at="2026-08-30T12:00:00+03:00", vintage="2026-08-30", coverage="Helsinki", checksum="sha256:fixture",
        processing_method="fixture", caveats=("fixture",), redistribution_decision="allowed", rationale="Open licence confirmed",
    )


def _paavo_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="paavo_income",
        name="Statistics Finland Paavo postal-area income",
        source_url="https://geo.stat.fi/geoserver/postialue/wfs",
        licence_url="https://stat.fi/fi/palvelut/tilastodatapalvelut/paikkatietoaineistot/postinumeroalueittainen-paikkatieto-paavo",
        licence_id="open",
        attribution="Tilastokeskus, Paavo",
        retrieved_at="2026-08-27T07:30:27+03:00",
        vintage="2026",
        coverage="Finland",
        checksum="sha256:fixture",
        processing_method="Offline postal-area assignment with suppressed values normalized to unknown",
        caveats=("Postal-area income is contextual, not a building-level measurement.",),
        redistribution_decision="allowed",
        rationale="Paavo is a free postal-area statistics dataset.",
    )


def _noise_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="helsinki_noise_2022",
        name="Helsinki traffic noise zones",
        source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        licence_id="CC-BY-4.0",
        attribution="Helsingin kaupunki",
        retrieved_at="2026-08-27T08:00:00+03:00",
        vintage="2022",
        coverage="Helsinki",
        checksum="sha256:fixture",
        processing_method="Offline maximum daytime noise-zone upper-bound aggregation",
        caveats=("Modeled zone upper bound, not a building-level maximum.",),
        redistribution_decision="allowed",
        rationale="The published dataset is CC BY 4.0.",
    )


def _night_noise_source_manifest() -> SourceManifest:
    return SourceManifest(
        source_id="helsinki_noise_night_2022",
        name="Helsinki nighttime traffic noise zones",
        source_url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        licence_id="CC-BY-4.0",
        attribution="Helsingin kaupunki",
        retrieved_at="2026-08-30T13:54:00+03:00",
        vintage="2022",
        coverage="Helsinki",
        checksum="sha256:fixture",
        processing_method="Offline maximum nighttime noise-zone upper-bound aggregation",
        caveats=("Modeled zone upper bound, not a building-level maximum.",),
        redistribution_decision="allowed",
        rationale="The published dataset is CC BY 4.0.",
    )


def _osm_source_manifest() -> SourceManifest:
    return SourceManifest("hsl_osm_extract", "Fixture OSM", "https://example.test/osm", "https://www.openstreetmap.org/copyright", "ODbL-1.0", "OpenStreetMap contributors", "2026-08-27T10:00:00+03:00", "2026-08-25", "Fixture", "sha256:fixture", "offline routing", ("fixture",), "derived_only", "fixture")
