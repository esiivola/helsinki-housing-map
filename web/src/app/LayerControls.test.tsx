import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { hasSelection, LayerControls } from "./LayerControls";

describe("LayerControls", () => {
  it("keeps layers collapsed by default and presents numeric selections as an inclusive interval", () => {
    const markup = renderToStaticMarkup(createElement(LayerControls, {
      layers: [{ layer_id: "income_median_eur", finnish_label: "Mediaanitulot", description: "", kind: "numeric", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: ["postal-area-context"], source_ids: [] }],
      preferences: { version: 1, layers: {}, selectedVisualization: "overall", missingDealbreakerPolicy: "pass" },
      onChange: () => {},
    }));

    expect(markup).toContain('class="layer-control"');
    expect(markup).toContain("Tyhjennä rajat");
    expect(markup).toContain("≤ arvo ≤");
    expect(markup).toContain("Arvo välillä (EUR)");
    expect(markup).toContain("Mediaanitulot alin arvo (EUR)");
    expect(markup).toContain("Täysi etu");
    expect(markup).toContain("Ei etua enää");
    expect(markup).toContain("Piste vähenee tasaisesti välillä");
    expect(markup).not.toContain("Lisätiedot:");
    expect(markup).toContain("0 käytössä");
    expect(markup).toContain("Lisää kriteeri");
    expect(markup).toContain("Tärkeys: tärkeä");
    expect(markup).not.toContain("Käytä pisteytyksessä");
  });

  it("groups workplace layers by trip mode and destination", () => {
    const markup = renderToStaticMarkup(createElement(LayerControls, {
      layers: ["min", "median", "max"].map((statistic) => ({ layer_id: `transit_workplace_ruoholahti_${statistic}_min`, finnish_label: `Aamumatka: Ruoholahti, ${statistic}`, description: "", kind: "numeric" as const, unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] })),
      preferences: { version: 1, layers: {}, selectedVisualization: "overall", missingDealbreakerPolicy: "pass" }, onChange: () => {},
    }));
    expect(markup).toContain("Aamumatka");
    expect(markup).toContain("Kohde: Ruoholahti");
  });
});

it("activates a layer only when its range or category selection is configured", () => {
  const numeric = { layer_id: "income_median_eur", finnish_label: "Mediaanitulot", description: "", kind: "numeric" as const, unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] };
  const categorical = { ...numeric, layer_id: "house_type", kind: "categorical" as const, allowed_categories: ["kerrostalo"] };

  expect(hasSelection(numeric, { enabled: false, acceptedCategories: [] })).toBe(false);
  expect(hasSelection(numeric, { enabled: false, minimum: 30000, acceptedCategories: [] })).toBe(true);
  expect(hasSelection(numeric, { enabled: false, acceptedCategories: [], softPreference: { direction: "lower_is_better", fullScoreAt: 15, zeroScoreAt: 35 } })).toBe(true);
  expect(hasSelection(categorical, { enabled: false, acceptedCategories: ["kerrostalo"] })).toBe(true);
});
