import { describe, expect, it } from "vitest";

import { formatLayerNumber, formatNumber } from "./format";

describe("formatNumber", () => {
  it("groups thousands with a plain space in Finnish style", () => {
    expect(formatNumber(32400)).toBe("32 400");
  });
});

describe("formatLayerNumber", () => {
  it("renders a year without a thousands separator or rounding artefacts", () => {
    expect(formatLayerNumber("year", 1962)).toBe("1962");
  });

  it("groups other numeric units normally", () => {
    expect(formatLayerNumber("EUR", 32400)).toBe("32 400");
    expect(formatLayerNumber(null, 1500)).toBe("1 500");
  });
});
