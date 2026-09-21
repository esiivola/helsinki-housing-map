import { expect, it } from "vitest";
import { niceTicks } from "./LayerHistogram";

it("places ticks at natural round numbers within the span", () => {
  expect(niceTicks(213, 7139)).toEqual([1000, 2000, 3000, 4000, 5000, 6000, 7000]);
  expect(niceTicks(32133, 88533)).toEqual([40000, 50000, 60000, 70000, 80000]);
  expect(niceTicks(1900, 2022)).toEqual([1900, 1920, 1940, 1960, 1980, 2000, 2020]);
});

it("returns no ticks for a degenerate span", () => {
  expect(niceTicks(50, 50)).toEqual([]);
});
