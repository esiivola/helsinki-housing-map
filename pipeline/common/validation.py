from __future__ import annotations

from collections.abc import Mapping

from pipeline.models import RedistributionDecision, SourceManifest


PUBLIC_PERSON_FIELDS = frozenset({"owner_name", "tenant_name", "leaseholder_name"})


def validate_source_manifest(manifest: SourceManifest) -> None:
    required = (
        manifest.source_id,
        manifest.name,
        manifest.source_url,
        manifest.licence_url,
        manifest.licence_id,
        manifest.attribution,
        manifest.retrieved_at,
        manifest.vintage,
        manifest.coverage,
        manifest.checksum,
        manifest.processing_method,
        manifest.rationale,
    )
    if not all(required):
        raise ValueError("source manifest has missing required provenance")
    if manifest.redistribution_decision is RedistributionDecision.EXCLUDED:
        raise ValueError(f"source {manifest.source_id} is excluded from public release")


def validate_public_evidence(record: Mapping[str, object]) -> None:
    forbidden = PUBLIC_PERSON_FIELDS.intersection(record)
    if forbidden:
        raise ValueError(f"public evidence contains forbidden field: {sorted(forbidden)[0]}")
