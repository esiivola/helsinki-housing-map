import { describe, expect, it } from "vitest";

import { parseManifest } from "./manifest";

describe("parseManifest", () => {
  it("accepts the supported schema major version", () => {
    expect(
      parseManifest('{"schema_version":"1.0.0","attribute_partitions":["attributes/a.json.gz"],"geometry_partitions":["geometry/a.geojson.gz"],"layer_catalogue":"layers.json","source_manifest":"sources.json","evidence":"evidence.json"}'),
    ).toMatchObject({ schemaVersion: "1.0.0" });
  });

  it("reads the optional compact all-building score inputs", () => {
    expect(parseManifest('{"schema_version":"1.0.0","attribute_partitions":[],"geometry_partitions":[],"layer_catalogue":"layers.json","source_manifest":"sources.json","evidence":"evidence.json","score_histogram_inputs":"score-histogram-inputs.json.gz"}').scoreHistogramInputs).toBe("score-histogram-inputs.json.gz");
  });

  it("reads optional tiled building partitions", () => {
    const manifest = parseManifest('{"schema_version":"1.1.0","attribute_partitions":[],"geometry_partitions":[],"layer_catalogue":"layers.json","source_manifest":"sources.json","evidence":"evidence.json","spatial_partitions":{"scheme":"webmercator","format":"geojson-gzip","building_tier":{"min_zoom":16,"tile_zoom":16,"geometry_path_template":"tiles/geometry/16/{x}/{y}.geojson.gz","core_attribute_path_template":"tiles/core/16/{x}/{y}.json.gz","layer_attribute_path_template":"tiles/layers/{layer_id}/16/{x}/{y}.json.gz","layer_tile_keys":{},"feature_id_property":"building_id","buffer_tiles":1,"tile_keys":["1/2"]},"overview_tiers":[{"min_zoom":10,"max_zoom":12,"cell_size_m":1000,"tile_zoom":10,"geometry_path_template":"overview/1000m/tiles/10/{x}/{y}.geojson.gz","layer_path_template":"overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz","tile_keys":["1/2"]}]}}');
    expect(manifest.spatialPartitions?.buildingTier.minZoom).toBe(16);
    expect(manifest.spatialPartitions?.buildingTier.tileKeys).toEqual(["1/2"]);
    expect(manifest.spatialPartitions?.overviewTiers[0].geometryPathTemplate).toBe("overview/1000m/tiles/10/{x}/{y}.geojson.gz");
  });

  it("keeps a missing layer tile index distinguishable from an empty index", () => {
    const manifest = parseManifest('{"schema_version":"1.1.0","attribute_partitions":[],"geometry_partitions":[],"layer_catalogue":"layers.json","source_manifest":"sources.json","evidence":"evidence.json","spatial_partitions":{"scheme":"webmercator","format":"geojson-gzip","building_tier":{"min_zoom":16,"tile_zoom":16,"geometry_path_template":"tiles/geometry/16/{x}/{y}.geojson.gz","core_attribute_path_template":"tiles/core/16/{x}/{y}.json.gz","layer_attribute_path_template":"tiles/layers/{layer_id}/16/{x}/{y}.json.gz","feature_id_property":"building_id","buffer_tiles":1,"tile_keys":["1/2"]},"overview_tiers":[{"min_zoom":10,"max_zoom":12,"cell_size_m":1000,"tile_zoom":10,"geometry_path_template":"overview/1000m/tiles/10/{x}/{y}.geojson.gz","layer_path_template":"overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz","tile_keys":["1/2"]}]}}');
    expect(manifest.spatialPartitions?.buildingTier.layerTileKeys).toBeUndefined();
  });

  it("rejects unsupported major versions with a readable error", () => {
    expect(() =>
      parseManifest('{"schema_version":"2.0.0","attribute_partitions":[],"geometry_partitions":[],"layer_catalogue":"layers.json","source_manifest":"sources.json","evidence":"evidence.json"}'),
    ).toThrow("Unsupported data schema version 2.0.0");
  });
});
