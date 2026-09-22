import { describe, expect, it } from "vitest";

import { evaluateBuilding, evaluateBuildingGroups, evaluateCriterionGroup, evaluateLayer, linearPreferenceScore } from "./evaluate";

const numeric = { id: "building_year", kind: "numeric" } as const;
const categorical = { id: "land_owner_class", kind: "categorical" } as const;

describe("evaluateLayer", () => {
  it("scores a lower-is-better preference linearly between its visible endpoints", () => {
    const preference = { direction: "lower_is_better" as const, fullScoreAt: 25, zeroScoreAt: 40 };
    expect(linearPreferenceScore(20, preference)).toBe(1);
    expect(linearPreferenceScore(32.5, preference)).toBe(0.5);
    expect(linearPreferenceScore(45, preference)).toBe(0);
  });

  it("supports higher-is-better preferences and rejects invalid endpoint order", () => {
    expect(linearPreferenceScore(800, { direction: "higher_is_better", fullScoreAt: 800, zeroScoreAt: 300 })).toBe(1);
    expect(linearPreferenceScore(550, { direction: "higher_is_better", fullScoreAt: 800, zeroScoreAt: 300 })).toBe(0.5);
    expect(() => linearPreferenceScore(1, { direction: "lower_is_better", fullScoreAt: 40, zeroScoreAt: 25 })).toThrow("Invalid linear preference endpoints");
  });

  it("scores a range band as full inside the interval and zero outside", () => {
    const band = { direction: "range" as const, fullScoreAt: 1930, zeroScoreAt: 1939 };
    expect(linearPreferenceScore(1930, band)).toBe(1);
    expect(linearPreferenceScore(1935, band)).toBe(1);
    expect(linearPreferenceScore(1939, band)).toBe(1);
    expect(linearPreferenceScore(1929, band)).toBe(0);
    expect(linearPreferenceScore(1980, band)).toBe(0);
    expect(() => linearPreferenceScore(1930, { direction: "range", fullScoreAt: 1930, zeroScoreAt: 1930 })).toThrow("Invalid linear preference endpoints");
  });

  it("uses inclusive numeric bounds and supports open-ended ranges", () => {
    expect(
      evaluateLayer(
        { state: "known", value: 1970 },
        numeric,
        { enabled: true, minimum: 1970, acceptedCategories: [] },
      ),
    ).toMatchObject({ configured: true, status: "pass", score: 1 });
    expect(
      evaluateLayer(
        { state: "known", value: 1969 },
        numeric,
        { enabled: true, maximum: 1969, acceptedCategories: [] },
      ),
    ).toMatchObject({ configured: true, status: "pass", score: 1 });
  });

  it("uses any-match semantics for multi-value facts", () => {
    expect(
      evaluateLayer(
        { state: "known", value: null, values: [1940, 1970] },
        numeric,
        { enabled: true, minimum: 1930, maximum: 1950, acceptedCategories: [] },
      ),
    ).toMatchObject({ status: "pass", score: 1 });
    expect(
      evaluateLayer(
        { state: "known", value: null, values: [1940, 1970] },
        numeric,
        { enabled: true, minimum: 1950, maximum: 1960, acceptedCategories: [] },
      ),
    ).toMatchObject({ status: "fail", score: 0 });
  });

  it("accepts an owner class only when the category is explicitly selected", () => {
    expect(
      evaluateLayer(
        { state: "known", value: "non_city" },
        categorical,
        { enabled: true, acceptedCategories: ["non_city"] },
      ),
    ).toMatchObject({ status: "pass", score: 1 });
    expect(
      evaluateLayer(
        { state: "known", value: "non_city" },
        categorical,
        { enabled: true, acceptedCategories: ["city"] },
      ),
    ).toMatchObject({ status: "fail", score: 0 });
  });

  it("omits unconfigured or unknown layers from scoring", () => {
    expect(
      evaluateLayer(
        { state: "known", value: 1970 },
        numeric,
        { enabled: true, acceptedCategories: [] },
      ),
    ).toMatchObject({ configured: false, status: "not_scored", score: null });
    expect(
      evaluateLayer(
        { state: "unknown", value: null },
        numeric,
        { enabled: true, minimum: 1960, acceptedCategories: [] },
      ),
    ).toMatchObject({ status: "unknown", score: null, hasMissingEvidence: true });
  });
});

describe("evaluateBuilding", () => {
  const definitions = [
    { id: "building_year", kind: "numeric" },
    { id: "noise_day_db", kind: "numeric" },
  ] as const;

  it("calculates the weighted mean without dealbreakers", () => {
    const result = evaluateBuilding(
      {
        building_year: { state: "known", value: 1970 },
        noise_day_db: { state: "known", value: 60 },
      },
      definitions,
      {
        building_year: { enabled: true, minimum: 1960, acceptedCategories: [], weight: 2 },
        noise_day_db: { enabled: true, maximum: 55, acceptedCategories: [], weight: 1 },
      },
      "pass",
    );

    expect(result).toMatchObject({ eligible: true, score: 2 / 3 });
  });

  it("excludes a failed dealbreaker from the weighted average", () => {
    const result = evaluateBuilding(
      {
        building_year: { state: "known", value: 1970 },
        noise_day_db: { state: "known", value: 60 },
      },
      definitions,
      {
        building_year: { enabled: true, minimum: 1960, acceptedCategories: [], weight: 1 },
        noise_day_db: {
          enabled: true,
          maximum: 55,
          acceptedCategories: [],
          weight: 99,
          dealbreaker: true,
        },
      },
      "pass",
    );

    expect(result).toMatchObject({ eligible: false, score: null, failedDealbreakers: ["noise_day_db"] });
  });

  it("scores buildings with only passing dealbreakers as fully suitable", () => {
    const result = evaluateBuilding(
      {
        building_year: { state: "known", value: 1970 },
        noise_day_db: { state: "known", value: 50 },
      },
      definitions,
      {
        building_year: { enabled: true, minimum: 1960, acceptedCategories: [], dealbreaker: true },
        noise_day_db: { enabled: true, maximum: 55, acceptedCategories: [], dealbreaker: true },
      },
      "pass",
    );

    expect(result).toMatchObject({ eligible: true, score: 1 });
  });

  it("applies the global missing-dealbreaker policy to partial evidence", () => {
    const values = {
      building_year: { state: "known" as const, value: 1970 },
      noise_day_db: { state: "partial" as const, value: 50 },
    };
    const preferences = {
      building_year: { enabled: true, minimum: 1960, acceptedCategories: [] },
      noise_day_db: { enabled: true, maximum: 55, acceptedCategories: [], dealbreaker: true },
    };

    expect(evaluateBuilding(values, definitions, preferences, "pass")).toMatchObject({
      eligible: true,
      missingLayers: ["noise_day_db"],
    });
    expect(evaluateBuilding(values, definitions, preferences, "fail")).toMatchObject({
      eligible: false,
      failedDealbreakers: ["noise_day_db"],
    });
  });

  it("returns no score when no known weighted layer participates", () => {
    const result = evaluateBuilding(
      {
        building_year: { state: "unknown", value: null },
        noise_day_db: { state: "known", value: 50 },
      },
      definitions,
      {
        building_year: { enabled: true, minimum: 1960, acceptedCategories: [], weight: 1 },
        noise_day_db: { enabled: true, maximum: 55, acceptedCategories: [], weight: 0 },
      },
      "pass",
    );

    expect(result).toMatchObject({ eligible: true, score: null });
  });
});

describe("evaluateCriterionGroup", () => {
  it("uses OR for alternative ranges and AND for multiple destinations", () => {
    const values = { building_year: { state: "known" as const, value: 1970 }, commute_a: { state: "known" as const, value: 20 }, commute_b: { state: "known" as const, value: 50 } };
    const definitions = [{ id: "building_year", kind: "numeric" as const }, { id: "commute_a", kind: "numeric" as const }, { id: "commute_b", kind: "numeric" as const }];
    expect(evaluateCriterionGroup(values, definitions, { id: "years", operator: "or", criteria: [{ id: "old", layerId: "building_year", preference: { enabled: true, minimum: 1930, maximum: 1950, acceptedCategories: [] } }, { id: "new", layerId: "building_year", preference: { enabled: true, minimum: 1960, maximum: 1980, acceptedCategories: [] } }] })).toMatchObject({ status: "pass", score: 1 });
    expect(evaluateCriterionGroup(values, definitions, { id: "commutes", operator: "and", criteria: [{ id: "a", layerId: "commute_a", preference: { enabled: true, maximum: 30, acceptedCategories: [] } }, { id: "b", layerId: "commute_b", preference: { enabled: true, maximum: 30, acceptedCategories: [] } }] })).toMatchObject({ status: "fail", score: 0 });
  });
});

it("weights groups and applies group dealbreakers", () => {
  const result = evaluateBuildingGroups({ age: { state: "known", value: 1970 }, commute: { state: "known", value: 45 } }, [{ id: "age", kind: "numeric" }, { id: "commute", kind: "numeric" }], [{ id: "age-group", operator: "or", weight: 2, criteria: [{ id: "age", layerId: "age", preference: { enabled: true, minimum: 1960, acceptedCategories: [] } }] }, { id: "commute-group", operator: "and", dealbreaker: true, criteria: [{ id: "commute", layerId: "commute", preference: { enabled: true, maximum: 30, acceptedCategories: [] } }] }], "pass");
  expect(result).toMatchObject({ eligible: false, score: null, failedDealbreakers: ["commute-group"] });
});
