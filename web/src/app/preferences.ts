import type { AppPreferences, CriterionGroup, LayerPreference, OverviewAggregation } from "../types/scoring";

export interface GroupPreferences {
  version: 2;
  groups: readonly CriterionGroup[];
  selectedVisualization: string;
  missingDealbreakerPolicy: "pass" | "fail";
  overviewAggregation?: OverviewAggregation;
}

export function newGroupPreferences(): GroupPreferences {
  return { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", overviewAggregation: "median" };
}

export function addCriterionGroup(preferences: GroupPreferences, group: CriterionGroup): GroupPreferences {
  if (preferences.groups.some((item) => item.id === group.id)) throw new Error(`Duplicate criterion group: ${group.id}`);
  return { ...preferences, groups: [...preferences.groups, copyGroup(group)] };
}

export function addSavedCriterionGroup(preferences: AppPreferences, group: CriterionGroup): AppPreferences {
  if (preferences.groups.some((item) => item.id === group.id)) throw new Error(`Duplicate criterion group: ${group.id}`);
  return { ...preferences, groups: [...preferences.groups, copyGroup(group)] };
}

export function replaceCriterionGroup(preferences: GroupPreferences, group: CriterionGroup): GroupPreferences {
  return { ...preferences, groups: preferences.groups.map((item) => item.id === group.id ? copyGroup(group) : item) };
}

function copyGroup(group: CriterionGroup): CriterionGroup {
  return JSON.parse(JSON.stringify(group)) as CriterionGroup;
}

export interface NamedPreferenceSet {
  id: string;
  name: string;
  updatedAt: string;
  preferences: AppPreferences;
}

export interface SavedPreferenceSets {
  version: 1;
  activeId: string | null;
  draft: AppPreferences;
  sets: readonly NamedPreferenceSet[];
}

export function restoreSavedPreferenceSets(serialized: string): SavedPreferenceSets | null {
  try {
    const value: unknown = JSON.parse(serialized);
    if (!isRecord(value) || value.version !== 1 || (value.activeId !== null && typeof value.activeId !== "string") || !isPreferences(value.draft) || !Array.isArray(value.sets)) return null;
    if (!value.sets.every(isNamedPreferenceSet) || (value.activeId !== null && !value.sets.some((set) => set.id === value.activeId))) return null;
    return { version: 1, activeId: value.activeId, draft: copyPreferences(value.draft), sets: value.sets.map(copySet) };
  } catch {
    return null;
  }
}

export function serializeSavedPreferenceSets(settings: SavedPreferenceSets): string {
  return JSON.stringify(settings);
}

export function newSavedPreferenceSets(): SavedPreferenceSets {
  return { version: 1, activeId: null, draft: defaults(), sets: [] };
}

export function updateDraft(settings: SavedPreferenceSets, draft: AppPreferences): SavedPreferenceSets {
  return { ...settings, draft: copyPreferences(draft) };
}

export function saveActivePreferenceSet(settings: SavedPreferenceSets, updatedAt: string): SavedPreferenceSets {
  if (!settings.activeId) return settings;
  return {
    ...settings,
    sets: settings.sets.map((set) => set.id === settings.activeId ? { ...set, updatedAt, preferences: copyPreferences(settings.draft) } : set),
  };
}

export function saveAsPreferenceSet(settings: SavedPreferenceSets, name: string, id: string, updatedAt: string): SavedPreferenceSets {
  const set = { id, name, updatedAt, preferences: copyPreferences(settings.draft) };
  return { ...settings, activeId: id, sets: [...settings.sets, set] };
}

export function renamePreferenceSet(settings: SavedPreferenceSets, id: string, name: string, updatedAt: string): SavedPreferenceSets {
  return { ...settings, sets: settings.sets.map((set) => set.id === id ? { ...set, name, updatedAt } : set) };
}

export function duplicatePreferenceSet(settings: SavedPreferenceSets, id: string, name: string, duplicateId: string, updatedAt: string): SavedPreferenceSets {
  const source = settings.sets.find((set) => set.id === id);
  return source ? { ...settings, sets: [...settings.sets, { id: duplicateId, name, updatedAt, preferences: copyPreferences(source.preferences) }] } : settings;
}

export function deletePreferenceSet(settings: SavedPreferenceSets, id: string): SavedPreferenceSets {
  return { ...settings, activeId: settings.activeId === id ? null : settings.activeId, sets: settings.sets.filter((set) => set.id !== id) };
}

export function loadPreferenceSet(settings: SavedPreferenceSets, id: string): SavedPreferenceSets {
  const set = settings.sets.find((item) => item.id === id);
  return set ? { ...settings, activeId: id, draft: copyPreferences(set.preferences) } : settings;
}

export function isActivePreferenceSetDirty(settings: SavedPreferenceSets): boolean {
  const active = settings.sets.find((set) => set.id === settings.activeId);
  return !!active && JSON.stringify(active.preferences) !== JSON.stringify(settings.draft);
}

function isPreferences(value: unknown): value is AppPreferences {
  if (!isRecord(value) || value.version !== 2 || typeof value.selectedVisualization !== "string") return false;
  if (value.missingDealbreakerPolicy !== "pass" && value.missingDealbreakerPolicy !== "fail") return false;
  return Array.isArray(value.groups) && value.groups.every(isCriterionGroup) && (value.overviewAggregation === undefined || isOverviewAggregation(value.overviewAggregation)) && [value.groceryStoreGroups, value.educationServiceGroups, value.healthServiceGroups].every((groups) => groups === undefined || Array.isArray(groups) && groups.every((group) => typeof group === "string"));
}

function isCriterionGroup(value: unknown): value is CriterionGroup {
  if (!isRecord(value) || typeof value.id !== "string" || (value.operator !== "and" && value.operator !== "or") || !Array.isArray(value.criteria) || !optionalNumber(value.weight) || (value.dealbreaker !== undefined && typeof value.dealbreaker !== "boolean")) return false;
  return value.criteria.every((criterion) => isRecord(criterion) && typeof criterion.id === "string" && typeof criterion.layerId === "string" && isLayerPreference(criterion.preference));
}

function isNamedPreferenceSet(value: unknown): value is NamedPreferenceSet {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string" && typeof value.updatedAt === "string" && isPreferences(value.preferences);
}

function copySet(set: NamedPreferenceSet): NamedPreferenceSet {
  return { ...set, preferences: copyPreferences(set.preferences) };
}

function copyPreferences(preferences: AppPreferences): AppPreferences {
  return JSON.parse(JSON.stringify(preferences)) as AppPreferences;
}

function defaults(): AppPreferences {
  return { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", overviewAggregation: "median" };
}

function isOverviewAggregation(value: unknown): value is OverviewAggregation {
  return value === "min" || value === "median" || value === "max";
}

function isLayerPreference(value: unknown): value is LayerPreference {
  if (!isRecord(value) || typeof value.enabled !== "boolean" || !Array.isArray(value.acceptedCategories)) {
    return false;
  }
  return (
    value.acceptedCategories.every((category) => typeof category === "string") &&
    optionalNumber(value.minimum) &&
    optionalNumber(value.maximum) &&
    optionalNumber(value.weight) &&
    (value.dealbreaker === undefined || typeof value.dealbreaker === "boolean") &&
    (value.softPreference === undefined || isSoftPreference(value.softPreference))
  );
}

function isSoftPreference(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return (value.direction === "lower_is_better" || value.direction === "higher_is_better") &&
    typeof value.fullScoreAt === "number" && Number.isFinite(value.fullScoreAt) &&
    typeof value.zeroScoreAt === "number" && Number.isFinite(value.zeroScoreAt);
}

function optionalNumber(value: unknown): boolean {
  return value === undefined || (typeof value === "number" && Number.isFinite(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
