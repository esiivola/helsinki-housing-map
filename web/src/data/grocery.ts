import type { AppPreferences } from "../types/scoring";
import type { BuildingLayerValue } from "./attributes";
import type { LayerMetadata } from "./layers";

export const selectedGroceryLayerId = "selected_grocery_walk_m";

export const groceryStoreGroups = [
  ["prisma", "Prisma"], ["k_citymarket", "K-Citymarket"], ["lidl", "Lidl"], ["s_market", "S-market"], ["k_supermarket", "K-Supermarket"], ["sale", "Sale"], ["k_market", "K-Market"], ["alepa", "Alepa"], ["other_supermarket", "Muut supermarketit"], ["other_grocery", "Muut ruoka- ja lähikaupat"],
] as const;

export const selectedGroceryLayer: LayerMetadata = {
  layer_id: selectedGroceryLayerId, finnish_label: "Kävelymatka valittuihin ruokakauppoihin", description: "Lyhin kävelymatka valitsemaasi ruokakaupparyhmään.", kind: "numeric", unit: "m", allowed_categories: [], methodology: "Offline pedestrian-network distance to selected OpenStreetMap grocery-store groups.", caveat_ids: ["routing-origin-fallback", "osm-completeness"], source_ids: ["hsl_osm_extract"], visualization_range: [0, 10000],
};

export function selectedGroceryGroups(preferences: AppPreferences): readonly string[] {
  return preferences.groceryStoreGroups ?? groceryStoreGroups.map(([id]) => id);
}

export function groceryStoreLayerIds(preferences: AppPreferences): readonly string[] {
  return selectedGroceryGroups(preferences).map((group) => `grocery_store_${group}_walk_m`);
}

export function withSelectedGroceryLayer(layers: readonly LayerMetadata[]): LayerMetadata[] {
  return layers.some((layer) => layer.layer_id === "grocery_store_prisma_walk_m") ? [...layers, selectedGroceryLayer] : [...layers];
}

export function withSelectedGroceryValue(values: Record<string, BuildingLayerValue>, preferences: AppPreferences): Record<string, BuildingLayerValue> {
  const selected = groceryStoreLayerIds(preferences).map((id) => values[id]).filter((value): value is BuildingLayerValue => value !== undefined);
  const candidates = selected.filter((value) => (value.state === "known" || value.state === "partial") && typeof value.value === "number");
  if (!selected.length || !candidates.length) return { ...values, [selectedGroceryLayerId]: unknownValue() };
  const closest = candidates.reduce((best, value) => Number(value.value) < Number(best.value) ? value : best);
  const partial = candidates.length !== selected.length || selected.some((value) => value.state === "partial");
  return {
    ...values,
    [selectedGroceryLayerId]: {
      ...closest,
      state: partial ? "partial" : "known",
      coverage: candidates.length / selected.length,
      evidenceIds: [...new Set(candidates.flatMap((value) => value.evidenceIds))],
    },
  };
}

function unknownValue(): BuildingLayerValue {
  return { state: "unknown", value: null, values: [], distribution: {}, coverage: 0, evidenceIds: [], method: "derived", confidence: null };
}
