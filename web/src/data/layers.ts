export interface LayerMetadata {
  layer_id: string;
  finnish_label: string;
  description: string;
  kind: "numeric" | "categorical";
  unit: string | null;
  allowed_categories: string[];
  methodology: string;
  caveat_ids: string[];
  source_ids: string[];
  visualization_range?: [number, number] | null;
  visualization_breaks?: number[];
  visible?: boolean;
}

export type TransitStatistic = "min" | "median" | "max" | "median_boarding";

export interface CommuteLayerParts {
  mode: "bike" | "transit";
  destination: string;
  statistic: BikeStatistic | TransitStatistic;
}

export type BikeStatistic = "min" | "effective";

export const transitStatistics: readonly TransitStatistic[] = ["min", "median", "max", "median_boarding"];
export const layerGroups = ["Liikkuminen", "Lähipalvelut", "Ympäristö", "Asuminen ja rakennus", "Aluetiedot"] as const;
export type LayerGroup = typeof layerGroups[number];

export function transitStatisticLabel(statistic: TransitStatistic): string {
  return ({ min: "Minimi", median: "Mediaani", max: "Maksimi", median_boarding: "Ajoneuvoihin nousut (mediaani)" })[statistic];
}

export function commuteLayerParts(layerId: string): CommuteLayerParts | undefined {
  const effective = /^bike_workplace_(.+)_effective_min$/.exec(layerId);
  if (effective) return { mode: "bike", destination: effective[1], statistic: "effective" };
  const bike = /^bike_workplace_(.+)_min$/.exec(layerId);
  if (bike) return { mode: "bike", destination: bike[1], statistic: "min" };
  const transit = /^transit_workplace_(.+)_(min|median|max)_min$/.exec(layerId);
  if (transit) return { mode: "transit", destination: transit[1], statistic: transit[2] as TransitStatistic };
  const boarding = /^transit_workplace_(.+)_median_boarding$/.exec(layerId);
  return boarding ? { mode: "transit", destination: boarding[1], statistic: "median_boarding" } : undefined;
}

export function commuteDestinations(layers: readonly { layer_id: string }[], mode: CommuteLayerParts["mode"]): string[] {
  return [...new Set(layers.flatMap((layer) => {
    const parts = commuteLayerParts(layer.layer_id);
    return parts?.mode === mode ? [parts.destination] : [];
  }))];
}

export function mapLayerOptions<T extends { layer_id: string }>(layers: readonly T[], selectedLayerId: string): T[] {
  const selected = layers.find((layer) => layer.layer_id === selectedLayerId);
  return selected && commuteLayerParts(selected.layer_id)
    ? [selected, ...layers.filter((layer) => layer !== selected && !commuteLayerParts(layer.layer_id))]
    : layers.filter((layer) => !commuteLayerParts(layer.layer_id));
}

export function layerGroupFor(layerId: string): LayerGroup {
  if (layerId.startsWith("transit_workplace_") || layerId.startsWith("bike_workplace_") || layerId === "helsinki_main_cycle_route_access_m") return "Liikkuminen";
  if (layerId === "selected_grocery_walk_m" || layerId === "selected_education_service_walk_m" || layerId === "selected_health_service_walk_m" || layerId === "library_walk_m") return "Lähipalvelut";
  if (["forest_walk_m", "green_cover_300m_pct", "noise_day_upper_db", "noise_night_upper_db", "shore_walk_m"].includes(layerId)) return "Ympäristö";
  if (["building_year", "dwelling_count", "elevator", "heating_energy_source", "heating_method", "house_type", "land_owner_class", "storey_count"].includes(layerId)) return "Asuminen ja rakennus";
  return "Aluetiedot";
}

export function parseLayers(serialized: string): LayerMetadata[] {
  const value: unknown = JSON.parse(serialized);
  if (!Array.isArray(value) || !value.every(isLayer)) throw new Error("Invalid layer catalogue");
  return value;
}

function isLayer(value: unknown): value is LayerMetadata {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const layer = value as Record<string, unknown>;
  return typeof layer.layer_id === "string" && typeof layer.finnish_label === "string"
    && typeof layer.description === "string" && (layer.kind === "numeric" || layer.kind === "categorical")
    && Array.isArray(layer.allowed_categories) && typeof layer.methodology === "string"
    && Array.isArray(layer.caveat_ids) && Array.isArray(layer.source_ids)
    && (layer.visible === undefined || typeof layer.visible === "boolean")
    && (layer.visualization_range === undefined || layer.visualization_range === null || Array.isArray(layer.visualization_range) && layer.visualization_range.length === 2 && layer.visualization_range.every((item) => typeof item === "number"))
    && (layer.visualization_breaks === undefined || Array.isArray(layer.visualization_breaks) && layer.visualization_breaks.length >= 2 && layer.visualization_breaks.every((item) => typeof item === "number"));
}
