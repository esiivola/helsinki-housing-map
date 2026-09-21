import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { App, AreaSummaryCard, consolidatedLicences, defaultCommuteLayerId, evaluationDetails, groupEvaluationDetails, InspectorCard, inspectorEyebrow, MapDisplayControls, mapDisplaySelectionFor, loadReconciledPreferenceSet, openGroundMessage, reconcilePreferences, renderLayerValue, returnFocusToMap, ServiceInfoModal, type SourceRecord } from "./App";
import type { BuildingLayerValue } from "../data/attributes";

const knownValue = (value: number | string): BuildingLayerValue => ({ state: "known", value, values: [], distribution: {}, coverage: 1, evidenceIds: [], method: "direct", confidence: "high" });

const sampleSources: SourceRecord[] = [
  { source_id: "hsy_buildings", name: "HSY metropolitan buildings", licence_id: "CC-BY-4.0", licence_url: "https://creativecommons.org/licenses/by/4.0/", attribution: "HSY", source_url: "https://kartta.hsy.fi/geoserver/wfs" },
  { source_id: "paavo_income", name: "Statistics Finland Paavo", licence_id: "open", licence_url: "https://stat.fi", attribution: "Tilastokeskus", source_url: "https://geo.stat.fi/geoserver/postialue/wfs" },
  { source_id: "hsl_osm_extract", name: "HSL-area OpenStreetMap extract", licence_id: "ODbL-1.0", licence_url: "https://www.openstreetmap.org/copyright", attribution: "OpenStreetMap contributors", source_url: "https://karttapalvelu.storage.hsldev.com/hsl.osm/hsl.osm.pbf" },
];

describe("App", () => {
  it("renders the Finnish map-first shell", () => {
    const markup = renderToStaticMarkup(createElement(App));

    expect(markup).toContain("Kartta");
    expect(markup).toContain('aria-label="Kartta"');
    expect(markup).toContain('aria-label="Omat kriteerit"');
    expect(markup).toContain('class="app-shell"');
  });
});

it("shows area facts as values instead of a summary sentence", () => {
  const markup = renderToStaticMarkup(createElement(AreaSummaryCard, { summary: {
    title: "Alueen sopivuus", value: "62 %", statistic: "Mediaani", buildingCount: 172, coverage: 0.76,
    contributors: [{ label: "Päivämelu", value: "54 dB" }],
  } }));

  expect(markup).toContain("62 %");
  expect(markup).toContain("<strong>172</strong> asuinrakennusta");
  expect(markup).toContain("<strong>76 %</strong> tiedoista saatavilla");
  expect(markup).toContain("Päivämelu");
  expect(markup).not.toContain("Ryhmä 1");
});

it("keeps map layers and overlays out of personal criteria", () => {
  const markup = renderToStaticMarkup(createElement(App));

  expect(markup).toContain("Lisätiedot kartalla");
  expect(markup).toContain("Omat kriteerit");
  expect(markup).not.toContain("Kartta ja kriteerit latautuvat paikallisista aineistoista.");
});

it("keeps map display selection and its dependent store controls together", () => {
  const markup = renderToStaticMarkup(createElement(MapDisplayControls, {
    layers: [{ layer_id: "selected_grocery_walk_m", finnish_label: "Kävelymatka valittuihin ruokakauppoihin", description: "", kind: "numeric", unit: "m", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }],
    distributions: {},
    preferences: { version: 2, groups: [], selectedVisualization: "selected_grocery_walk_m", missingDealbreakerPolicy: "pass" },
    onChange: () => {},
  }));

  expect(markup).toContain("Karttanäkymä");
  expect(markup).toContain("Näytettävä karttataso");
  expect(markup).toContain("Valitut ruokakaupat");
});

it("shows the distance histogram that belongs to the active store selection", () => {
  const markup = renderToStaticMarkup(createElement(MapDisplayControls, {
    layers: [{ layer_id: "selected_grocery_walk_m", finnish_label: "Kävelymatka valittuihin ruokakauppoihin", description: "", kind: "numeric", unit: "m", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }],
    distributions: {}, dynamicDistribution: { counts: [1, 2], knownCount: 3, min: 20, max: 200 },
    preferences: { version: 2, groups: [], selectedVisualization: "selected_grocery_walk_m", missingDealbreakerPolicy: "pass", groceryStoreGroups: ["prisma"] },
    onChange: () => {},
  }));

  expect(markup).toContain('aria-label="Arvojakauma: Kävelymatka valittuihin ruokakauppoihin"');
  expect(markup).toContain("3 tunnettua arvoa");
});

it("shows service checkboxes only for their active composite map layer", () => {
  expect(mapDisplaySelectionFor("overall")).toBeUndefined();
  expect(mapDisplaySelectionFor("selected_grocery_walk_m")).toBe("grocery");
  expect(mapDisplaySelectionFor("selected_education_service_walk_m")).toMatchObject({ layerId: "selected_education_service_walk_m" });
  expect(mapDisplaySelectionFor("selected_health_service_walk_m")).toMatchObject({ layerId: "selected_health_service_walk_m" });
});

it("does not require a map element when returning focus during server rendering", () => {
  expect(returnFocusToMap()).toBeUndefined();
});

it("does not claim a score for open ground", () => {
  expect(openGroundMessage()).toBe("Sopivuutta ei lasketa. Raaka-arvoja ei ole saatavilla tästä pisteestä.");
});

it("shows configured selection, score, and weight in inspector details", () => {
  const details = evaluationDetails(
    { layer_id: "income_median_eur", kind: "numeric", finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] },
    { enabled: true, minimum: 30000, maximum: 50000, weight: 2, acceptedCategories: [] },
    { configured: true, status: "pass", score: 1 },
  );

  expect(details).toContain("30 000–50 000 EUR");
  expect(details).toContain("paino 2");
});

it("flattens groups into single-criterion AND criteria and converts hard ranges to ramps", () => {
  const layers = [
    { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] },
    { layer_id: "building_year", kind: "numeric" as const, finnish_label: "Rakennusvuosi", description: "", unit: "year", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] },
  ];
  const result = reconcilePreferences({
    version: 2, selectedVisualization: "overall", missingDealbreakerPolicy: "pass",
    groups: [{ id: "g", operator: "or", weight: 3, dealbreaker: true, criteria: [
      { id: "a", layerId: "income_median_eur", preference: { enabled: true, acceptedCategories: [], minimum: 30000, maximum: 50000 } },
      { id: "b", layerId: "building_year", preference: { enabled: true, acceptedCategories: [], softPreference: { direction: "lower_is_better", fullScoreAt: 1960, zeroScoreAt: 2000 } } },
    ] }],
  }, layers);

  expect(result.groups).toHaveLength(2);
  expect(result.groups.every((group) => group.operator === "and" && group.criteria.length === 1 && group.dealbreaker === true && group.weight === 3)).toBe(true);
  expect(result.groups[0].criteria[0].preference.softPreference).toEqual({ direction: "lower_is_better", fullScoreAt: 30000, zeroScoreAt: 50000 });
  expect(result.groups[0].criteria[0].preference.minimum).toBeUndefined();
  expect(result.groups[1].criteria[0].preference.softPreference).toEqual({ direction: "lower_is_better", fullScoreAt: 1960, zeroScoreAt: 2000 });
});

it("removes retired group criteria and clears the map view when the selected layer is retired", () => {
  expect(reconcilePreferences(
    { version: 2, groups: [{ id: "commute", operator: "and", criteria: [{ id: "central", layerId: "transit_central_worst_min", preference: { enabled: true, maximum: 60, acceptedCategories: [] } }] }], selectedVisualization: "transit_central_worst_min", missingDealbreakerPolicy: "pass" },
    [{ layer_id: "transit_morning_worst_min", kind: "numeric", finnish_label: "Aamu", description: "", unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }],
  )).toMatchObject({ selectedVisualization: "none", groups: [] });
});

it("reconciles a named profile when it is loaded after the layer catalogue changes", () => {
  expect(loadReconciledPreferenceSet(
    { version: 1, activeId: "old", draft: { version: 2, groups: [], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" }, sets: [{ id: "old", name: "Vanha", updatedAt: "2026-08-31T12:00:00.000Z", preferences: { version: 2, groups: [{ id: "commute", operator: "and", criteria: [{ id: "central", layerId: "transit_central_worst_min", preference: { enabled: true, maximum: 60, acceptedCategories: [] } }] }], selectedVisualization: "transit_central_worst_min", missingDealbreakerPolicy: "pass" } }] },
    "old",
    [{ layer_id: "transit_morning_worst_min", kind: "numeric", finnish_label: "Aamu", description: "", unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] }],
  )).toMatchObject({ activeId: "old", draft: { selectedVisualization: "none", groups: [] } });
});

it("de-duplicates licences into one readable summary line", () => {
  expect(consolidatedLicences(sampleSources)).toBe("CC BY 4.0 · avoin data · OpenStreetMap ODbL");
});

it("gathers developer, sources, and licences into one service-info modal", () => {
  const markup = renderToStaticMarkup(createElement(ServiceInfoModal, {
    sources: sampleSources,
    developerHomepage: "https://esiivola.github.io",
    onClose: () => {},
  }));

  expect(markup).toContain("Tietoa palvelusta");
  expect(markup).toContain('aria-labelledby="tietoa-palvelusta-otsikko"');
  expect(markup).toContain('id="tietoa-palvelusta-otsikko"');
  expect(markup).toContain("esiivola.github.io");
  expect(markup).toContain("Rakennukset");
  expect(markup).toContain("https://kartta.hsy.fi/geoserver/wfs");
  expect(markup).toContain("CC BY 4.0 · avoin data · OpenStreetMap ODbL");
});

it("adds a selected-layer section to the service-info modal when a layer is active", () => {
  const markup = renderToStaticMarkup(createElement(ServiceInfoModal, {
    sources: sampleSources,
    selectedLayer: { layer_id: "income_median_eur", kind: "numeric", finnish_label: "Mediaanitulot", description: "Postinumeroalueen tulotaso.", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: ["postal-area-context"], source_ids: [] },
    developerHomepage: "https://esiivola.github.io",
    onClose: () => {},
  }));

  expect(markup).toContain("Valittu karttataso: Mediaanitulot");
  expect(markup).toContain("Postinumeroalueen tulotaso.");
});

it("resolves the default layer for a commute mode chosen from the Karttataso list", () => {
  const commuteLayer = (id: string) => ({ layer_id: id, kind: "numeric" as const, finnish_label: id, description: "", unit: "min", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] });
  const layers = [
    commuteLayer("transit_workplace_aviapolis_median_min"),
    commuteLayer("transit_workplace_aviapolis_min_min"),
    commuteLayer("transit_workplace_pasila_median_min"),
    commuteLayer("bike_workplace_aviapolis_effective_min"),
  ];

  expect(defaultCommuteLayerId(layers, "transit")).toBe("transit_workplace_aviapolis_median_min");
  expect(defaultCommuteLayerId(layers, "transit", "min")).toBe("transit_workplace_aviapolis_min_min");
  // Cycling now publishes only the perceived-duration layer.
  expect(defaultCommuteLayerId(layers, "bike")).toBe("bike_workplace_aviapolis_effective_min");
  expect(defaultCommuteLayerId([], "transit")).toBeUndefined();
});

it("renders a numeric layer value with its unit and a categorical one without", () => {
  const income = { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] };
  const houseType = { layer_id: "house_type", kind: "categorical" as const, finnish_label: "Talotyyppi", description: "", unit: null, allowed_categories: ["kerrostalo"], methodology: "", caveat_ids: [], source_ids: [] };

  expect(renderLayerValue(income, knownValue(32400))).toEqual({ text: "32 400", unit: " EUR", known: true });
  expect(renderLayerValue(houseType, knownValue("kerrostalo"))).toEqual({ text: "kerrostalo", unit: "", known: true });
  expect(renderLayerValue(income, undefined)).toEqual({ text: "tieto puuttuu", unit: "", known: false });
});

it("renders a building year without a thousands separator or unit", () => {
  const year = { layer_id: "building_year", kind: "numeric" as const, finnish_label: "Rakennusvuosi", description: "", unit: "year", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] };
  expect(renderLayerValue(year, knownValue(1962))).toEqual({ text: "1962", unit: "", known: true });
});

it("builds the inspector eyebrow from house type and build year", () => {
  expect(inspectorEyebrow({ years: [1962], values: { house_type: knownValue("kerrostalo") } })).toBe("kerrostalo · rakennettu 1962");
  expect(inspectorEyebrow({ years: [], values: {} })).toBe("Asuinrakennus");
});

it("leads the inspector card with the score and lists only configured and selected values", () => {
  const layers = [
    { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] },
    { layer_id: "house_type", kind: "categorical" as const, finnish_label: "Talotyyppi", description: "", unit: null, allowed_categories: ["kerrostalo"], methodology: "", caveat_ids: [], source_ids: [] },
    { layer_id: "school_walk_m", kind: "numeric" as const, finnish_label: "Kävelymatka kouluun", description: "", unit: "m", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] },
  ];
  const preferences = { version: 2 as const, selectedVisualization: "income_median_eur", missingDealbreakerPolicy: "pass" as const, groups: [{ id: "g1", operator: "and" as const, weight: 1, criteria: [{ id: "c1", layerId: "income_median_eur", preference: { enabled: true, minimum: 30000, maximum: 50000, acceptedCategories: [] } }] }] };
  const building = { id: "091-4-52-7", years: [1962], status: "arvioitu", values: { income_median_eur: knownValue(32400), house_type: knownValue("kerrostalo") } };
  const evaluation = { eligible: true, score: 0.78, failedDealbreakers: [], missingLayers: [], layers: { c1: { configured: true, status: "pass" as const, score: 1, hasMissingEvidence: false } } };

  const markup = renderToStaticMarkup(createElement(InspectorCard, { building, evaluation, layers, preferences, onOpenInfo: () => {} }));

  expect(markup).toContain("Kokonaissopivuus");
  expect(markup).toContain(">78<");
  expect(markup).toContain("Pakolliset kriteerit täyttyvät");
  expect(markup).toContain("Mediaanitulot");
  expect(markup).toContain("32 400 EUR");
  expect(markup).toContain("Tieto puuttuu 1 muusta karttatasosta.");
  expect(markup).toContain("Tietoa palvelusta");
  // the per-layer source/licence/methodology wall is gone
  expect(markup).not.toContain("Lisenssi");
  expect(markup).not.toContain("Lähde:");
});

it("shows the criterion's ramp, weight, and layer score in the inspector", () => {
  const layer = { layer_id: "income_median_eur", kind: "numeric" as const, finnish_label: "Mediaanitulot", description: "", unit: "EUR", allowed_categories: [], methodology: "", caveat_ids: [], source_ids: [] };
  const preferences = { version: 2 as const, groups: [{ id: "income", operator: "and" as const, weight: 2, criteria: [{ id: "income-ramp", layerId: "income_median_eur", preference: { enabled: true, acceptedCategories: [], softPreference: { direction: "higher_is_better" as const, fullScoreAt: 50000, zeroScoreAt: 30000 } } }] }], selectedVisualization: "overall", missingDealbreakerPolicy: "pass" as const };
  const details = groupEvaluationDetails(layer, preferences, { "income-ramp": { configured: true, status: "pass", score: 1, hasMissingEvidence: false } });
  expect(details).toContain("painoarvo 2");
  expect(details).toContain("täysi 50 000 EUR → nolla 30 000 EUR");
});
