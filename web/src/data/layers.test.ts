import { describe, expect, it } from "vitest";
import { commuteDestinations, commuteLayerParts, layerGroupFor, layerGroups, mapLayerOptions, transitStatisticLabel, transitStatistics } from "./layers";

describe("commuteLayerParts", () => {
  it("recognizes the published workplace layer identifiers", () => {
    expect(commuteLayerParts("bike_workplace_ruoholahti_min")).toEqual({ mode: "bike", destination: "ruoholahti", statistic: "min" });
    expect(commuteLayerParts("transit_workplace_keilaniemi_median_min")).toEqual({ mode: "transit", destination: "keilaniemi", statistic: "median" });
    expect(commuteLayerParts("transit_workplace_keilaniemi_median_boarding")).toEqual({ mode: "transit", destination: "keilaniemi", statistic: "median_boarding" });
    expect(commuteLayerParts("forest_walk_m")).toBeUndefined();
  });

  it("labels every destination-specific transit metric for the frontend selector", () => {
    expect(transitStatistics).toEqual(["min", "median", "max", "median_boarding"]);
    expect(transitStatisticLabel("median_boarding")).toBe("Ajoneuvoihin nousut (mediaani)");
  });
});

it("lists only destinations with published layers for the selected commute mode", () => {
  const layers = [
    ...["aviapolis", "kalasatama", "kamppi", "keilaniemi", "leppavaara", "myyrmaki", "pasila", "rautatieasema", "ruoholahti", "tapiola", "tikkurila"].map((destination) => ({ layer_id: `transit_workplace_${destination}_median_min` })),
    ...["aviapolis", "kalasatama", "kamppi", "keilaniemi", "leppavaara", "myyrmaki", "pasila", "rautatieasema", "ruoholahti", "tapiola", "tikkurila"].map((destination) => ({ layer_id: `bike_workplace_${destination}_min` })),
  ];

  expect(commuteDestinations(layers, "transit")).toHaveLength(11);
  expect(commuteDestinations(layers, "transit")).toContain("rautatieasema");
  expect(commuteDestinations(layers, "bike")).toHaveLength(11);
});

it("keeps the active commute layer visible in the map-layer picker", () => {
  const active = "transit_workplace_aviapolis_median_min";
  const layers = [{ layer_id: "daycare_walk_m" }, { layer_id: active }];

  expect(mapLayerOptions(layers, active).map((layer) => layer.layer_id)).toEqual([active, "daycare_walk_m"]);
});

it("assigns every selectable layer type to one Finnish picker group", () => {
  expect(layerGroups).toEqual(["Liikkuminen", "Lähipalvelut", "Ympäristö", "Asuminen ja rakennus", "Aluetiedot"]);
  expect(layerGroupFor("transit_workplace_aviapolis_median_min")).toBe("Liikkuminen");
  expect(layerGroupFor("selected_health_service_walk_m")).toBe("Lähipalvelut");
  expect(layerGroupFor("noise_night_upper_db")).toBe("Ympäristö");
  expect(layerGroupFor("heating_method")).toBe("Asuminen ja rakennus");
  expect(layerGroupFor("income_median_eur")).toBe("Aluetiedot");
});
