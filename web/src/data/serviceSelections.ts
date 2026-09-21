import type { AppPreferences } from "../types/scoring";
import type { BuildingLayerValue } from "./attributes";
import type { LayerMetadata } from "./layers";

export type ServiceSelection = {
  readonly layerId: string;
  readonly preferenceKey: "educationServiceGroups" | "healthServiceGroups";
  readonly prefix: "education_service" | "health_service";
  readonly label: string;
  readonly description: string;
  readonly sourceIds: readonly string[];
  readonly groups: readonly (readonly [string, string])[];
};

export const educationSelection: ServiceSelection = {
  layerId: "selected_education_service_walk_m", preferenceKey: "educationServiceGroups", prefix: "education_service", label: "Kävelymatka valittuihin kouluihin ja päiväkoteihin", description: "Lyhin kävelymatka valitsemaasi koulutus- tai päiväkotiryhmään.", sourceIds: ["service_map_education", "hsl_osm_extract"],
  groups: [["daycare", "Päiväkoti"], ["primary_school", "Ala-aste"], ["lower_secondary_school", "Yläaste"], ["upper_secondary_school", "Lukio"], ["vocational_school", "Ammattikoulu"]],
};

export const healthSelection: ServiceSelection = {
  layerId: "selected_health_service_walk_m", preferenceKey: "healthServiceGroups", prefix: "health_service", label: "Kävelymatka valittuihin terveys- ja sosiaalipalveluihin", description: "Lyhin kävelymatka valitsemaasi terveys- tai sosiaalipalveluryhmään.", sourceIds: ["ptv_healthcare", "hsl_osm_extract"],
  groups: [["health_centre", "Terveyskeskus"], ["dental_care", "Hammashoito"], ["maternity_and_child_health_clinic", "Neuvola"], ["mental_health_and_substance_use_services", "Mielenterveys- ja päihdepalvelut"], ["university_or_central_hospital", "Yliopisto- tai keskussairaala"], ["mehilainen", "Mehiläinen"], ["terveystalo", "Terveystalo"], ["pihlajalinna", "Pihlajalinna"], ["other_private_clinic", "Muut yksityiset lääkäriasemat"], ["social_services", "Sosiaalipalvelut"]],
};

export const serviceSelections = [educationSelection, healthSelection] as const;

export function selectedServiceGroups(selection: ServiceSelection, preferences: AppPreferences): readonly string[] {
  return preferences[selection.preferenceKey] ?? selection.groups.map(([id]) => id);
}

export function serviceLayerIds(selection: ServiceSelection, preferences: AppPreferences): readonly string[] {
  return selectedServiceGroups(selection, preferences).map((group) => `${selection.prefix}_${group}_walk_m`);
}

export function withSelectedServiceLayers(layers: readonly LayerMetadata[]): LayerMetadata[] {
  return serviceSelections.reduce<LayerMetadata[]>((available, selection) => available.some((layer) => layer.layer_id === `${selection.prefix}_${selection.groups[0][0]}_walk_m`) ? [...available, selectedServiceLayer(selection)] : available, [...layers]);
}

export function selectedServiceLayer(selection: ServiceSelection): LayerMetadata {
  return { layer_id: selection.layerId, finnish_label: selection.label, description: selection.description, kind: "numeric", unit: "m", allowed_categories: [], methodology: "Offline pedestrian-network distance to selected published service-location groups.", caveat_ids: ["routing-origin-fallback", "service-category-classification"], source_ids: [...selection.sourceIds], visualization_range: [0, 10000] };
}

export function withSelectedServiceValues(values: Record<string, BuildingLayerValue>, preferences: AppPreferences): Record<string, BuildingLayerValue> {
  return serviceSelections.reduce((result, selection) => withSelectedServiceValue(result, selection, preferences), values);
}

export function withSelectedServiceValue(values: Record<string, BuildingLayerValue>, selection: ServiceSelection, preferences: AppPreferences): Record<string, BuildingLayerValue> {
  const selected = serviceLayerIds(selection, preferences).map((id) => values[id]).filter((value): value is BuildingLayerValue => value !== undefined);
  const candidates = selected.filter((value) => (value.state === "known" || value.state === "partial") && typeof value.value === "number");
  if (!selected.length || !candidates.length) return { ...values, [selection.layerId]: unknownValue() };
  const closest = candidates.reduce((best, value) => Number(value.value) < Number(best.value) ? value : best);
  const partial = candidates.length !== selected.length || selected.some((value) => value.state === "partial");
  return { ...values, [selection.layerId]: { ...closest, state: partial ? "partial" : "known", coverage: candidates.length / selected.length, evidenceIds: [...new Set(candidates.flatMap((value) => value.evidenceIds))] } };
}

export function selectionForLayerId(layerId: string): ServiceSelection | undefined {
  return serviceSelections.find((selection) => selection.layerId === layerId);
}

function unknownValue(): BuildingLayerValue {
  return { state: "unknown", value: null, values: [], distribution: {}, coverage: 0, evidenceIds: [], method: "derived", confidence: null };
}
