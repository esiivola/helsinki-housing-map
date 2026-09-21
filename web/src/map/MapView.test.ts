import { describe, expect, it } from "vitest";

import { activeLayerIds, activePlanPopupHtml, buildingTilePaths, cartoStyleUrl, destinationPopupHtml, filteredServiceDestinations, failedTileMessage, initialAttributePartition, initialGeometryPartition, layerTileIsAvailable, layerTilePath, mapControlLabels, mapLibreWorkerUrl, mergeOverviewGeometry, mergeOverviewTiles, mergeTileGeometry, overviewContributors, overviewGeometryForBounds, overviewLayerPath, overviewLoadedMessage, overviewMessage, overviewStillCurrent, overviewSummary, overviewTierForZoom, overviewTileKeys, overviewTilePath, scoredGeometry, scoredOverview, serviceDestinationLayerIds, smallestBuildingFeature, suitabilityLegendItems, visualizationLegend, visualizationLegendItems, visualizationPaint, visualizationVisibility } from "./MapView";

it("uses Finnish labels for map controls", () => {
  expect(mapControlLabels).toEqual({ zoomIn: "Lähennä karttaa", zoomOut: "Loitonna karttaa", resetNorth: "Nollaa kartan suunta" });
});

it("hides map geometry until a visualization is selected", () => {
  expect(visualizationVisibility({ version: 2, selectedVisualization: "none", missingDealbreakerPolicy: "pass", groups: [] })).toBe("none");
  expect(visualizationVisibility({ version: 2, selectedVisualization: "overall", missingDealbreakerPolicy: "pass", groups: [] })).toBe("visible");
});

it("loads only the selected visualization and configured criterion layers", () => {
  expect(activeLayerIds({ version: 2, selectedVisualization: "income", missingDealbreakerPolicy: "pass", groups: [{ id: "a", operator: "and", criteria: [{ id: "one", layerId: "noise", preference: { enabled: true, acceptedCategories: [] } }, { id: "two", layerId: "income", preference: { enabled: true, acceptedCategories: [] } }] }] })).toEqual(["income", "noise"]);
  expect(activeLayerIds({ version: 2, selectedVisualization: "overall", missingDealbreakerPolicy: "pass", groups: [] })).toEqual([]);
  expect(activeLayerIds({ version: 2, selectedVisualization: "selected_education_service_walk_m", missingDealbreakerPolicy: "pass", groups: [], educationServiceGroups: ["daycare", "primary_school"] })).toEqual(["education_service_daycare_walk_m", "education_service_primary_school_walk_m"]);
});

it("filters non-interactive service markers to the active selected service groups", () => {
  const groceryPreferences = { version: 2 as const, groups: [], selectedVisualization: "selected_grocery_walk_m", missingDealbreakerPolicy: "pass" as const, groceryStoreGroups: ["prisma", "lidl"] };
  const educationPreferences = { version: 2 as const, groups: [], selectedVisualization: "selected_education_service_walk_m", missingDealbreakerPolicy: "pass" as const, educationServiceGroups: ["daycare"] };
  const destinations = { type: "FeatureCollection", features: [
    { type: "Feature", properties: { layer_id: "grocery_store_prisma_walk_m" }, geometry: { type: "Point", coordinates: [24.93, 60.2] } },
    { type: "Feature", properties: { layer_id: "grocery_store_lidl_walk_m" }, geometry: { type: "Point", coordinates: [24.94, 60.2] } },
    { type: "Feature", properties: { layer_id: "education_service_daycare_walk_m" }, geometry: { type: "Point", coordinates: [24.95, 60.2] } },
  ] } as GeoJSON.FeatureCollection;

  expect(serviceDestinationLayerIds(groceryPreferences)).toEqual(["grocery_store_prisma_walk_m", "grocery_store_lidl_walk_m"]);
  expect(filteredServiceDestinations(destinations, groceryPreferences).features).toHaveLength(2);
  expect(serviceDestinationLayerIds(educationPreferences)).toEqual(["education_service_daycare_walk_m"]);
  expect(filteredServiceDestinations(destinations, educationPreferences).features).toHaveLength(1);
});

it("renders every distinct destination name safely in a marker popup", () => {
  expect(destinationPopupHtml(["Prisma Tripla", "Prisma Kannelmäki", "Prisma Tripla", "<test>"])).toContain("Prisma Kannelmäki");
  expect(destinationPopupHtml(["<test>"])).toContain("&lt;test&gt;");
  expect(destinationPopupHtml(["Prisma Tripla", "Prisma Tripla"]).match(/Prisma Tripla/g)).toHaveLength(1);
});

it("renders useful active-plan details and the official plan-map link", () => {
  const html = activePlanPopupHtml({ plan_number: "12990", plan_type: "Kaava", status: "Vireillä", area_m2: 7297.97007, approval: "kylk <27.1.2026>", source_updated_at: "2026-08-28" });

  expect(html).toContain("Vireillä oleva asemakaavamuutos");
  expect(html).toContain("Kaavanumero");
  expect(html).toContain("12990");
  expect(html).toContain("kylk &lt;27.1.2026&gt;");
  expect(html).toContain("Lisätietoa kaavasta");
  expect(html).toContain("https://kartta.hel.fi/?link=bZWSYX");
  expect(html).not.toContain("Tyyppi");
  expect(html).not.toContain("Tila");
  expect(html).not.toContain("Pinta-ala");
  expect(html).not.toContain("Lähde päivitetty");
});

it("builds a layer-specific tile path", () => {
  expect(layerTilePath("37308/18969", "income_median_eur", "tiles/layers/{layer_id}/16/{x}/{y}.json.gz")).toBe("tiles/layers/income_median_eur/16/37308/18969.json.gz");
});

it("loads legacy layer tiles when the manifest has no availability index", () => {
  const tier = { minZoom: 16, tileZoom: 16, geometryPathTemplate: "tiles/geometry/16/{x}/{y}.geojson.gz", coreAttributePathTemplate: "tiles/core/16/{x}/{y}.json.gz", layerAttributePathTemplate: "tiles/layers/{layer_id}/16/{x}/{y}.json.gz", bufferTiles: 1, tileKeys: ["1/2"] };
  expect(layerTileIsAvailable(tier, "income_median_eur", "1/2")).toBe(true);
  expect(layerTileIsAvailable({ ...tier, layerTileKeys: { income_median_eur: [] } }, "income_median_eur", "1/2")).toBe(false);
});

it("uses a Vite-managed MapLibre worker asset", () => {
  expect(mapLibreWorkerUrl).toContain("maplibre-gl-worker");
});

it("uses CARTO's Positron vector style when a build-time key is provided", () => {
  expect(cartoStyleUrl("example")).toBe("https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=example");
  expect(cartoStyleUrl(undefined)).toBe("https://basemaps.cartocdn.com/gl/positron-gl-style/style.json");
});

it("shows suitability failure and missing-data swatches using the map colours", () => {
  expect(suitabilityLegendItems()).toEqual(expect.arrayContaining([
    { label: "Ehdoton vaatimus ei täyty", color: "#b91c1c" },
    { label: "Tieto puuttuu", color: "#475569" },
  ]));
});

it("colours an overview cell from selected-layer coverage without scoring it", () => {
  const overview = { type: "FeatureCollection", features: [{ type: "Feature", properties: { building_count: 4, layer_state_counts: { income_median_eur: { known: 3, unknown: 1 } } }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  expect(scoredOverview(overview, "income_median_eur").features[0].properties?.display_coverage).toBe(0.75);
  expect(scoredOverview(overview, "overall").features[0].properties?.display_coverage).toBe(0);
});

it("calculates suitability summaries from the building inputs exported with an overview cell", () => {
  const overview = { type: "FeatureCollection", features: [{ type: "Feature", properties: { building_count: 2, score_inputs: [{ building_year: { state: "known", value: 1980, values: [] } }, { building_year: { state: "known", value: 1940, values: [] } }] }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  const layers = [{ layer_id: "building_year", kind: "numeric" as const, finnish_label: "Rakennusvuosi", description: "", unit: "year", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }];
  const preferences = { version: 2 as const, groups: [{ id: "years", operator: "and" as const, criteria: [{ id: "year", layerId: "building_year", preference: { enabled: true, minimum: 1960, acceptedCategories: [] } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };

  expect(scoredOverview(overview, "overall", layers, "median", preferences).features[0].properties).toMatchObject({ display_status: "known", display_value: 0.5 });
});

it("uses exported min, median, and max values plus categorical modes in overview cells", () => {
  const overview = { type: "FeatureCollection", features: [{ type: "Feature", properties: { building_count: 4, layer_state_counts: { income_median_eur: { known: 3, unknown: 1 }, land_owner_class: { known: 4 } }, layer_summaries: { income_median_eur: { min: 22000, median: 42000, max: 72000 }, land_owner_class: { value: "city", mode_share: 0.75 } } }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  const layers = [
    { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [0, 100000] as [number, number] },
    { layer_id: "land_owner_class", kind: "categorical" as const, finnish_label: "Maanomistajaluokka", description: "", unit: null, allowed_categories: ["city", "non_city", "mixed"], methodology: "", caveat_ids: [], source_ids: [] },
  ];

  expect(scoredOverview(overview, "income_median_eur", layers).features[0].properties).toMatchObject({ display_value: 42000, display_coverage: 0.75, display_status: "partial" });
  expect(scoredOverview(overview, "income_median_eur", layers, "min").features[0].properties).toMatchObject({ display_value: 22000 });
  expect(scoredOverview(overview, "income_median_eur", layers, "max").features[0].properties).toMatchObject({ display_value: 72000 });
  expect(scoredOverview(overview, "land_owner_class", layers).features[0].properties).toMatchObject({ display_value: "city", display_mode_share: 0.75 });
});

it("labels overview inspection with the selected evidence coverage", () => {
  expect(overviewMessage(12, "Mediaanitulot", 0.75)).toContain("Mediaanitulot-tiedon kattavuus 75 %");
  expect(overviewMessage(12, "Kokonaissopivuus", 0.75)).toContain("pisteytettyjen rakennusten osuus 75 %");
});

it("uses a short zoom hint after overview tiles load", () => {
  expect(overviewLoadedMessage()).toBe("Lähennä nähdäksesi rakennukset.");
});

it("lists criterion-group contributors in an overview inspection", () => {
  const layers = [{ layer_id: "commute", kind: "numeric" as const, finnish_label: "Aamumatka", description: "", unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }];
  const preferences = { version: 2 as const, groups: [{ id: "commute-group", operator: "and" as const, criteria: [{ id: "kamppi", layerId: "commute", preference: { enabled: true, maximum: 30, acceptedCategories: [] } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };
  expect(overviewContributors({ layer_summaries: { commute: { median: 25 } } }, layers, preferences)).toEqual(["Aamumatka: 25 min"]);
});

it("keeps overview metrics distinct from their labels", () => {
  const layers = [{ layer_id: "noise", kind: "numeric" as const, finnish_label: "Päivämelu", description: "", unit: "dB", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }];
  const preferences = { version: 2 as const, groups: [{ id: "noise", operator: "and" as const, criteria: [{ id: "noise", layerId: "noise", preference: { enabled: true, maximum: 55, acceptedCategories: [] } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };
  const result = overviewSummary({ building_count: 172, display_value: 0.62, display_coverage: 0.76, layer_summaries: { noise: { median: 54 } } }, undefined, layers, preferences);

  expect(result).toMatchObject({ title: "Alueen sopivuus", value: "62 %", statistic: "Mediaani", buildingCount: 172, coverage: 0.76, contributors: [{ label: "Päivämelu", value: "54 dB" }] });
});

it("reports a retryable local tile failure", () => {
  expect(failedTileMessage(2)).toContain("Yritä uudelleen");
});

it("keeps an overview visible at fractional zoom levels between configured integer bounds", () => {
  const tiers = [
    { minZoom: 10, maxZoom: 10, tileZoom: 10, geometryPathTemplate: "overview/1000m/tiles/10/{x}/{y}.geojson.gz", layerPathTemplate: "overview/1000m/layers/{layer_id}/10/{x}/{y}.json.gz", tileKeys: ["1/2"] },
    { minZoom: 11, maxZoom: 12, tileZoom: 11, geometryPathTemplate: "overview/500m/tiles/11/{x}/{y}.geojson.gz", layerPathTemplate: "overview/500m/layers/{layer_id}/11/{x}/{y}.json.gz", tileKeys: ["1/2"] },
    { minZoom: 13, maxZoom: 14, tileZoom: 12, geometryPathTemplate: "overview/250m/tiles/12/{x}/{y}.geojson.gz", layerPathTemplate: "overview/250m/layers/{layer_id}/12/{x}/{y}.json.gz", tileKeys: ["1/2"] },
  ];

  expect(overviewTierForZoom(tiers, 10.5)?.geometryPathTemplate).toBe("overview/1000m/tiles/10/{x}/{y}.geojson.gz");
  expect(overviewTierForZoom(tiers, 12.5)?.geometryPathTemplate).toBe("overview/500m/tiles/11/{x}/{y}.geojson.gz");
  expect(overviewTierForZoom(tiers, 14.5)?.geometryPathTemplate).toBe("overview/250m/tiles/12/{x}/{y}.geojson.gz");
  expect(overviewTilePath(tiers[0], "1/2")).toBe("overview/1000m/tiles/10/1/2.geojson.gz");
  expect(overviewLayerPath(tiers[0], "income_median_eur", "1/2")).toBe("overview/1000m/layers/income_median_eur/10/1/2.json.gz");
});

it("renders a fetched overview while still below the building zoom on the same tier", () => {
  // Regression: the post-fetch guard once bailed whenever zoom < buildingMinZoom
  // (i.e. always, in overview mode), so overview cells never drew below zoom 15.
  expect(overviewStillCurrent(12, 15, "overview/500m", "overview/500m")).toBe(true);
  // zoomed into building range during the fetch -> defer to the building render
  expect(overviewStillCurrent(15, 15, "overview/500m", "overview/500m")).toBe(false);
  // zoomed to a different overview tier during the fetch -> a re-fetch will render it
  expect(overviewStillCurrent(13, 15, "overview/500m", "overview/250m")).toBe(false);
  expect(overviewStillCurrent(12, 15, "overview/500m", undefined)).toBe(false);
});

it("loads only indexed overview tiles around the viewport", () => {
  const tier = { minZoom: 11, maxZoom: 12, tileZoom: 16, geometryPathTemplate: "overview/500m/tiles/16/{x}/{y}.geojson.gz", layerPathTemplate: "overview/500m/layers/{layer_id}/16/{x}/{y}.json.gz", tileKeys: ["37308/18969"] };
  expect(overviewTileKeys(tier, [24.94, 60.17, 24.941, 60.171])).toEqual(["37308/18969"]);
});

it("deduplicates overview cells shared by adjacent tile payloads", () => {
  const cell = { type: "Feature", properties: { cell_id: "1/2" }, geometry: { type: "Point", coordinates: [24.9, 60.2] } } as GeoJSON.Feature;
  expect(mergeOverviewTiles([{ type: "FeatureCollection", features: [cell] }, { type: "FeatureCollection", features: [cell] }]).features).toHaveLength(1);
});

it("merges only requested overview layer data with compact cell geometry", () => {
  const geometry = { type: "FeatureCollection", features: [{ type: "Feature", properties: { cell_id: "1/2", building_count: 2 }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  const overview = mergeOverviewGeometry(geometry, { income: { version: 1, cells: [{ cell_id: "1/2", state_counts: { known: 1, unknown: 1 }, summary: { median: 42000 }, score_inputs: [{ state: "known", value: 42000, values: [] }, null] }] } });
  expect(overview.features[0].properties).toMatchObject({ layer_state_counts: { income: { known: 1, unknown: 1 } }, layer_summaries: { income: { median: 42000 } }, score_inputs: [{ income: { value: 42000 } }, {}] });
});

it("does not allocate score inputs for an overview with no active layers", () => {
  const geometry = { type: "FeatureCollection", features: [{ type: "Feature", properties: { cell_id: "1/2", building_count: 500 }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  expect(mergeOverviewGeometry(geometry, {}).features[0].properties?.score_inputs).toBeUndefined();
});

it("keeps only overview cells that intersect the visible map bounds", () => {
  const overview = { type: "FeatureCollection", features: [
    { type: "Feature", properties: { cell_id: "inside" }, geometry: { type: "Polygon", coordinates: [[[24.9, 60.1], [25, 60.1], [25, 60.2], [24.9, 60.2], [24.9, 60.1]]] } },
    { type: "Feature", properties: { cell_id: "outside" }, geometry: { type: "Polygon", coordinates: [[[25.5, 60.1], [25.6, 60.1], [25.6, 60.2], [25.5, 60.2], [25.5, 60.1]]] } },
  ] } as GeoJSON.FeatureCollection;
  expect(overviewGeometryForBounds(overview, [24.95, 60.05, 25.1, 60.25]).features.map((feature) => feature.properties?.cell_id)).toEqual(["inside"]);
});

it("restores cached geometry without refetching after a zoom-tier switch", () => {
  const feature = { type: "Feature", properties: { building_id: "a" }, geometry: { type: "Point", coordinates: [24.9, 60.2] } } as GeoJSON.Feature;
  expect(mergeTileGeometry([{ type: "FeatureCollection", features: [feature] }]).features).toHaveLength(1);
});

it("selects the smallest overlapping building for an inspection", () => {
  const large = { type: "Feature", properties: { building_id: "large" }, geometry: { type: "Polygon", coordinates: [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]] } } as GeoJSON.Feature;
  const small = { type: "Feature", properties: { building_id: "small" }, geometry: { type: "Polygon", coordinates: [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]] } } as GeoJSON.Feature;
  expect(smallestBuildingFeature([large, small])?.properties?.building_id).toBe("small");
});

it("builds a geometry tile path", () => {
  expect(buildingTilePaths("37308/18969", {
    minZoom: 16,
    tileZoom: 16,
    geometryPathTemplate: "tiles/geometry/16/{x}/{y}.geojson.gz",
    coreAttributePathTemplate: "tiles/core/16/{x}/{y}.json.gz",
    layerAttributePathTemplate: "tiles/layers/{layer_id}/16/{x}/{y}.json.gz",
    layerTileKeys: {},
    bufferTiles: 1,
    tileKeys: ["37308/18969"],
  })).toEqual("tiles/geometry/16/37308/18969.geojson.gz");
});

describe("initialGeometryPartition", () => {
  it("loads the Helsinki partition without requesting the full region", () => {
    expect(
      initialGeometryPartition([
        "geometry/Espoo.geojson.gz",
        "geometry/Helsinki.geojson.gz",
        "geometry/Vantaa.geojson.gz",
      ]),
    ).toBe("geometry/Helsinki.geojson.gz");
  });

  it("reports a missing initial partition explicitly", () => {
    expect(() => initialGeometryPartition([])).toThrow("Helsinki geometry partition is missing");
  });

  it("uses the corresponding attribute partition", () => {
    expect(initialAttributePartition(["attributes/Helsinki.json.gz"])).toBe(
      "attributes/Helsinki.json.gz",
    );
  });
});

describe("scoredGeometry", () => {
  it("uses all loaded layer values for the overall view and selected layers", () => {
    const geometry = { type: "FeatureCollection", features: [{ type: "Feature", properties: { layer_values: { building_year: { state: "known" as const, value: 1970, values: [] } } }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
    const layers = [{ layer_id: "building_year", kind: "numeric" as const, finnish_label: "Rakennusvuosi", description: "", unit: null, allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }];
    const preferences = { version: 2 as const, groups: [{ id: "years", operator: "and" as const, criteria: [{ id: "year", layerId: "building_year", preference: { enabled: true, minimum: 1960, acceptedCategories: [] } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };

    expect(scoredGeometry(geometry, layers, preferences).features[0].properties?.display_status).toBe("scored");
    expect(scoredGeometry(geometry, layers, { ...preferences, selectedVisualization: "income_median_eur" }).features[0].properties?.display_status).toBe("unknown");
  });

it("uses loaded raw numeric values for an individual-layer scale and legend", () => {
    const geometry = { type: "FeatureCollection", features: [
      { type: "Feature", properties: { layer_values: { income_median_eur: { state: "known" as const, value: 30000, values: [] } } }, geometry: { type: "Point", coordinates: [24.9, 60.2] } },
      { type: "Feature", properties: { layer_values: { income_median_eur: { state: "known" as const, value: 50000, values: [] } } }, geometry: { type: "Point", coordinates: [24.91, 60.2] } },
    ] } as GeoJSON.FeatureCollection;
    const layers = [{ layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "€", allowed_categories: [], methodology: "", caveat_ids: ["postal-area-context"], source_ids: [], visualization_range: [25000, 75000] as [number, number], visualization_breaks: [30000, 40000, 50000, 60000, 70000] }];
    const preferences = { version: 2 as const, groups: [], selectedVisualization: "income_median_eur", missingDealbreakerPolicy: "pass" as const };

  expect(scoredGeometry(geometry, layers, preferences).features[0].properties?.display_value).toBe(30000);
  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences))).toContain("step");
  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences))).toContain("#475569");
  expect(visualizationLegend(geometry, layers, preferences)).toContain("25 000–75 000 €");
  expect(visualizationLegend(geometry, layers, preferences, [30000, 40000, 50000, 60000, 70000])).toContain("30 000, 40 000, 50 000, 60 000, 70 000");
  expect(visualizationLegend(geometry, layers, preferences)).toContain("Arvo kuvaa postinumeroaluetta");
  expect(visualizationLegendItems(geometry, layers, preferences).map((item) => item.label)).toContain("≤ 40 000 €");
});

it("gives every median boarding count its own map-legend class", () => {
  const geometry = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
  const layers = [{ layer_id: "transit_workplace_rautatieasema_median_boarding", kind: "numeric" as const, finnish_label: "Ajoneuvoihin nousut (mediaani)", description: "", unit: "nousua", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [0, 4] as [number, number], visualization_breaks: [0, 1, 2, 3, 4] }];
  const preferences = { version: 2 as const, groups: [], selectedVisualization: "transit_workplace_rautatieasema_median_boarding", missingDealbreakerPolicy: "pass" as const };

  expect(visualizationLegendItems(geometry, layers, preferences).map((item) => item.label)).toEqual([
    "0 nousua", "1 nousua", "2 nousua", "3 nousua", "4 nousua", "Tieto puuttuu",
  ]);
  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences))).toContain("0.5");
  expect(visualizationLegend(geometry, layers, preferences)).toContain("jokaisella nousumäärällä on oma väri");
  expect(visualizationLegendItems(geometry, [{ ...layers[0], visualization_breaks: [1, 2, 3, 4, 5] }], preferences).map((item) => item.label)).toContain("5 nousua");
});

it("uses criterion groups for map suitability", () => {
  const geometry = { type: "FeatureCollection", features: [{ type: "Feature", properties: { layer_values: { commute: { state: "known", value: 45, values: [] } } }, geometry: { type: "Point", coordinates: [24.9, 60.2] } }] } as GeoJSON.FeatureCollection;
  const layers = [{ layer_id: "commute", kind: "numeric" as const, finnish_label: "Aamumatka", description: "", unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }];
  const preferences = { version: 2 as const, groups: [{ id: "commute-group", operator: "and" as const, dealbreaker: true, criteria: [{ id: "kamppi", layerId: "commute", preference: { enabled: true, maximum: 30, acceptedCategories: [] } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };
  expect(scoredGeometry(geometry, layers, preferences).features[0].properties?.display_status).toBe("failed_dealbreaker");
});

it("uses semantic numeric scales and a fixed categorical palette", () => {
  const geometry = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
  const layers = [
    { layer_id: "grocery_walk_m", kind: "numeric" as const, finnish_label: "Kauppa", description: "", unit: "m", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [0, 5000] as [number, number] },
    { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [0, 100000] as [number, number] },
    { layer_id: "building_year", kind: "numeric" as const, finnish_label: "Rakennusvuosi", description: "", unit: null, allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [], visualization_range: [1600, 2100] as [number, number] },
    { layer_id: "land_owner_class", kind: "categorical" as const, finnish_label: "Maanomistajaluokka", description: "", unit: null, allowed_categories: ["city", "non_city", "mixed"], methodology: "", caveat_ids: [], source_ids: [] },
  ];
  const preferences = (selectedVisualization: string) => ({ version: 2 as const, groups: [], selectedVisualization, missingDealbreakerPolicy: "pass" as const });

  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences("grocery_walk_m")))).toContain("#14532d");
  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences("income_median_eur")))).toContain("#e0f2fe");
  expect(JSON.stringify(visualizationPaint(geometry, layers, preferences("building_year")))).toContain("#1e3a8a");
  expect(visualizationLegend(geometry, layers, preferences("grocery_walk_m"))).toContain("tummanvihreä = parempi");
  expect(visualizationLegendItems(geometry, layers, preferences("land_owner_class")).map((item) => item.label)).toContain("kaupunki");
});
});
