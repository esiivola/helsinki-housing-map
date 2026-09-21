import { describe, expect, it } from "vitest";
import { yearStatus } from "./yearStyle";

describe("yearStatus", () => {
  it("uses the documented any-match range semantics", () => {
    expect(yearStatus([1940, 1970], { enabled: true, minimum: 1960, maximum: 1980, acceptedCategories: [] })).toBe("pass");
    expect(yearStatus([1940, 1970], { enabled: true, minimum: 1950, maximum: 1960, acceptedCategories: [] })).toBe("fail");
  });
});
