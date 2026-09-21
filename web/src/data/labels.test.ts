import { describe, expect, it } from "vitest";

import { finnishCaveat, finnishLicence, finnishMethodology, finnishSource, finnishUnit, finnishValue, unitSuffix } from "./labels";

describe("finnishValue", () => {
  it("renders canonical categorical identifiers in Finnish", () => {
    expect(finnishValue("non_city")).toBe("muu omistaja");
    expect(finnishValue("mixed")).toBe("sekoittunut");
    expect(finnishValue("city_owned")).toBe("kaupungin omistama");
    expect(finnishValue("lease_area")).toBe("vuokra-alue");
    expect(finnishValue("ground_source_heat")).toBe("maalämpö tms.");
  });

  it("renders layer caveats in Finnish", () => {
    expect(finnishCaveat("representative-weekday")).toContain("arkipäivä");
    expect(finnishCaveat("helsinki-only-building-register")).toContain("Helsingistä");
    expect(finnishCaveat("helsinki-only-noise")).toContain("Helsingistä");
    expect(finnishCaveat("local-only-data")).toContain("vain tällä koneella");
  });
});

describe("finnishLicence", () => {
  it("maps licence identifiers to readable labels", () => {
    expect(finnishLicence("CC-BY-4.0")).toBe("CC BY 4.0");
    expect(finnishLicence("ODbL-1.0")).toBe("OpenStreetMap ODbL");
    expect(finnishLicence("open")).toBe("avoin data");
  });

  it("falls back to the raw identifier for unknown licences", () => {
    expect(finnishLicence("MIT")).toBe("MIT");
  });
});

describe("finnishUnit", () => {
  it("drops the English 'year' pseudo-unit and passes real units through", () => {
    expect(finnishUnit("year")).toBe("");
    expect(finnishUnit("EUR")).toBe("EUR");
    expect(finnishUnit("min")).toBe("min");
    expect(finnishUnit(null)).toBe("");
  });

  it("only prefixes a space when a unit label remains", () => {
    expect(unitSuffix("year")).toBe("");
    expect(unitSuffix("EUR")).toBe(" EUR");
    expect(unitSuffix(null)).toBe("");
  });
});

describe("finnishMethodology", () => {
  it("translates known English methodology strings to Finnish", () => {
    expect(finnishMethodology("Direct building-record value with at-least-one-value matching.")).toBe("Suora rakennustietue, jossa vähintään yksi arvo täsmää.");
    expect(finnishMethodology("Offline cycling-network route length divided by 15 km/h.")).toContain("15 km/h");
    expect(finnishMethodology("Offline cycling-network route length divided by 15 km/h.")).not.toContain("Offline");
  });

  it("falls back to the original text for unknown methodology", () => {
    expect(finnishMethodology("Some new method.")).toBe("Some new method.");
  });
});

describe("finnishSource", () => {
  it("renders a Finnish title and description for a known source", () => {
    const summary = finnishSource("hsy_buildings", "HSY metropolitan buildings");
    expect(summary.title).toContain("Rakennukset");
    expect(summary.description).not.toBe("");
  });

  it("falls back to the source name with no description for an unknown source", () => {
    expect(finnishSource("mystery", "Mystery source")).toEqual({ title: "Mystery source", description: "" });
  });
});
