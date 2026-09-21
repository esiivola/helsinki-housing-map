import { expect, it } from "vitest";

import { availableTileKeys, fulfilledValues, retainRecentKeys, tileKeysForBounds } from "./spatial";

it("returns visible web mercator tiles with a buffer", () => {
  expect(tileKeysForBounds([24.94, 60.17, 24.941, 60.171], 16, 1)).toContain("37308/18969");
});

it("does not request an absent sparse tile", () => {
  expect(availableTileKeys(["1/2", "2/2"], new Set(["2/2"]))).toEqual(["2/2"]);
});

it("keeps only the newest bounded tile keys", () => {
  expect(retainRecentKeys(["a", "b", "c"], 2)).toEqual(["b", "c"]);
});

it("keeps successful tile loads when another tile fails", () => {
  expect(fulfilledValues([{ status: "fulfilled", value: "tile" }, { status: "rejected", reason: new Error("missing") }])).toEqual(["tile"]);
});
