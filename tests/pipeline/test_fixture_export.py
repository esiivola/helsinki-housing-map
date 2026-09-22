from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from pipeline.build import build_fixture_release


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "release_fixture.json"


def test_fixture_build_exports_deterministic_static_artifacts(tmp_path: Path) -> None:
    first = build_fixture_release(FIXTURE_PATH, tmp_path / "first")
    second = build_fixture_release(FIXTURE_PATH, tmp_path / "second")

    assert first == second
    assert json.loads((tmp_path / "first" / "manifest.json").read_text()) == {
        "attribute_partitions": ["attributes/Helsinki.json.gz"],
        "audit_report": "audit.json",
        "evidence": "evidence.json",
        "geometry_partitions": ["geometry/Helsinki.geojson.gz"],
        "layer_distributions": "layer-distributions.json",
        "layer_catalogue": "layers.json",
        "score_histogram_inputs": "score-histogram-inputs.json.gz",
        "schema_version": "1.0.0",
        "source_manifest": "sources.json",
    }
    assert json.loads(gzip.decompress((tmp_path / "first" / "attributes" / "Helsinki.json.gz").read_bytes()))[
        "building_values"
    ][0]["value"] == "city"
    assert json.loads(gzip.decompress((tmp_path / "first" / "geometry" / "Helsinki.geojson.gz").read_bytes()))["features"][0]["properties"] == {"building_id": "fixture-building-1"}
    assert json.loads((tmp_path / "first" / "audit.json").read_text()) == {
        "building_count_by_municipality": {"Helsinki": 4},
        "evidence_count": 2,
        "layer_value_state_counts": {"known": 3, "partial": 1, "unknown": 1},
        "layer_value_state_counts_by_municipality": {"Helsinki": {"known": 3, "partial": 1, "unknown": 1}},
        "layer_value_state_counts_by_layer": {"land_owner_class": {"known": 2}, "noise_day_upper_db": {"known": 1, "partial": 1, "unknown": 1}},
        "layer_value_state_counts_by_municipality_and_layer": {"Helsinki": {"land_owner_class": {"known": 2}, "noise_day_upper_db": {"known": 1, "partial": 1, "unknown": 1}}},
    }


def test_fixture_build_rejects_orphan_evidence_reference(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    fixture["layer_values"][0]["evidence_ids"] = ["missing-evidence"]
    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text(json.dumps(fixture))

    with pytest.raises(ValueError, match="orphan evidence"):
        build_fixture_release(invalid_fixture, tmp_path / "output")
