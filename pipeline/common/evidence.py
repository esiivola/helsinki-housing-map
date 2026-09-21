from __future__ import annotations

from collections.abc import Iterable

from pipeline.models import (
    BuildingValue,
    Confidence,
    EvidenceRecord,
    LandClaim,
    ValueKind,
    ValueMethod,
    ValueState,
)


CLAIMS_BY_LAYER = {
    "plot_tenure": {LandClaim.OWNED, LandClaim.LEASED},
    "land_owner_class": {LandClaim.CITY, LandClaim.NON_CITY},
}


def resolve_land_evidence(
    records: Iterable[EvidenceRecord], layer_id: str
) -> BuildingValue:
    relevant = [record for record in records if record.claim in CLAIMS_BY_LAYER[layer_id]]
    if not relevant:
        return BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None)

    values = {record.claim for record in relevant}
    state = ValueState.KNOWN if len(values) == 1 else ValueState.CONFLICT
    value = next(iter(values)) if state is ValueState.KNOWN else "mixed"
    return BuildingValue(
        state=state,
        kind=ValueKind.SCALAR,
        value=value,
        coverage=1,
        evidence_ids=tuple(record.evidence_id for record in relevant),
        method=_least_specific_method(relevant),
        confidence=_lowest_confidence(relevant),
    )


def _least_specific_method(records: list[EvidenceRecord]) -> ValueMethod:
    order = [ValueMethod.DIRECT, ValueMethod.AGGREGATED, ValueMethod.DERIVED, ValueMethod.INFERRED]
    return max((record.method for record in records), key=order.index)


def _lowest_confidence(records: list[EvidenceRecord]) -> Confidence:
    order = [Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]
    return min((record.confidence for record in records), key=order.index)
