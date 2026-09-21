import { describe, expect, it } from "vitest";

import { buildingLayerValues, buildingYears } from "./attributes";

describe("buildingYears", () => {
  it("keeps source-backed multi-value years and leaves unknown records absent", () => {
    const years = buildingYears({
      building_values: [
        { building_id: "known", layer_id: "building_year", state: "known", value: null, values: [1940, 1970] },
        { building_id: "unknown", layer_id: "building_year", state: "unknown", value: null, values: [] },
      ],
    });

    expect(years.get("known")).toEqual([1940, 1970]);
    expect(years.has("unknown")).toBe(false);
  });
});

describe("buildingLayerValues", () => {
  it("keeps every exported layer value, including explicit unknowns", () => {
    const values = buildingLayerValues({
      building_values: [
        { building_id: "a", layer_id: "building_year", state: "known", value: null, values: [1970] },
        { building_id: "a", layer_id: "income_median_eur", state: "unknown", value: null, values: [] },
      ],
    });

    expect(values.get("a")).toEqual({
      building_year: { state: "known", value: null, values: [1970], distribution: {}, coverage: 0, evidenceIds: [], method: null, confidence: null },
      income_median_eur: { state: "unknown", value: null, values: [], distribution: {}, coverage: 0, evidenceIds: [], method: null, confidence: null },
    });
  });

  it("keeps coverage and provenance needed by the inspector", () => {
    const values = buildingLayerValues({
      building_values: [{
        building_id: "a", layer_id: "noise_day_upper_db", state: "partial", value: 55, values: [],
        distribution: {}, coverage: 0.7, evidence_ids: ["noise"], method: "aggregated", confidence: "medium",
      }],
    });

    expect(values.get("a")?.noise_day_upper_db).toMatchObject({ coverage: 0.7, evidenceIds: ["noise"], method: "aggregated", confidence: "medium" });
  });
});
