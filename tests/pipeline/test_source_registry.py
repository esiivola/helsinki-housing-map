from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.models import RedistributionDecision
from pipeline.source_registry import load_source_registry


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "source_registry.yaml"
PROJECT_CONFIG_PATH = Path(__file__).parents[2] / "pipeline" / "config" / "sources.yaml"


def test_registry_loads_source_manifests_without_admitting_excluded_sources() -> None:
    registry = load_source_registry(FIXTURE_PATH)

    assert registry["fixture_allowed"].licence_id == "CC-BY-4.0"
    assert registry["fixture_excluded"].redistribution_decision is RedistributionDecision.EXCLUDED


def test_registry_rejects_duplicate_source_identifiers(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(FIXTURE_PATH.read_text().replace("fixture_excluded", "fixture_allowed"))

    with pytest.raises(ValueError, match="duplicate source_id"):
        load_source_registry(duplicate)


def test_registry_requires_a_source_list(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("source_id: missing-list\n")

    with pytest.raises(ValueError, match="sources list"):
        load_source_registry(invalid)


def test_project_registry_marks_the_restricted_owner_map_excluded() -> None:
    registry = load_source_registry(PROJECT_CONFIG_PATH)

    assert registry["hsy_buildings"].redistribution_decision is RedistributionDecision.ALLOWED
    assert (
        registry["helsinki_owner_map_excluded"].redistribution_decision
        is RedistributionDecision.EXCLUDED
    )
