import { describe, expect, it } from "vitest";

import { addCriterionGroup, addSavedCriterionGroup, deletePreferenceSet, duplicatePreferenceSet, isActivePreferenceSetDirty, loadPreferenceSet, newGroupPreferences, newSavedPreferenceSets, replaceCriterionGroup, restoreSavedPreferenceSets, saveActivePreferenceSet, saveAsPreferenceSet } from "./preferences";

describe("preferences", () => {
  const preferences = {
    version: 2 as const,
    groups: [{ id: "noise", operator: "and" as const, dealbreaker: true, criteria: [{ id: "noise-day", layerId: "noise_day_db", preference: { enabled: true, maximum: 55, acceptedCategories: [] } }] }],
    selectedVisualization: "noise_day_db",
    missingDealbreakerPolicy: "fail" as const,
    overviewAggregation: "max" as const,
  };

  it("starts with a blank draft and rejects malformed saved settings", () => {
    expect(newSavedPreferenceSets()).toMatchObject({ version: 1, activeId: null, sets: [] });
    expect(restoreSavedPreferenceSets('{"version":1}')).toBeNull();
  });

  it("saves, restores, and marks edits to a named profile", () => {
    const saved = saveAsPreferenceSet({ ...newSavedPreferenceSets(), draft: preferences }, "Koti", "home", "2026-08-31T10:00:00.000Z");
    const edited = { ...preferences, selectedVisualization: "overall" };
    expect(isActivePreferenceSetDirty({ ...saved, draft: edited })).toBe(true);
    const restored = restoreSavedPreferenceSets(JSON.stringify(saveActivePreferenceSet({ ...saved, draft: edited }, "2026-08-31T11:00:00.000Z")));
    expect(restored).toMatchObject({ activeId: "home", draft: edited, sets: [{ id: "home", updatedAt: "2026-08-31T11:00:00.000Z", preferences: edited }] });
  });

  it("duplicates, loads, and deletes named profiles", () => {
    const home = saveAsPreferenceSet({ ...newSavedPreferenceSets(), draft: preferences }, "Koti", "home", "2026-08-31T10:00:00.000Z");
    const duplicated = duplicatePreferenceSet(home, "home", "Koti (kopio)", "copy", "2026-08-31T11:00:00.000Z");
    expect(duplicated.sets).toHaveLength(2);
    expect(loadPreferenceSet({ ...duplicated, draft: { ...preferences, selectedVisualization: "overall" } }, "copy").draft).toEqual(preferences);
    expect(deletePreferenceSet({ ...duplicated, activeId: "copy" }, "copy")).toMatchObject({ activeId: null, sets: [{ id: "home" }] });
  });
});

describe("group preferences", () => {
  it("adds repeatable groups and keeps their weight and dealbreaker on the group", () => {
    const first = { id: "commute-1", operator: "and" as const, weight: 2, dealbreaker: true, criteria: [{ id: "kamppi", layerId: "transit_workplace_kamppi_median_min", preference: { enabled: true, maximum: 35, acceptedCategories: [] } }] };
    const second = { ...first, id: "commute-2", dealbreaker: false };
    const preferences = addCriterionGroup(addCriterionGroup(newGroupPreferences(), first), second);
    expect(preferences.groups).toHaveLength(2);
    expect(replaceCriterionGroup(preferences, { ...second, weight: 3 }).groups[1]).toMatchObject({ weight: 3, dealbreaker: false });
  });

  it("persists groups in named settings profiles", () => {
    const group = { id: "years", operator: "or" as const, criteria: [{ id: "before", layerId: "building_year", preference: { enabled: true, maximum: 1950, acceptedCategories: [] } }] };
    const draft = { ...newSavedPreferenceSets().draft, selectedVisualization: "building_year" };
    const saved = saveAsPreferenceSet({ ...newSavedPreferenceSets(), draft: addSavedCriterionGroup(draft, group) }, "Koti", "home", "2026-09-01T08:00:00.000Z");
    expect(restoreSavedPreferenceSets(JSON.stringify(saved))?.draft.groups).toEqual([group]);
  });
});
