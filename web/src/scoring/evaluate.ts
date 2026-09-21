import type {
  BuildingEvaluation,
  LayerDefinition,
  LayerEvaluation,
  CriterionGroup,
  GroupEvaluation,
  LayerPreference,
  LayerValue,
  MissingDealbreakerPolicy,
} from "../types/scoring";

export function evaluateLayer(
  value: LayerValue,
  definition: LayerDefinition,
  preference: LayerPreference,
): LayerEvaluation {
  const configured = preference.enabled && isConfigured(definition, preference);
  if (!configured) {
    return { configured: false, status: "not_scored", score: null, hasMissingEvidence: false };
  }
  if (value.state === "unknown") {
    return { configured: true, status: "unknown", score: null, hasMissingEvidence: true };
  }

  const matches = values(value).map((candidate) =>
    definition.kind === "numeric"
      ? numericMatch(candidate, preference)
      : categoryMatch(candidate, preference),
  );
  if (!matches.length || matches.some((match) => match === null)) {
    return { configured: true, status: "unknown", score: null, hasMissingEvidence: true };
  }
  if (definition.kind === "numeric" && preference.softPreference) {
    const scores = values(value).map((candidate) => linearPreferenceScore(candidate, preference.softPreference!));
    if (scores.some((score) => score === null)) return { configured: true, status: "unknown", score: null, hasMissingEvidence: true };
    const score = Math.max(...scores as number[]);
    return { configured: true, status: score > 0 ? "pass" : "fail", score, hasMissingEvidence: value.state !== "known" };
  }
  const score = matches.includes(true) ? 1 : 0;
  return {
    configured: true,
    status: score ? "pass" : "fail",
    score,
    hasMissingEvidence: value.state !== "known",
  };
}

export function evaluateCriterionGroup(
  values: Readonly<Record<string, LayerValue>>,
  definitions: readonly LayerDefinition[],
  group: CriterionGroup,
): GroupEvaluation {
  const byLayer = new Map(definitions.map((definition) => [definition.id, definition]));
  const criterionEvaluations: Record<string, LayerEvaluation> = {};
  for (const criterion of group.criteria) {
    const definition = byLayer.get(criterion.layerId);
    if (!definition) continue;
    criterionEvaluations[criterion.id] = evaluateLayer(values[criterion.layerId] ?? { state: "unknown", value: null }, definition, { ...criterion.preference, enabled: true });
  }
  const evaluations = Object.values(criterionEvaluations).filter((evaluation) => evaluation.configured);
  if (!evaluations.length) return { configured: false, status: "not_scored", score: null, hasMissingEvidence: false, criterionEvaluations };
  const hasMissingEvidence = evaluations.some((evaluation) => evaluation.hasMissingEvidence);
  if (group.operator === "and") {
    if (evaluations.some((evaluation) => evaluation.status === "fail")) return { configured: true, status: "fail", score: 0, hasMissingEvidence, criterionEvaluations };
    if (evaluations.some((evaluation) => evaluation.status === "unknown")) return { configured: true, status: "unknown", score: null, hasMissingEvidence, criterionEvaluations };
    return { configured: true, status: "pass", score: Math.min(...evaluations.map((evaluation) => evaluation.score ?? 0)), hasMissingEvidence, criterionEvaluations };
  }
  if (evaluations.some((evaluation) => evaluation.status === "pass")) return { configured: true, status: "pass", score: Math.max(...evaluations.map((evaluation) => evaluation.score ?? 0)), hasMissingEvidence, criterionEvaluations };
  if (evaluations.every((evaluation) => evaluation.status === "fail")) return { configured: true, status: "fail", score: 0, hasMissingEvidence, criterionEvaluations };
  return { configured: true, status: "unknown", score: null, hasMissingEvidence, criterionEvaluations };
}

export function evaluateBuildingGroups(
  values: Readonly<Record<string, LayerValue>>,
  definitions: readonly LayerDefinition[],
  groups: readonly CriterionGroup[],
  missingDealbreakerPolicy: MissingDealbreakerPolicy,
): BuildingEvaluation {
  const layers: Record<string, LayerEvaluation> = {};
  const failedDealbreakers: string[] = [];
  const missingLayers: string[] = [];
  let numerator = 0;
  let denominator = 0;
  for (const group of groups) {
    const evaluation = evaluateCriterionGroup(values, definitions, group);
    for (const [criterionId, criterionEvaluation] of Object.entries(evaluation.criterionEvaluations)) layers[criterionId] = criterionEvaluation;
    if (!evaluation.configured) continue;
    if (evaluation.hasMissingEvidence) missingLayers.push(group.id);
    // A dealbreaker (must-have) rejects the building when it fails, but its
    // score still counts toward the suitability average like any other criterion.
    if (group.dealbreaker && (evaluation.status === "fail" || (evaluation.hasMissingEvidence && missingDealbreakerPolicy === "fail"))) {
      failedDealbreakers.push(group.id);
    }
    const weight = group.weight ?? 1;
    if (!Number.isFinite(weight) || weight < 0) throw new RangeError(`Invalid weight for ${group.id}`);
    if (evaluation.score !== null && weight > 0) {
      numerator += evaluation.score * weight;
      denominator += weight;
    }
  }
  const eligible = failedDealbreakers.length === 0;
  return { eligible, score: !eligible ? null : denominator > 0 ? numerator / denominator : null, failedDealbreakers, missingLayers, layers };
}

export function evaluateBuilding(
  values: Readonly<Record<string, LayerValue>>,
  definitions: readonly LayerDefinition[],
  preferences: Readonly<Record<string, LayerPreference>>,
  missingDealbreakerPolicy: MissingDealbreakerPolicy,
): BuildingEvaluation {
  const layers: Record<string, LayerEvaluation> = {};
  const failedDealbreakers: string[] = [];
  const missingLayers: string[] = [];
  let numerator = 0;
  let denominator = 0;
  let configuredDealbreakersOnly = true;

  for (const definition of definitions) {
    const preference = preferences[definition.id];
    const value = values[definition.id] ?? { state: "unknown", value: null };
    if (!preference) continue;
    const evaluation = evaluateLayer(value, definition, preference);
    layers[definition.id] = evaluation;
    if (!evaluation.configured) continue;
    if (evaluation.hasMissingEvidence) missingLayers.push(definition.id);

    if (preference.dealbreaker) {
      if (
        evaluation.status === "fail" ||
        (evaluation.hasMissingEvidence && missingDealbreakerPolicy === "fail")
      ) {
        failedDealbreakers.push(definition.id);
      }
      continue;
    }

    configuredDealbreakersOnly = false;

    const weight = preference.weight ?? 1;
    if (!Number.isFinite(weight) || weight < 0) {
      throw new RangeError(`Invalid weight for ${definition.id}`);
    }
    if (evaluation.score !== null && weight > 0) {
      numerator += evaluation.score * weight;
      denominator += weight;
    }
  }

  const eligible = failedDealbreakers.length === 0;
  return {
    eligible,
    score: !eligible ? null : denominator > 0 ? numerator / denominator : configuredDealbreakersOnly && Object.values(layers).some((evaluation) => evaluation.configured) && missingLayers.length === 0 ? 1 : null,
    failedDealbreakers,
    missingLayers,
    layers,
  };
}

function isConfigured(definition: LayerDefinition, preference: LayerPreference): boolean {
  if (preference.softPreference) return true;
  return definition.kind === "numeric"
    ? preference.minimum !== undefined || preference.maximum !== undefined
    : preference.acceptedCategories.length > 0;
}

export function linearPreferenceScore(
  value: number | string,
  preference: NonNullable<LayerPreference["softPreference"]>,
): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const { direction, fullScoreAt, zeroScoreAt } = preference;
  if (!Number.isFinite(fullScoreAt) || !Number.isFinite(zeroScoreAt) ||
    direction === "lower_is_better" && fullScoreAt >= zeroScoreAt ||
    direction === "higher_is_better" && fullScoreAt <= zeroScoreAt ||
    direction === "range" && fullScoreAt === zeroScoreAt) throw new RangeError("Invalid linear preference endpoints");
  if (direction === "range") {
    const low = Math.min(fullScoreAt, zeroScoreAt);
    const high = Math.max(fullScoreAt, zeroScoreAt);
    return value >= low && value <= high ? 1 : 0;
  }
  if (direction === "lower_is_better") {
    if (value <= fullScoreAt) return 1;
    if (value >= zeroScoreAt) return 0;
    return (zeroScoreAt - value) / (zeroScoreAt - fullScoreAt);
  }
  if (value >= fullScoreAt) return 1;
  if (value <= zeroScoreAt) return 0;
  return (value - zeroScoreAt) / (fullScoreAt - zeroScoreAt);
}

function values(value: LayerValue): readonly (number | string)[] {
  if (value.values?.length) {
    return value.values;
  }
  return value.value === null ? [] : [value.value];
}

function numericMatch(value: number | string, preference: LayerPreference): boolean | null {
  if (typeof value !== "number") {
    return null;
  }
  return (
    (preference.minimum === undefined || value >= preference.minimum) &&
    (preference.maximum === undefined || value <= preference.maximum)
  );
}

function categoryMatch(value: number | string, preference: LayerPreference): boolean | null {
  return typeof value === "string" ? preference.acceptedCategories.includes(value) : null;
}
