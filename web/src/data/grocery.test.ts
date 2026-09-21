import { expect, it } from "vitest";

import { selectedGroceryLayerId, withSelectedGroceryValue } from "./grocery";

const value = (state: "known" | "partial" | "unknown", metres: number | null) => ({ state, value: metres, values: [], distribution: {}, coverage: state === "unknown" ? 0 : 1, evidenceIds: ["osm"], method: "derived" as const, confidence: "medium" as const });

it("uses the minimum known distance among selected grocery-store groups", () => {
  const values = withSelectedGroceryValue({
    grocery_store_lidl_walk_m: value("known", 800),
    grocery_store_prisma_walk_m: value("known", 350),
  }, { version: 2, groups: [], selectedVisualization: selectedGroceryLayerId, missingDealbreakerPolicy: "pass", groceryStoreGroups: ["lidl", "prisma"] });

  expect(values[selectedGroceryLayerId]).toMatchObject({ state: "known", value: 350 });
});

it("keeps the composite partial when a selected store group is unavailable", () => {
  const values = withSelectedGroceryValue({
    grocery_store_lidl_walk_m: value("known", 800),
    grocery_store_prisma_walk_m: value("unknown", null),
  }, { version: 2, groups: [], selectedVisualization: selectedGroceryLayerId, missingDealbreakerPolicy: "pass", groceryStoreGroups: ["lidl", "prisma"] });

  expect(values[selectedGroceryLayerId]).toMatchObject({ state: "partial", value: 800 });
});

it("does not synthesize a value when no store group is selected", () => {
  const values = withSelectedGroceryValue({ grocery_store_lidl_walk_m: value("known", 800) }, { version: 2, groups: [], selectedVisualization: selectedGroceryLayerId, missingDealbreakerPolicy: "pass", groceryStoreGroups: [] });

  expect(values[selectedGroceryLayerId]).toMatchObject({ state: "unknown", value: null });
});
