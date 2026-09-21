import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";

import { CriteriaControls, defaultRampDraft, newCriterionGroup, softFromRampDraft } from "./CriteriaControls";

const numericLayer = { layer_id: "building_year", finnish_label: "Rakennusvuosi", description: "", kind: "numeric" as const, unit: "year", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [1900, 2020] as [number, number], visualization_breaks: [1910, 1930, 1950, 1970, 1990, 2000, 2010] };

it("renders a flat AND criteria list with the ramp editor and no group or OR controls", () => {
  const preferences = { version: 2 as const, selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const, groups: [{ id: "y", operator: "and" as const, weight: 1, dealbreaker: false, criteria: [{ id: "y", layerId: "building_year", preference: { enabled: true, acceptedCategories: [], softPreference: { direction: "lower_is_better" as const, fullScoreAt: 1950, zeroScoreAt: 2000 } } }] }] };
  const markup = renderToStaticMarkup(createElement(CriteriaControls, { layers: [numericLayer], distributions: { building_year: { counts: [1, 2, 3, 4, 3, 2, 1], knownCount: 16, min: 1910, max: 2010 } }, preferences, onChange: () => {} }));

  expect(markup).toContain("Kriteerit");
  expect(markup).toContain("Lisää kriteeri");
  expect(markup).toContain("Pakollinen vaatimus");
  expect(markup).toContain("Tärkeys");
  expect(markup).toContain("ramp-dot");
  expect(markup).toContain("Aamumatka");
  expect(markup).not.toContain("Lisäasetukset");
  expect(markup).not.toContain("Yhdistä ehdot");
  expect(markup).not.toContain("Lisää ryhmä");
  expect(markup).not.toContain("Ehdoton vaatimus");
});

it("hides weight when the criterion is mandatory", () => {
  const preferences = { version: 2 as const, selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const, groups: [{ id: "y", operator: "and" as const, weight: 1, dealbreaker: true, criteria: [{ id: "y", layerId: "building_year", preference: { enabled: true, acceptedCategories: [] } }] }] };
  const markup = renderToStaticMarkup(createElement(CriteriaControls, { layers: [numericLayer], preferences, onChange: () => {} }));

  expect(markup).toContain("Pakollinen vaatimus");
  expect(markup).not.toContain("Tärkeys");
});

it("converts a ramp draft to a soft preference and rejects incomplete or reversed bounds", () => {
  expect(softFromRampDraft({ low: "0", high: "15", fullLow: true, fullHigh: false })).toEqual({ direction: "lower_is_better", fullScoreAt: 0, zeroScoreAt: 15 });
  expect(softFromRampDraft({ low: "25000", high: "45000", fullLow: false, fullHigh: true })).toEqual({ direction: "higher_is_better", fullScoreAt: 45000, zeroScoreAt: 25000 });
  // Both ends full = a full-score band (e.g. any building from the 1930s).
  expect(softFromRampDraft({ low: "1930", high: "1939", fullLow: true, fullHigh: true })).toEqual({ direction: "range", fullScoreAt: 1930, zeroScoreAt: 1939 });
  expect(softFromRampDraft({ low: "15", high: "0", fullLow: true, fullHigh: false })).toBeUndefined();
  expect(softFromRampDraft({ low: "", high: "15", fullLow: true, fullHigh: false })).toBeUndefined();
  expect(softFromRampDraft({ low: "0", high: "15", fullLow: false, fullHigh: false })).toBeUndefined();
});

it("creates a single-criterion AND group with a default ramp when adding a numeric criterion", () => {
  const group = newCriterionGroup(numericLayer);
  expect(group.operator).toBe("and");
  expect(group.dealbreaker).toBe(false);
  expect(group.criteria).toHaveLength(1);
  expect(group.criteria[0].layerId).toBe("building_year");
  expect(group.criteria[0].preference.softPreference).toEqual(softFromRampDraft(defaultRampDraft(numericLayer)));
});
