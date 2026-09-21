import { expect, it } from "vitest";

import { educationSelection, healthSelection, withSelectedServiceValue } from "./serviceSelections";
import type { BuildingLayerValue } from "./attributes";

const value = (state: BuildingLayerValue["state"], number: number): BuildingLayerValue => ({ state, value: number, values: [], distribution: {}, coverage: 1, evidenceIds: [], method: "derived", confidence: null });

it("uses the closest selected education group and keeps partial evidence visible", () => {
  const result = withSelectedServiceValue({ education_service_daycare_walk_m: value("known", 800), education_service_primary_school_walk_m: value("partial", 300) }, educationSelection, { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", educationServiceGroups: ["daycare", "primary_school"] });

  expect(result[educationSelection.layerId]).toMatchObject({ state: "partial", value: 300, coverage: 1 });
});

it("uses the selected private healthcare group only", () => {
  const result = withSelectedServiceValue({ health_service_mehilainen_walk_m: value("known", 900), health_service_terveystalo_walk_m: value("known", 250) }, healthSelection, { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", healthServiceGroups: ["mehilainen"] });

  expect(result[healthSelection.layerId]).toMatchObject({ state: "known", value: 900 });
});

it("keeps the wellbeing-service layer as one selectable minimum across new service groups", () => {
  const result = withSelectedServiceValue({ health_service_dental_care_walk_m: value("known", 450), health_service_social_services_walk_m: value("known", 120) }, healthSelection, { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", healthServiceGroups: ["dental_care", "social_services"] });

  expect(healthSelection.label).toBe("Kävelymatka valittuihin terveys- ja sosiaalipalveluihin");
  expect(result[healthSelection.layerId]).toMatchObject({ state: "known", value: 120 });
});
