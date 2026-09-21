import { describe, expect, it } from "vitest";

import { fixtureBuildings } from "./buildings";

describe("fixtureBuildings", () => {
  it("contains only explicitly residential fixture features", () => {
    expect(fixtureBuildings.features).toHaveLength(1);
    expect(fixtureBuildings.features[0].properties?.residential).toBe(true);
  });
});
