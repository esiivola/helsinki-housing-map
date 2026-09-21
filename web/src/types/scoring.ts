export type LayerKind = "numeric" | "categorical";
export type ValueState = "known" | "partial" | "unknown" | "conflict";

export interface LayerDefinition {
  id: string;
  kind: LayerKind;
}

export interface LayerValue {
  state: ValueState;
  value: number | string | null;
  values?: readonly (number | string)[];
}

export interface LayerPreference {
  enabled: boolean;
  minimum?: number;
  maximum?: number;
  acceptedCategories: readonly string[];
  weight?: number;
  dealbreaker?: boolean;
  softPreference?: {
    // "lower_is_better"/"higher_is_better" are monotonic ramps: full score at
    // fullScoreAt, zero at zeroScoreAt, linear between. "range" is a full-score
    // band: full inside [fullScoreAt, zeroScoreAt] (the two hold the band's low
    // and high edges) and zero outside — e.g. "any building from the 1930s".
    direction: "lower_is_better" | "higher_is_better" | "range";
    fullScoreAt: number;
    zeroScoreAt: number;
  };
}

export interface Criterion {
  id: string;
  layerId: string;
  preference: Omit<LayerPreference, "weight" | "dealbreaker">;
}

export interface CriterionGroup {
  id: string;
  operator: "and" | "or";
  criteria: readonly Criterion[];
  weight?: number;
  dealbreaker?: boolean;
}

export interface GroupEvaluation {
  configured: boolean;
  status: "pass" | "fail" | "unknown" | "not_scored";
  score: number | null;
  hasMissingEvidence: boolean;
  criterionEvaluations: Readonly<Record<string, LayerEvaluation>>;
}

export interface LayerEvaluation {
  configured: boolean;
  status: "pass" | "fail" | "unknown" | "not_scored";
  score: number | null;
  hasMissingEvidence: boolean;
}

export type MissingDealbreakerPolicy = "pass" | "fail";
export type OverviewAggregation = "min" | "median" | "max";

export interface BuildingEvaluation {
  eligible: boolean;
  score: number | null;
  failedDealbreakers: readonly string[];
  missingLayers: readonly string[];
  layers: Readonly<Record<string, LayerEvaluation>>;
}

export interface AppPreferences {
  version: 2;
  groups: readonly CriterionGroup[];
  selectedVisualization: string;
  missingDealbreakerPolicy: MissingDealbreakerPolicy;
  overviewAggregation?: OverviewAggregation;
  groceryStoreGroups?: readonly string[];
  educationServiceGroups?: readonly string[];
  healthServiceGroups?: readonly string[];
}

export interface AppManifest {
  schemaVersion: string;
  attributePartitions: readonly string[];
  geometryPartitions: readonly string[];
  layerCatalogue: string;
  sourceManifest: string;
  evidence: string;
  layerDistributions?: string;
  scoreHistogramInputs?: string;
  spatialPartitions?: {
    buildingTier: {
      minZoom: number;
      tileZoom: number;
      geometryPathTemplate: string;
      coreAttributePathTemplate?: string;
      layerAttributePathTemplate?: string;
      layerTileKeys?: Readonly<Record<string, readonly string[]>>;
      bufferTiles: number;
      tileKeys: readonly string[];
    };
    overviewTiers: readonly {
      minZoom: number;
      maxZoom: number;
      tileZoom: number;
      geometryPathTemplate: string;
      layerPathTemplate: string;
      tileKeys: readonly string[];
    }[];
  };
}
