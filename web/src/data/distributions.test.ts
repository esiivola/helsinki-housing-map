import { expect, it } from "vitest";
import { linearHistogram, parseLayerDistributions } from "./distributions";

it("builds a dynamic histogram with the same bounded axis as static layers", () => {
  expect(linearHistogram([0, 10, 20, 30, 100], [0, 100])).toMatchObject({ knownCount: 5, min: 0, max: 100 });
  expect(linearHistogram([0, 10, 20, 30, 100], [0, 100])?.counts.reduce((total, count) => total + count, 0)).toBe(5);
});

it("parses complete static numeric distributions", () => {
  expect(parseLayerDistributions('{"version":1,"distributions":[{"layer_id":"income","counts":[2,3],"known_count":5,"min":10,"max":50}]}')).toEqual({ income: { counts: [2, 3], knownCount: 5, min: 10, max: 50 } });
});

it("accepts counts below the known population (out-of-range values dropped from the bars)", () => {
  expect(parseLayerDistributions('{"version":1,"distributions":[{"layer_id":"income","counts":[2],"known_count":5,"min":10,"max":50}]}')).toEqual({ income: { counts: [2], knownCount: 5, min: 10, max: 50 } });
});

it("rejects distributions whose counts exceed the known population", () => {
  expect(() => parseLayerDistributions('{"version":1,"distributions":[{"layer_id":"income","counts":[6],"known_count":5,"min":10,"max":50}]}')).toThrow("counts");
});

it("rejects distributions without a valid value span", () => {
  expect(() => parseLayerDistributions('{"version":1,"distributions":[{"layer_id":"income","counts":[5],"known_count":5,"max":50}]}')).toThrow("span");
});
