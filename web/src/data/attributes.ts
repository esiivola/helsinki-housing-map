export interface AttributePartition {
  building_values: Array<{
    building_id: string;
    layer_id: string;
    state: "known" | "partial" | "unknown" | "conflict";
    value: number | string | null;
    values: Array<number | string>;
    distribution?: Record<string, number>;
    coverage?: number;
    evidence_ids?: string[];
    method?: "direct" | "aggregated" | "derived" | "inferred";
    confidence?: "high" | "medium" | "low";
  }>;
}

export function buildingYears(partition: AttributePartition): ReadonlyMap<string, readonly number[]> {
  return new Map(
    partition.building_values
      .filter((value) => value.layer_id === "building_year" && value.state === "known")
      .map((value) => [value.building_id, value.values.filter((year): year is number => typeof year === "number")]),
  );
}

export interface BuildingLayerValue {
  state: "known" | "partial" | "unknown" | "conflict";
  value: number | string | null;
  values: readonly (number | string)[];
  distribution: Readonly<Record<string, number>>;
  coverage: number;
  evidenceIds: readonly string[];
  method: "direct" | "aggregated" | "derived" | "inferred" | null;
  confidence: "high" | "medium" | "low" | null;
}

export function buildingLayerValues(partition: AttributePartition): ReadonlyMap<string, Record<string, BuildingLayerValue>> {
  const byBuilding = new Map<string, Record<string, BuildingLayerValue>>();
  for (const value of partition.building_values) {
    const layers = byBuilding.get(value.building_id) ?? {};
    layers[value.layer_id] = {
      state: value.state,
      value: value.value,
      values: value.values,
      distribution: value.distribution ?? {},
      coverage: value.coverage ?? 0,
      evidenceIds: value.evidence_ids ?? [],
      method: value.method ?? null,
      confidence: value.confidence ?? null,
    };
    byBuilding.set(value.building_id, layers);
  }
  return byBuilding;
}
