export const fixtureBuildings: GeoJSON.FeatureCollection<GeoJSON.Polygon> = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { building_id: "fixture-building-1", residential: true },
      geometry: {
        type: "Polygon",
        coordinates: [[[24.934, 60.17], [24.936, 60.17], [24.936, 60.171], [24.934, 60.171], [24.934, 60.17]]],
      },
    },
  ],
};
