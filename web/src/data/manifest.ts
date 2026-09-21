import type { AppManifest } from "../types/scoring";

const SUPPORTED_SCHEMA_MAJOR = "1";

export function parseManifest(serialized: string): AppManifest {
  const value: unknown = JSON.parse(serialized);
  if (!isManifest(value)) throw new Error("Invalid data manifest");
  if (value.schema_version.split(".")[0] !== SUPPORTED_SCHEMA_MAJOR) {
    throw new Error(`Unsupported data schema version ${value.schema_version}`);
  }
  return {
    schemaVersion: value.schema_version,
    attributePartitions: value.attribute_partitions,
    geometryPartitions: value.geometry_partitions,
    layerCatalogue: value.layer_catalogue,
    sourceManifest: value.source_manifest,
    evidence: value.evidence,
    layerDistributions: typeof value.layer_distributions === "string" ? value.layer_distributions : undefined,
    scoreHistogramInputs: typeof value.score_histogram_inputs === "string" ? value.score_histogram_inputs : undefined,
    spatialPartitions: spatialPartitions(value.spatial_partitions),
  };
}

function spatialPartitions(value: unknown): AppManifest["spatialPartitions"] {
  if (typeof value !== "object" || value === null) return undefined;
  const buildingTier = (value as Record<string, unknown>).building_tier;
  if (typeof buildingTier !== "object" || buildingTier === null) return undefined;
  const tier = buildingTier as Record<string, unknown>;
  const overviewTiers = (value as Record<string, unknown>).overview_tiers;
  if (!Number.isInteger(tier.min_zoom) || !Number.isInteger(tier.tile_zoom) || typeof tier.geometry_path_template !== "string" || typeof tier.core_attribute_path_template !== "string" || typeof tier.layer_attribute_path_template !== "string" || !Number.isInteger(tier.buffer_tiles) || !Array.isArray(tier.tile_keys) || !tier.tile_keys.every((key) => typeof key === "string")) return undefined;
  if (!Array.isArray(overviewTiers) || !overviewTiers.every((item) => typeof item === "object" && item !== null && Number.isInteger((item as Record<string, unknown>).min_zoom) && Number.isInteger((item as Record<string, unknown>).max_zoom) && Number.isInteger((item as Record<string, unknown>).tile_zoom) && typeof (item as Record<string, unknown>).geometry_path_template === "string" && typeof (item as Record<string, unknown>).layer_path_template === "string" && Array.isArray((item as Record<string, unknown>).tile_keys) && ((item as Record<string, unknown>).tile_keys as unknown[]).every((key) => typeof key === "string"))) return undefined;
  return {
    buildingTier: {
      minZoom: tier.min_zoom as number,
      tileZoom: tier.tile_zoom as number,
      geometryPathTemplate: tier.geometry_path_template as string,
      coreAttributePathTemplate: tier.core_attribute_path_template as string,
      layerAttributePathTemplate: tier.layer_attribute_path_template as string,
      layerTileKeys: typeof tier.layer_tile_keys === "object" && tier.layer_tile_keys !== null ? tier.layer_tile_keys as Record<string, string[]> : undefined,
      bufferTiles: tier.buffer_tiles as number,
      tileKeys: tier.tile_keys as string[],
    },
    overviewTiers: overviewTiers.map((item) => ({ minZoom: (item as Record<string, unknown>).min_zoom as number, maxZoom: (item as Record<string, unknown>).max_zoom as number, tileZoom: (item as Record<string, unknown>).tile_zoom as number, geometryPathTemplate: (item as Record<string, unknown>).geometry_path_template as string, layerPathTemplate: (item as Record<string, unknown>).layer_path_template as string, tileKeys: (item as Record<string, unknown>).tile_keys as string[] })),
  };
}

function isManifest(value: unknown): value is {
  schema_version: string;
  attribute_partitions: string[];
  geometry_partitions: string[];
  layer_catalogue: string;
  source_manifest: string;
  evidence: string;
  layer_distributions?: string;
  score_histogram_inputs?: string;
  spatial_partitions?: unknown;
} {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const manifest = value as Record<string, unknown>;
  return (
    typeof manifest.schema_version === "string" &&
    Array.isArray(manifest.attribute_partitions) &&
    manifest.attribute_partitions.every((partition) => typeof partition === "string") &&
    Array.isArray(manifest.geometry_partitions) &&
    manifest.geometry_partitions.every((partition) => typeof partition === "string") &&
    typeof manifest.layer_catalogue === "string" &&
    typeof manifest.source_manifest === "string" &&
    typeof manifest.evidence === "string"
  );
}
