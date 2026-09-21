from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.layer_registry import load_layer_registry, validate_layer_sources
from pipeline.models import LayerKind, SourceManifest
from pipeline.source_registry import load_source_registry


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "layer_registry.yaml"
PROJECT_LAYER_PATH = Path(__file__).parents[2] / "pipeline" / "config" / "layers.yaml"


def test_registry_loads_finnish_layer_metadata_and_technical_identifiers() -> None:
    registry = load_layer_registry(FIXTURE_PATH)

    assert registry["building_year"].finnish_label == "Rakennusvuosi"
    assert registry["building_year"].kind is LayerKind.NUMERIC
    assert registry["building_year"].visualization_range == (1600, 2100)
    assert registry["plot_tenure"].allowed_categories == ("owned", "leased", "mixed")
    assert registry["plot_tenure"].source_ids == ("espoo_city_land",)


def test_registry_rejects_unknown_as_an_accepted_category(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(FIXTURE_PATH.read_text().replace("      - owned", "      - unknown"))

    with pytest.raises(ValueError, match="unknown cannot be accepted"):
        load_layer_registry(invalid)


def test_registry_rejects_numeric_categories(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(FIXTURE_PATH.read_text().replace("    allowed_categories: []", "    allowed_categories: [owned]"))

    with pytest.raises(ValueError, match="numeric layer cannot define categories"):
        load_layer_registry(invalid)


def test_registry_rejects_missing_numeric_visualization_range(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(FIXTURE_PATH.read_text().replace("    visualization_range: [1600, 2100]", "    visualization_range: null"))

    with pytest.raises(ValueError, match="numeric layer must define an ascending visualization range"):
        load_layer_registry(invalid)


def test_project_layer_registry_uses_finnish_labels_and_known_categories() -> None:
    registry = load_layer_registry(PROJECT_LAYER_PATH)

    assert registry["house_type"].finnish_label == "Talotyyppi"
    assert registry["land_owner_class"].finnish_label == "Maanomistus"
    assert registry["income_median_eur"].finnish_label == "Alueen mediaanitulot"
    assert registry["noise_day_upper_db"].finnish_label == "Päivämelun yläraja"
    assert registry["noise_night_upper_db"].finnish_label == "Yömelun yläraja"
    assert registry["heating_energy_source"].allowed_categories[-1] == "other"
    assert registry["plot_tenure"].allowed_categories == ("owned", "leased", "mixed")
    assert set(registry) == {
        "building_year",
        "house_type",
        "elevator",
        "heating_method",
        "heating_energy_source",
        "storey_count",
        "dwelling_count",
        "plot_tenure",
        "land_owner_class",
        "noise_day_upper_db",
        "noise_night_upper_db",
        "forest_walk_m",
        "shore_walk_m",
        "daycare_walk_m",
        "school_walk_m",
        "healthcare_walk_m",
        "library_walk_m",
        "grocery_store_prisma_walk_m", "grocery_store_k_citymarket_walk_m", "grocery_store_lidl_walk_m", "grocery_store_s_market_walk_m", "grocery_store_k_supermarket_walk_m", "grocery_store_sale_walk_m", "grocery_store_k_market_walk_m", "grocery_store_alepa_walk_m", "grocery_store_other_supermarket_walk_m", "grocery_store_other_grocery_walk_m",
        "income_median_eur",
    }


def test_project_layers_only_reference_registered_sources() -> None:
    layers = load_layer_registry(PROJECT_LAYER_PATH)
    sources = load_source_registry(Path(__file__).parents[2] / "pipeline" / "config" / "sources.yaml")

    validate_layer_sources(layers, sources)


def test_registry_rejects_an_unregistered_layer_source() -> None:
    layers = load_layer_registry(FIXTURE_PATH)
    sources = {
        "espoo_city_land": SourceManifest(
            source_id="espoo_city_land",
            name="Fixture",
            source_url="https://example.test/source",
            licence_url="https://example.test/licence",
            licence_id="fixture",
            attribution="Fixture",
            retrieved_at="2026-08-26T10:00:00+00:00",
            vintage="2026-08-26",
            coverage="Fixture",
            checksum="sha256:fixture",
            processing_method="fixture",
            caveats=(),
            redistribution_decision="allowed",
            rationale="fixture",
        )
    }

    with pytest.raises(ValueError, match="layer building_year references unknown source: hsy_buildings"):
        validate_layer_sources(layers, sources)
