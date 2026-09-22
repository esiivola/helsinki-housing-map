from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.common.evidence import resolve_land_evidence
from pipeline.common.validation import validate_public_evidence, validate_source_manifest
from pipeline.models import (
    EvidenceRecord,
    LandClaim,
    RedistributionDecision,
    SourceManifest,
    ValueState,
)


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "source_manifests.json"


def source_manifests() -> list[SourceManifest]:
    return [SourceManifest(**item) for item in json.loads(FIXTURE_PATH.read_text())]


def evidence(claim: LandClaim, evidence_id: str = "evidence-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_id="espoo_city_land",
        source_url="https://example.test/evidence",
        retrieved_at="2026-08-26T10:00:00+00:00",
        vintage="2026-08-19",
        claim=claim,
        method="direct",
        confidence="high",
        caveat_ids=(),
    )


def test_source_manifest_requires_publication_provenance() -> None:
    manifest = source_manifests()[0]

    validate_source_manifest(manifest)

    assert manifest.redistribution_decision is RedistributionDecision.ALLOWED
    assert manifest.schema_version == "2026-08"


def test_excluded_source_cannot_enter_a_public_release() -> None:
    excluded = source_manifests()[1]

    with pytest.raises(ValueError, match="excluded"):
        validate_source_manifest(excluded)


def test_absent_land_evidence_remains_unknown() -> None:
    result = resolve_land_evidence([], "land_owner_class")

    assert result.state is ValueState.UNKNOWN
    assert result.value is None


def test_unrelated_land_evidence_does_not_change_owner_class() -> None:
    records = [evidence(LandClaim.CITY), evidence(LandClaim.LEASED, "evidence-2")]

    assert resolve_land_evidence(records, "land_owner_class").value == "city"


def test_conflicting_positive_evidence_is_not_resolved_by_input_order() -> None:
    records = [evidence(LandClaim.CITY), evidence(LandClaim.NON_CITY, "evidence-2")]

    result = resolve_land_evidence(records, "land_owner_class")

    assert result.state is ValueState.CONFLICT
    assert result.value == "mixed"
    assert result.evidence_ids == ("evidence-1", "evidence-2")


def test_public_evidence_rejects_natural_person_fields() -> None:
    with pytest.raises(ValueError, match="owner_name"):
        validate_public_evidence({"claim": "city", "owner_name": "Example Person"})


def test_evidence_accepts_a_non_land_factual_claim() -> None:
    record = evidence("construction_year:1970")

    assert record.claim == "construction_year:1970"
