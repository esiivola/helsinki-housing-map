from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ValueState(StrEnum):
    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class ValueKind(StrEnum):
    SCALAR = "scalar"
    MULTI = "multi"
    DISTRIBUTION = "distribution"


class ValueMethod(StrEnum):
    DIRECT = "direct"
    AGGREGATED = "aggregated"
    DERIVED = "derived"
    INFERRED = "inferred"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RedistributionDecision(StrEnum):
    ALLOWED = "allowed"
    DERIVED_ONLY = "derived_only"
    EXCLUDED = "excluded"


class LandClaim(StrEnum):
    OWNED = "owned"
    LEASED = "leased"
    CITY = "city"
    NON_CITY = "non_city"


class LayerKind(StrEnum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


@dataclass(frozen=True)
class BuildingValue:
    state: ValueState
    kind: ValueKind
    value: float | str | None
    values: tuple[float | str, ...] = ()
    distribution: dict[str, float] = field(default_factory=dict)
    coverage: float = 0
    evidence_ids: tuple[str, ...] = ()
    method: ValueMethod = ValueMethod.AGGREGATED
    confidence: Confidence = Confidence.MEDIUM


@dataclass(frozen=True)
class SourceManifest:
    source_id: str
    name: str
    source_url: str
    licence_url: str
    licence_id: str
    attribution: str
    retrieved_at: str
    vintage: str
    coverage: str
    checksum: str
    processing_method: str
    caveats: tuple[str, ...]
    redistribution_decision: RedistributionDecision
    rationale: str
    schema_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "caveats", tuple(self.caveats))
        object.__setattr__(
            self,
            "redistribution_decision",
            RedistributionDecision(self.redistribution_decision),
        )


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_id: str
    source_url: str
    retrieved_at: str
    vintage: str
    claim: str
    method: ValueMethod
    confidence: Confidence
    caveat_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.claim, str) or not self.claim:
            raise ValueError("evidence claim must be a non-empty string")
        object.__setattr__(self, "method", ValueMethod(self.method))
        object.__setattr__(self, "confidence", Confidence(self.confidence))
        object.__setattr__(self, "caveat_ids", tuple(self.caveat_ids))


@dataclass(frozen=True)
class BuildingRecord:
    building_id: str
    source_id: str
    municipality: str
    completed: bool | None
    residential_use: bool | None
    house_type: str | None
    construction_years: tuple[int, ...]

    @property
    def is_scored(self) -> bool:
        return self.completed is True and (
            self.residential_use is True or self.house_type is not None
        )


@dataclass(frozen=True)
class LayerValueRecord:
    building_id: str
    layer_id: str
    value: BuildingValue


@dataclass(frozen=True)
class ReleaseArtifact:
    schema_version: str
    sources: tuple[SourceManifest, ...]
    evidence: tuple[EvidenceRecord, ...]
    buildings: tuple[BuildingRecord, ...]
    layer_values: tuple[LayerValueRecord, ...]


@dataclass(frozen=True)
class StaticBundle:
    manifest: dict[str, object]


@dataclass(frozen=True)
class LayerDefinition:
    layer_id: str
    finnish_label: str
    description: str
    kind: LayerKind
    unit: str | None
    formatter: str
    allowed_categories: tuple[str, ...]
    allowed_min: float | None
    allowed_max: float | None
    default_enabled: bool
    default_weight: float
    visualization_scale: str
    visualization_range: tuple[float, float] | None
    methodology: str
    caveat_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", LayerKind(self.kind))
        object.__setattr__(self, "allowed_categories", tuple(self.allowed_categories))
        object.__setattr__(self, "caveat_ids", tuple(self.caveat_ids))
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        if self.visualization_range is not None:
            object.__setattr__(self, "visualization_range", tuple(self.visualization_range))


@dataclass(frozen=True)
class RawArtifact:
    source_id: str
    source_url: str
    path: Path
    checksum: str
