import { createRoot } from "react-dom/client";
import { createElement, Fragment, lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";

import { CriteriaControls } from "./CriteriaControls";
import { deletePreferenceSet, duplicatePreferenceSet, isActivePreferenceSetDirty, loadPreferenceSet, newSavedPreferenceSets, renamePreferenceSet, restoreSavedPreferenceSets, saveActivePreferenceSet, saveAsPreferenceSet, serializeSavedPreferenceSets, updateDraft, type SavedPreferenceSets } from "./preferences";
import { commuteDestinations, commuteLayerParts, layerGroupFor, layerGroups, parseLayers, transitStatisticLabel, transitStatistics, type LayerMetadata } from "../data/layers";
import { linearHistogram, parseLayerDistributions, type LayerDistribution, type LayerDistributions } from "../data/distributions";
import { LayerHistogram } from "./LayerHistogram";
import { finnishCaveat, finnishLicence, finnishMethodology, finnishSource, finnishValue, unitSuffix } from "../data/labels";
import { formatLayerNumber, formatNumber } from "../data/format";
import type { BuildingLayerValue } from "../data/attributes";
import type { AppPreferences, BuildingEvaluation, Criterion, CriterionGroup, LayerEvaluation, LayerPreference } from "../types/scoring";
import { evaluateBuildingGroups } from "../scoring/evaluate";
import { groceryStoreGroups, selectedGroceryLayerId, selectedGroceryGroups, withSelectedGroceryLayer, withSelectedGroceryValue } from "../data/grocery";
import { selectionForLayerId, selectedServiceGroups, type ServiceSelection, withSelectedServiceLayers, withSelectedServiceValues } from "../data/serviceSelections";
import { buildingLayerValues, type AttributePartition } from "../data/attributes";
import { loadGzipJson } from "../data/gzip";
import { parseManifest } from "../data/manifest";
import type { OverviewSummary } from "../map/MapView";
import "./app.css";

const savedSettingsKey = "helsinki-housing-map-saved-settings";
const developerHomepage = "https://esiivola.github.io";
const MapView = lazy(() => import("../map/MapView").then((module) => ({ default: module.MapView })));
const suitabilityHistogramLayer: LayerMetadata = { layer_id: "overall", finnish_label: "Sopivuus", description: "Kokonaissopivuuden jakauma kaikissa pisteytettävissä rakennuksissa.", kind: "numeric", unit: "%", allowed_categories: [], methodology: "Nykyisillä asetuksilla laskettu kokonaissopivuus.", caveat_ids: [], source_ids: [], visualization_breaks: [0, 20, 40, 60, 80, 100] };

export type SourceRecord = { source_id: string; name: string; licence_id: string; licence_url: string; attribution: string; source_url: string; coverage?: string };

export function App() {
  const [layers, setLayers] = useState<LayerMetadata[]>([]);
  const [distributions, setDistributions] = useState<LayerDistributions>({});
  const [dynamicDistribution, setDynamicDistribution] = useState<LayerDistribution>();
  const allBuildingValues = useRef<Promise<readonly Record<string, BuildingLayerValue>[]> | null>(null);
  const [selected, setSelected] = useState<{ id: string; years: readonly number[]; status: string; values: Record<string, BuildingLayerValue> } | null>(null);
  const [pointMessage, setPointMessage] = useState<string | null>(null);
  const [areaSummary, setAreaSummary] = useState<OverviewSummary | null>(null);
  const [sources, setSources] = useState<Record<string, SourceRecord>>({});
  const [sourceIds, setSourceIds] = useState<readonly string[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [activePlansOverlay, setActivePlansOverlay] = useState(false);
  const [mainCycleRoutesOverlay, setMainCycleRoutesOverlay] = useState(false);
  const inspectorHeading = useRef<HTMLHeadingElement>(null);
  const settingsDialog = useRef<HTMLElement>(null);
  const settingsButton = useRef<HTMLButtonElement>(null);
  const infoDialog = useRef<HTMLElement>(null);
  const infoButton = useRef<HTMLButtonElement>(null);
  const infoOpener = useRef<HTMLElement>(null);
  const [savedSettings, setSavedSettings] = useState(() => {
    if (!storageAvailable()) return newSavedPreferenceSets();
    return restoreSavedPreferenceSets(localStorage.getItem(savedSettingsKey) ?? "")
      ?? newSavedPreferenceSets();
  });
  const preferences = savedSettings.draft;
  const selectedLayer = layers.find((layer) => layer.layer_id === preferences.selectedVisualization);
  const setPreferences = (next: AppPreferences) => setSavedSettings((current) => updateDraft(current, next));
  const closeSettings = useCallback(() => setSettingsOpen(false), []);
  const closeInfo = useCallback(() => setInfoOpen(false), []);
  const openInfo = useCallback(() => {
    infoOpener.current = document.activeElement instanceof HTMLElement ? document.activeElement : infoButton.current;
    setInfoOpen(true);
  }, []);

  useModalKeyboard(settingsOpen, settingsDialog, settingsButton, closeSettings);
  useModalKeyboard(infoOpen, infoDialog, infoOpener, closeInfo);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/layers.json`)
      .then((response) => response.text())
      .then(parseLayers)
      .then((definitions) => {
        const available = withSelectedServiceLayers(withSelectedGroceryLayer(definitions));
        setLayers(available);
        setSavedSettings((current) => updateDraft(current, reconcilePreferences(current.draft, available)));
      })
      .catch(() => setLayers([]));
  }, []);
  useEffect(() => {
    const selection = mapDisplaySelectionFor(preferences.selectedVisualization);
    const needsDynamicDistribution = preferences.selectedVisualization === "overall" || selection !== undefined;
    if (!needsDynamicDistribution) {
      setDynamicDistribution(undefined);
      return;
    }
    let cancelled = false;
    if (!allBuildingValues.current) allBuildingValues.current = loadAllBuildingValues();
    void allBuildingValues.current.then((values) => {
      const selectedValues = values.map((value) => withSelectedServiceValues(withSelectedGroceryValue(value, preferences), preferences));
      const histogram = preferences.selectedVisualization === "overall"
        ? linearHistogram(selectedValues.flatMap((value) => {
          const evaluation = evaluateBuildingGroups(value, layers.map((layer) => ({ id: layer.layer_id, kind: layer.kind })), preferences.groups, preferences.missingDealbreakerPolicy);
          return evaluation.eligible && evaluation.score !== null ? [evaluation.score * 100] : [];
        }), [0, 100])
        : linearHistogram(selectedValues.flatMap((value) => {
          const selected = value[preferences.selectedVisualization];
          return (selected?.state === "known" || selected?.state === "partial") && typeof selected.value === "number" ? [selected.value] : [];
        }));
      if (!cancelled) setDynamicDistribution(histogram);
    }).catch(() => {
      if (!cancelled) setDynamicDistribution(undefined);
    });
    return () => { cancelled = true; };
  }, [layers, preferences]);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/layer-distributions.json`)
      .then((response) => response.text())
      .then(parseLayerDistributions)
      .then(setDistributions)
      .catch(() => setDistributions({}));
  }, []);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/sources.json`).then((response) => response.json()).then((items: SourceRecord[]) => { setSources(Object.fromEntries(items.map((item) => [item.source_id, item]))); setSourceIds(items.map((item) => item.source_id)); }).catch(() => { setSources({}); setSourceIds([]); });
  }, []);

  useEffect(() => {
    if (storageAvailable()) localStorage.setItem(savedSettingsKey, serializeSavedPreferenceSets(savedSettings));
  }, [savedSettings]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (infoOpen) { setInfoOpen(false); return; }
      const inspectorWasOpen = selected !== null || pointMessage !== null || areaSummary !== null;
      setSelected(null);
      setPointMessage(null); setAreaSummary(null);
      if (inspectorWasOpen) returnFocusToMap();
    };
    addEventListener("keydown", close);
    return () => removeEventListener("keydown", close);
  }, [areaSummary, pointMessage, selected, infoOpen]);
  useEffect(() => {
    if (selected) inspectorHeading.current?.focus();
  }, [selected]);
  const evaluation = selected && evaluateBuildingGroups(selected.values as Record<string, { state: "known" | "partial" | "unknown" | "conflict"; value: number | string | null; values: readonly (number | string)[] }>, layers.map((layer) => ({ id: layer.layer_id, kind: layer.kind })), preferences.groups, preferences.missingDealbreakerPolicy);
  const dismissInspector = () => {
    setSelected(null);
    setPointMessage(null);
    setAreaSummary(null);
    returnFocusToMap();
  };
  const activeSet = savedSettings.sets.find((set) => set.id === savedSettings.activeId);
  const profileDirty = isActivePreferenceSetDirty(savedSettings);
  const askForName = (message: string, initial = ""): string | null => {
    const name = typeof window === "undefined" ? null : window.prompt(message, initial);
    return name?.trim() || null;
  };
  const makeId = () => typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `profile-${Date.now()}`;

  return createElement(
    "main",
    { className: "app-shell" },
    createElement("details", { className: "map-menu" },
      createElement("summary", null,
        createElement("span", null, "Kartta"),
        createElement("strong", null, selectedLayer?.finnish_label ?? (preferences.selectedVisualization === "overall" ? "Sopivuus" : "Ei teemaa")),
      ),
      createElement("div", { className: "map-menu-content" },
        createElement(MapDisplayControls, { layers, distributions, dynamicDistribution, preferences, onChange: setPreferences }),
        createElement("details", { className: "map-overlays" },
          createElement("summary", null, "Lisätiedot kartalla"),
          createElement("label", null, createElement("input", { type: "checkbox", checked: activePlansOverlay, onChange: (event: ChangeEvent<HTMLInputElement>) => setActivePlansOverlay(event.target.checked) }), " Asemakaavamuutokset"),
          createElement("label", null, createElement("input", { type: "checkbox", checked: mainCycleRoutesOverlay, onChange: (event: ChangeEvent<HTMLInputElement>) => setMainCycleRoutesOverlay(event.target.checked) }), " Helsingin pääpyöräreitit"),
        ),
      ),
    ),
    createElement("button", {
      type: "button",
      className: "settings-ribbon",
      "aria-label": "Omat kriteerit",
      "aria-expanded": settingsOpen,
      "aria-controls": "asetukset-paneeli",
      ref: settingsButton,
      onClick: () => setSettingsOpen((open) => !open),
    }, `Kriteerit${preferences.groups.length ? ` (${preferences.groups.length})` : ""}`),
    settingsOpen && createElement("div", { className: "settings-backdrop", onClick: closeSettings },
    createElement("aside", { id: "asetukset-paneeli", className: "controls-panel", role: "dialog", "aria-modal": true, "aria-labelledby": "asetukset-otsikko", ref: settingsDialog, onClick: (event: { stopPropagation: () => void }) => event.stopPropagation() },
      createElement("div", { className: "controls-heading" },
        createElement("h2", { id: "asetukset-otsikko" }, "Omat kriteerit"),
        createElement("button", { type: "button", "data-dialog-initial-focus": true, onClick: closeSettings }, "Sulje"),
      ),
      createElement("section", { className: "settings-profiles", "aria-label": "Tallennetut asetukset" },
        createElement("label", null, "Asetusprofiili", createElement("select", {
          value: savedSettings.activeId ?? "",
          onChange: (event: ChangeEvent<HTMLSelectElement>) => setSavedSettings((current) => event.target.value ? loadReconciledPreferenceSet(current, event.target.value, layers) : { ...current, activeId: null }),
        }, createElement("option", { value: "" }, "Ei tallennettua profiilia"), ...savedSettings.sets.map((set) => createElement("option", { key: set.id, value: set.id }, set.name)))),
        activeSet && createElement("p", null, `${activeSet.name}${profileDirty ? " — Muokattu" : ""}`),
        createElement("div", { className: "profile-actions" },
          createElement("button", { type: "button", disabled: !activeSet, onClick: () => setSavedSettings((current) => saveActivePreferenceSet(current, new Date().toISOString())) }, "Tallenna"),
          createElement("button", { type: "button", onClick: () => { const name = askForName("Uuden asetussarjan nimi"); if (name) setSavedSettings((current) => saveAsPreferenceSet(current, name, makeId(), new Date().toISOString())); } }, "Tallenna uutena…"),
          activeSet && createElement("details", { className: "profile-overflow" }, createElement("summary", null, "Lisää"),
            createElement("button", { type: "button", onClick: () => { const name = askForName("Asetussarjan uusi nimi", activeSet.name); if (name) setSavedSettings((current) => renamePreferenceSet(current, activeSet.id, name, new Date().toISOString())); } }, "Nimeä uudelleen"),
            createElement("button", { type: "button", onClick: () => { const name = askForName("Kopioidun asetussarjan nimi", `${activeSet.name} (kopio)`); if (name) setSavedSettings((current) => duplicatePreferenceSet(current, activeSet.id, name, makeId(), new Date().toISOString())); } }, "Monista"),
            createElement("button", { type: "button", onClick: () => setSavedSettings((current) => deletePreferenceSet(current, activeSet.id)) }, "Poista"),
          ),
        ),
      ),
      createElement("label", { className: "missing-policy" }, createElement(
        "input",
        {
          type: "checkbox",
          checked: preferences.missingDealbreakerPolicy === "fail",
          onChange: (event: ChangeEvent<HTMLInputElement>) => setPreferences({
            ...preferences,
            missingDealbreakerPolicy: event.target.checked ? "fail" : "pass",
          }),
        },
      ), "Älä hyväksy rakennusta, jos pakollisen vaatimuksen tieto puuttuu"),
      createElement(CriteriaControls, { layers, distributions, preferences, onChange: setPreferences }),
    )),
    createElement("section", { className: "map-panel", "aria-label": "Kartta" },
      createElement("h2", { className: "sr-only" }, "Kartta"),
      createElement("p", { className: "sr-only" }, "Asuinrakennukset ladataan paikallisista staattisista tiedostoista."),
      createElement(Suspense, { fallback: createElement("p", { role: "status" }, "Karttaa ladataan…") }, createElement(MapView, {
        layers,
        preferences,
        activePlansOverlay,
        mainCycleRoutesOverlay,
        onSelect: (building) => { setSelected(building); setPointMessage(null); setAreaSummary(null); },
        onOpenGround: () => { setSelected(null); setAreaSummary(null); setPointMessage(openGroundMessage()); },
        onAreaSummary: (summary) => { setSelected(null); setPointMessage(null); setAreaSummary(summary); },
      })),
      selected && createElement("aside", { className: "inspector-panel", "aria-label": "Rakennuksen tiedot" },
        createElement("div", { className: "inspector-heading" },
          createElement("h2", { ref: inspectorHeading, tabIndex: -1 }, "Rakennuksen tiedot"),
          createElement("button", { type: "button", onClick: dismissInspector }, "Sulje"),
        ),
        createElement(InspectorCard, { building: selected, evaluation: evaluation || null, layers, preferences, onOpenInfo: openInfo }),
      ),
      pointMessage && createElement("aside", { className: "inspector-panel", "aria-label": "Karttapisteen tiedot" },
        createElement("div", { className: "inspector-heading" },
          createElement("h2", null, "Ei asuinrakennusta"),
          createElement("button", { type: "button", onClick: dismissInspector }, "Sulje"),
        ),
        createElement("p", null, pointMessage),
      ),
      areaSummary && createElement("aside", { className: "inspector-panel", "aria-label": "Alueyhteenvedon tiedot" },
        createElement("div", { className: "inspector-heading" }, createElement("h2", null, areaSummary.title), createElement("button", { type: "button", onClick: dismissInspector }, "Sulje")),
        createElement(AreaSummaryCard, { summary: areaSummary }),
      ),
      createElement("button", {
        type: "button",
        className: "map-info-button",
        "aria-label": "Tietoa palvelusta ja tietolähteistä",
        "aria-expanded": infoOpen,
        ref: infoButton,
        onClick: openInfo,
      }, "i"),
      infoOpen && createElement(ServiceInfoModal, {
        sources: sourceIds.map((id) => sources[id]).filter(Boolean),
        selectedLayer,
        developerHomepage,
        dialogRef: infoDialog,
        onClose: closeInfo,
      }),
    ),
  );
}

export function AreaSummaryCard({ summary }: { summary: OverviewSummary }) {
  return createElement(Fragment, null,
    createElement("div", { className: "inspector-summary" },
      createElement("p", { className: "inspector-eyebrow" }, summary.statistic),
      createElement("div", { className: "inspector-hero" },
        createElement("span", { className: "cap" }, "Valittu arvo"),
        createElement("span", { className: summary.value ? "num" : "num muted" }, summary.value ?? "tieto puuttuu"),
      ),
      createElement("div", { className: "area-facts" },
        createElement("span", null, createElement("strong", null, summary.buildingCount.toLocaleString("fi-FI")), " asuinrakennusta"),
        createElement("span", null, createElement("strong", null, `${Math.round(summary.coverage * 100)} %`), " tiedoista saatavilla"),
      ),
    ),
    createElement("h3", { className: "area-contributors-heading" }, "Kriteerisi"),
    summary.contributors.length
      ? createElement("dl", { className: "inspector-values" }, ...summary.contributors.map((item) => createElement("div", { className: "row", key: item.label }, createElement("dt", null, item.label), createElement("dd", null, item.value))))
      : createElement("p", { className: "inspector-hint" }, "Et ole asettanut kriteerejä."),
  );
}

export function MapDisplayControls({ layers, distributions, dynamicDistribution, preferences, onChange }: { layers: readonly LayerMetadata[]; distributions: LayerDistributions; dynamicDistribution?: LayerDistribution; preferences: AppPreferences; onChange(next: AppPreferences): void }) {
  const selectedCommute = commuteLayerParts(preferences.selectedVisualization);
  const selectedLayer = layers.find((layer) => layer.layer_id === preferences.selectedVisualization);
  const commuteModes = (["transit", "bike"] as const).filter((mode) => commuteDestinations(layers, mode).length > 0);
  const selectedCommuteDestinations = selectedCommute ? commuteDestinations(layers, selectedCommute.mode) : [];
  const normalLayers = layers.filter((layer) => layer.visible !== false && !commuteLayerParts(layer.layer_id));
  const dependentSelection = mapDisplaySelectionFor(preferences.selectedVisualization);
  const commuteModeLabel = { transit: "Aamumatka", bike: "Pyörämatka" } as const;
  return createElement("section", { className: "map-display-controls", "aria-label": "Karttanäkymän asetukset" },
    createElement("h3", null, "Karttanäkymä"),
    createElement("label", null, "Näytettävä karttataso", createElement(
      "select",
      { value: selectedCommute ? `mode:${selectedCommute.mode}` : preferences.selectedVisualization, onChange: (event: ChangeEvent<HTMLSelectElement>) => { const value = event.target.value; if (value.startsWith("mode:")) { const layerId = defaultCommuteLayerId(layers, value.slice(5) as "transit" | "bike"); if (layerId) onChange({ ...preferences, selectedVisualization: layerId }); } else onChange({ ...preferences, selectedVisualization: value }); } },
      createElement("option", { value: "none" }, "Ei karttatasoa"),
      createElement("option", { value: "overall" }, "Sopivuus"),
      ...layerGroups.map((group) => {
        const options = [
          ...normalLayers.filter((layer) => layerGroupFor(layer.layer_id) === group).map((layer) => createElement("option", { key: layer.layer_id, value: layer.layer_id }, layer.finnish_label)),
          ...(group === "Liikkuminen" ? commuteModes.map((mode) => createElement("option", { key: mode, value: `mode:${mode}` }, commuteModeLabel[mode])) : []),
        ];
        return options.length ? createElement("optgroup", { key: group, label: group }, ...options) : null;
      }),
    )),
    selectedCommute && createElement("label", null, "Kohde", createElement(
      "select",
      { value: selectedCommute.destination, onChange: (event: ChangeEvent<HTMLSelectElement>) => { const layer = layers.find((item) => { const parts = commuteLayerParts(item.layer_id); return parts?.mode === selectedCommute.mode && parts.destination === event.target.value && (parts.statistic === selectedCommute.statistic || selectedCommute.mode === "bike"); }); if (layer) onChange({ ...preferences, selectedVisualization: layer.layer_id }); } },
      ...selectedCommuteDestinations.map((destination) => createElement("option", { key: destination, value: destination }, layers.find((layer) => { const parts = commuteLayerParts(layer.layer_id); return parts?.mode === selectedCommute.mode && parts.destination === destination; })?.finnish_label.split(": ")[1]?.split(",")[0] ?? destination)),
    )),
    selectedCommute?.mode === "transit" && createElement("label", null, "Arvo", createElement(
      "select",
      { value: selectedCommute.statistic, onChange: (event: ChangeEvent<HTMLSelectElement>) => { const layer = layers.find((item) => { const parts = commuteLayerParts(item.layer_id); return parts?.mode === selectedCommute.mode && parts.destination === selectedCommute.destination && parts.statistic === event.target.value; }); if (layer) onChange({ ...preferences, selectedVisualization: layer.layer_id }); } },
      ...transitStatistics.map((statistic) => createElement("option", { key: statistic, value: statistic }, transitStatisticLabel(statistic))),
    )),
    (selectedLayer?.kind === "numeric" || preferences.selectedVisualization === "overall") && createElement(LayerHistogram, { layer: preferences.selectedVisualization === "overall" ? suitabilityHistogramLayer : selectedLayer, distributions, distribution: dynamicDistribution }),
    (preferences.selectedVisualization === "overall" || dependentSelection !== undefined) && !dynamicDistribution && createElement("small", { className: "histogram-loading" }, "Lasketaan jakaumaa kaikista rakennuksista…"),
    dependentSelection === "grocery" ? createElement(GroceryStoreSelection, { preferences, onChange }) : dependentSelection ? createElement(ServiceSelectionControls, { selection: dependentSelection, preferences, onChange }) : null,
    (preferences.selectedVisualization === "overall" || selectedLayer?.kind === "numeric") && createElement("label", { className: "overview-aggregation" }, "Arvo karttaruudussa", createElement(
      "select",
      { value: preferences.overviewAggregation ?? "median", onChange: (event: ChangeEvent<HTMLSelectElement>) => onChange({ ...preferences, overviewAggregation: event.target.value as AppPreferences["overviewAggregation"] }) },
      createElement("option", { value: "min" }, "Pienin arvo"),
      createElement("option", { value: "median" }, "Mediaani"),
      createElement("option", { value: "max" }, "Suurin arvo"),
    )),
  );
}

async function loadAllBuildingValues(): Promise<readonly Record<string, BuildingLayerValue>[]> {
  const manifestResponse = await fetch(`${import.meta.env.BASE_URL}data/manifest.json`);
  if (!manifestResponse.ok) throw new Error("Static data manifest request failed");
  const manifest = parseManifest(await manifestResponse.text());
  if (manifest.scoreHistogramInputs) {
    const inputs = await loadGzipJson<ScoreHistogramInputs>(`${import.meta.env.BASE_URL}data/${manifest.scoreHistogramInputs}`);
    if (inputs.version !== 1 || !Array.isArray(inputs.building_values)) throw new Error("Invalid score histogram inputs");
    return inputs.building_values.map((values) => (
      Object.fromEntries(Object.entries(values).map(([layerId, value]) => [layerId, {
        state: value.state,
        value: value.value,
        values: value.values,
        distribution: {}, coverage: value.state === "unknown" ? 0 : 1,
        evidenceIds: [], method: "derived", confidence: null,
      }])) as Record<string, BuildingLayerValue>
    ));
  }
  const partitions = await Promise.all(manifest.attributePartitions.map((path) => loadGzipJson<AttributePartition>(`${import.meta.env.BASE_URL}data/${path}`)));
  return partitions.flatMap((partition) => [...buildingLayerValues(partition).values()]);
}

type ScoreHistogramInputs = {
  version: number;
  building_values: Array<Record<string, Pick<BuildingLayerValue, "state" | "value" | "values">>>;
};

export function mapDisplaySelectionFor(layerId: string): ServiceSelection | "grocery" | undefined {
  return layerId === selectedGroceryLayerId ? "grocery" : selectionForLayerId(layerId);
}

export function consolidatedLicences(sources: readonly SourceRecord[]): string {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const source of sources) {
    const label = finnishLicence(source.licence_id);
    if (seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
  }
  return labels.join(" · ");
}

export function ServiceInfoModal({ sources, selectedLayer, developerHomepage, dialogRef, onClose }: { sources: readonly SourceRecord[]; selectedLayer?: LayerMetadata; developerHomepage: string; dialogRef?: RefObject<HTMLElement | null>; onClose: () => void }) {
  const developerLabel = developerHomepage.replace(/^https?:\/\//, "");
  return createElement("div", { className: "info-backdrop", onClick: onClose },
    createElement("aside", { className: "info-modal", role: "dialog", "aria-modal": true, "aria-labelledby": "tietoa-palvelusta-otsikko", ref: dialogRef, onClick: (event: { stopPropagation: () => void }) => event.stopPropagation() },
      createElement("div", { className: "info-heading" },
        createElement("h2", { id: "tietoa-palvelusta-otsikko" }, "Tietoa palvelusta"),
        createElement("button", { type: "button", "data-dialog-initial-focus": true, onClick: onClose }, "Sulje"),
      ),
      createElement("p", { className: "info-developer" },
        "Sivuston tekijän kotisivut: ",
        createElement("a", { href: developerHomepage, target: "_blank", rel: "noreferrer" }, `${developerLabel} ↗`),
      ),
      createElement("p", { className: "info-service" }, "Helsingin seudun asuinpaikkakartta auttaa vertailemaan rakennusten sijaintia omien kriteeriesi mukaan."),
      createElement("p", { className: "info-disclaimer" }, "Palvelu kokoaa avoimet aineistot yhteen näkymään asuinpaikan sopivuuden vertailuun. Tiedot voivat olla puutteellisia tai vanhentuneita, eivätkä korvaa virallista omistus- tai kaavaselvitystä."),
      selectedLayer ? createElement("section", { className: "info-current", "aria-label": "Valittu karttataso" },
        createElement("h3", null, `Valittu karttataso: ${selectedLayer.finnish_label}`),
        selectedLayer.description ? createElement("p", null, selectedLayer.description) : null,
        selectedLayer.methodology ? createElement("p", null, `Menetelmä: ${finnishMethodology(selectedLayer.methodology)}`) : null,
        ...selectedLayer.caveat_ids.map((caveat) => createElement("p", { key: caveat, className: "info-caveat" }, finnishCaveat(caveat))),
      ) : null,
      createElement("h3", { className: "info-sources-heading" }, "Tietolähteet"),
      createElement("ul", { className: "info-sources" },
        ...sources.map((source) => {
          const summary = finnishSource(source.source_id, source.name);
          return createElement("li", { key: source.source_id },
            createElement("div", { className: "info-source-text" },
              createElement("strong", null, summary.title),
              summary.description ? createElement("p", null, summary.description) : null,
            ),
            createElement("a", { className: "info-source-link", href: source.source_url, target: "_blank", rel: "noreferrer", "aria-label": `Avaa lähde: ${summary.title}` }, "↗"),
          );
        }),
      ),
      createElement("p", { className: "info-licences" }, sources.length ? consolidatedLicences(sources) : "Lähteitä ladataan…"),
    ),
  );
}

function useModalKeyboard(open: boolean, dialogRef: RefObject<HTMLElement | null>, openerRef: RefObject<HTMLElement | null>, onClose: () => void): void {
  useLayoutEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = () => [...dialog.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')];
    const initialFocus = dialog.querySelector<HTMLElement>("[data-dialog-initial-focus]") ?? focusable()[0];
    initialFocus?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); dialog.focus(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    addEventListener("keydown", handleKeyDown);
    return () => {
      removeEventListener("keydown", handleKeyDown);
      openerRef.current?.focus();
    };
  }, [dialogRef, onClose, open, openerRef]);
}

export function InspectorCard({ building, evaluation, layers, preferences, onOpenInfo }: { building: { id: string; years: readonly number[]; status: string; values: Record<string, BuildingLayerValue> }; evaluation: BuildingEvaluation | null; layers: readonly LayerMetadata[]; preferences: AppPreferences; onOpenInfo: () => void }) {
  const configuredLayerIds = preferences.groups.flatMap((group) => group.criteria.map((criterion) => criterion.layerId));
  const inspectorLayerIds = [...new Set([...(preferences.selectedVisualization === "overall" ? [] : [preferences.selectedVisualization]), ...configuredLayerIds])].filter((id) => layers.some((layer) => layer.layer_id === id));
  const knownLayers = layers.filter((layer) => layer.visible !== false && (() => { const value = building.values[layer.layer_id]; return value && value.state !== "unknown"; })());
  return createElement(Fragment, null,
    createElement("div", { className: "inspector-summary" },
      createElement("p", { className: "inspector-eyebrow" }, inspectorEyebrow(building)),
      createElement("div", { className: "inspector-hero" },
        createElement("span", { className: "cap" }, "Kokonaissopivuus"),
        evaluation && evaluation.score !== null
          ? createElement("span", { className: "val" }, createElement("span", { className: "num" }, `${Math.round(evaluation.score * 100)}`), createElement("span", { className: "unit" }, "%"))
          : createElement("span", { className: "num muted" }, "ei pisteytettävää näyttöä"),
      ),
      createElement("div", { className: "inspector-chips" },
        createElement("span", { className: evaluation?.eligible ? "chip chip-pass" : "chip chip-fail" }, evaluation?.eligible ? "Pakolliset kriteerit täyttyvät" : `Pakollinen kriteeri ei täyty: ${criterionLabels(preferences, layers, evaluation ? evaluation.failedDealbreakers : [])}`),
        evaluation?.missingLayers.length ? createElement("span", { className: "chip chip-part" }, `Osittainen tieto: ${criterionLabels(preferences, layers, evaluation.missingLayers)}`) : null,
      ),
      inspectorLayerIds.length
        ? createElement("dl", { className: "inspector-values" },
            ...inspectorLayerIds.flatMap((layerId) => {
              const layer = layers.find((item) => item.layer_id === layerId);
              if (!layer) return [];
              const value = building.values[layerId];
              const rendered = renderLayerValue(layer, value);
              const stateChip = value?.state === "partial" ? "osittainen" : value?.state === "conflict" ? "ristiriita" : null;
              return [createElement("div", { className: "row", key: layerId },
                createElement("dt", null, layer.finnish_label),
                createElement("dd", null,
                  rendered.known ? `${rendered.text}${rendered.unit}` : createElement("span", { className: "miss" }, "tieto puuttuu"),
                  stateChip ? createElement("span", { className: "chip chip-part" }, stateChip) : null,
                ),
              )];
            }),
          )
        : createElement("p", { className: "inspector-hint" }, "Lisää kriteerejä asetuksista, niin näet rakennuksen omat arvot tässä."),
    ),
    createElement("details", { className: "inspector-evidence" },
      createElement("summary", null, "Raaka-arvot ja tietojen laatu"),
      createElement("div", null,
        createElement("p", null, building.years.length ? `Rakennusvuodet: ${building.years.join(", ")}` : "Rakennusvuosi: tuntematon"),
        createElement("p", null, `Rakennusvuoden arvio: ${building.status}`),
        createElement("p", { className: "inspector-id" }, `Tunnus: ${building.id}`),
        ...knownLayers.map((layer) => {
          const value = building.values[layer.layer_id]!;
          const rendered = renderLayerValue(layer, value);
          const distribution = Object.keys(value.distribution).length ? `; osuudet: ${Object.entries(value.distribution).map(([category, share]) => `${finnishValue(category)} ${formatNumber(share * 100)} %`).join(", ")}` : "";
          const detail = configuredLayerIds.includes(layer.layer_id) ? groupEvaluationDetails(layer, preferences, evaluation ? evaluation.layers : undefined) : "";
          return createElement("p", { key: layer.layer_id }, `${layer.finnish_label}: ${rendered.text}${rendered.unit} (${value.state}; kattavuus ${Math.round(value.coverage * 100)} %; luottamus ${value.confidence ?? "tuntematon"})${distribution}${detail}`);
        }),
        layers.length - knownLayers.length > 0 ? createElement("p", { className: "inspector-missing" }, `Tieto puuttuu ${layers.length - knownLayers.length} muusta karttatasosta.`) : null,
        createElement("p", { className: "inspector-provenance" }, "Lähteet, lisenssit ja menetelmät: ", createElement("button", { type: "button", className: "inspector-link", onClick: onOpenInfo }, "Tietoa palvelusta")),
        createElement("p", null, "Tontin hallinta ja maanomistaja ovat lähdenäyttöön perustuvia eivätkä virallinen omistusoikeusselvitys."),
      ),
    ),
  );
}

function GroceryStoreSelection({ preferences, onChange }: { preferences: AppPreferences; onChange(next: AppPreferences): void }) {
  const selected = selectedGroceryGroups(preferences);
  return createElement("fieldset", { className: "grocery-store-selection" },
    createElement("legend", null, "Valitut ruokakaupat"),
    createElement("p", null, "Kartalla ja kriteerissä käytetään lyhintä kävelymatkaa valitsemiisi kauppoihin."),
    ...groceryStoreGroups.map(([id, label]) => createElement("label", { key: id }, createElement("input", { type: "checkbox", checked: selected.includes(id), onChange: (event: ChangeEvent<HTMLInputElement>) => { const groceryStoreGroups = event.target.checked ? [...selected, id] : selected.filter((item) => item !== id); onChange({ ...preferences, groceryStoreGroups, groups: groceryStoreGroups.length ? preferences.groups : preferences.groups.filter((group) => group.criteria[0]?.layerId !== selectedGroceryLayerId) }); } }), ` ${label}`)),
  );
}

function ServiceSelectionControls({ selection, preferences, onChange }: { selection: ServiceSelection; preferences: AppPreferences; onChange(next: AppPreferences): void }) {
  const selected = selectedServiceGroups(selection, preferences);
  return createElement("fieldset", { className: "grocery-store-selection" },
    createElement("legend", null, selection.label),
    createElement("p", null, "Valitse mukaan otettavat palvelut. Arvoksi tulee valittujen ryhmien lyhin kävelymatka."),
    ...selection.groups.map(([id, label]) => createElement("label", { key: id }, createElement("input", { type: "checkbox", checked: selected.includes(id), onChange: (event: ChangeEvent<HTMLInputElement>) => {
      const groups = event.target.checked ? [...selected, id] : selected.filter((item) => item !== id);
      onChange({ ...preferences, [selection.preferenceKey]: groups, groups: groups.length ? preferences.groups : preferences.groups.filter((group) => group.criteria[0]?.layerId !== selection.layerId) });
    } }), ` ${label}`)),
  );
}

export function inspectorEyebrow(building: { years: readonly number[]; values: Record<string, BuildingLayerValue> }): string {
  const houseType = building.values["house_type"];
  const typeText = houseType && typeof houseType.value === "string" ? finnishValue(houseType.value) : null;
  const yearText = building.years.length ? `rakennettu ${building.years.join(", ")}` : null;
  return [typeText, yearText].filter(Boolean).join(" · ") || "Asuinrakennus";
}

export function renderLayerValue(layer: LayerMetadata, value: BuildingLayerValue | undefined): { text: string; unit: string; known: boolean } {
  const rendered = value?.values.length
    ? value.values.map((item) => typeof item === "string" ? finnishValue(item) : formatLayerNumber(layer.unit, item)).join(", ")
    : typeof value?.value === "string" ? finnishValue(value.value)
      : typeof value?.value === "number" ? formatLayerNumber(layer.unit, value.value)
        : null;
  if (rendered === null) return { text: "tieto puuttuu", unit: "", known: false };
  return { text: rendered, unit: layer.kind === "numeric" ? unitSuffix(layer.unit) : "", known: true };
}

function criterionLabels(preferences: AppPreferences, layers: readonly LayerMetadata[], ids: readonly string[]): string {
  return ids.map((id) => {
    const layerId = preferences.groups.find((group) => group.id === id)?.criteria[0]?.layerId;
    return layers.find((layer) => layer.layer_id === layerId)?.finnish_label ?? "kriteeri";
  }).join(", ");
}

export function defaultCommuteLayerId(layers: readonly LayerMetadata[], mode: "transit" | "bike", statistic = "median"): string | undefined {
  const destination = commuteDestinations(layers, mode)[0];
  if (destination === undefined) return undefined;
  return layers.find((layer) => { const parts = commuteLayerParts(layer.layer_id); return parts?.mode === mode && parts.destination === destination && (mode === "bike" ? parts.statistic === "effective" : parts.statistic === statistic); })?.layer_id;
}

export function reconcilePreferences(preferences: AppPreferences, definitions: readonly LayerMetadata[]): AppPreferences {
  const layerById = new Map(definitions.map((layer) => [layer.layer_id, layer]));
  return {
    ...preferences,
    selectedVisualization: preferences.selectedVisualization === "overall" || preferences.selectedVisualization === "none" || layerById.has(preferences.selectedVisualization) ? preferences.selectedVisualization : "none",
    groups: preferences.groups.flatMap((group) => group.criteria.filter((criterion) => layerById.has(criterion.layerId)).map((criterion) => normalizeCriterion(group, criterion))),
  };
}

// The Settings UI presents a flat list of criteria (all combined with AND) where
// each criterion carries its own must-have flag, weight, and score ramp. Under
// the hood each is a single-criterion "and" group, so the existing scoring engine
// is reused unchanged. This also migrates older saved profiles (multi-criterion
// groups, OR groups, hard min/max ranges) into that flat, ramp-based shape.
export function normalizeCriterion(group: CriterionGroup, criterion: Criterion): CriterionGroup {
  const preference = criterion.preference;
  const softPreference = preference.softPreference
    ?? (preference.minimum !== undefined && preference.maximum !== undefined && preference.minimum < preference.maximum
      ? { direction: "lower_is_better" as const, fullScoreAt: preference.minimum, zeroScoreAt: preference.maximum }
      : undefined);
  return {
    id: criterion.id,
    operator: "and",
    dealbreaker: group.dealbreaker ?? false,
    weight: group.weight ?? 1,
    criteria: [{ id: criterion.id, layerId: criterion.layerId, preference: { enabled: true, acceptedCategories: preference.acceptedCategories, ...(softPreference ? { softPreference } : {}) } }],
  };
}

export function loadReconciledPreferenceSet(settings: SavedPreferenceSets, id: string, definitions: readonly LayerMetadata[]): SavedPreferenceSets {
  const loaded = loadPreferenceSet(settings, id);
  return { ...loaded, draft: reconcilePreferences(loaded.draft, definitions) };
}

function defaults(): AppPreferences {
  return { version: 2, groups: [], selectedVisualization: "none", missingDealbreakerPolicy: "pass", overviewAggregation: "median" };
}

export function openGroundMessage(): string {
  return "Sopivuutta ei lasketa. Raaka-arvoja ei ole saatavilla tästä pisteestä.";
}

export function returnFocusToMap(): void {
  if (typeof document !== "undefined") document.querySelector<HTMLElement>('[aria-label="Karttanäkymä"]')?.focus();
}

export function evaluationDetails(
  layer: LayerMetadata,
  preference: LayerPreference | undefined,
  evaluation: { configured: boolean; status: string; score: number | null } | undefined,
): string {
  if (!evaluation?.configured || !preference) return " — ei pisteytetä";
  const accepted = layer.kind === "numeric"
    ? `${preference.minimum === undefined ? "−∞" : formatLayerNumber(layer.unit, preference.minimum)}–${preference.maximum === undefined ? "∞" : formatLayerNumber(layer.unit, preference.maximum)}${unitSuffix(layer.unit)}`
    : preference.acceptedCategories.map(finnishValue).join(", ");
  const role = preference.dealbreaker ? "ehdoton vaatimus" : `paino ${preference.weight ?? 1}`;
  return ` — hyväksytään: ${accepted}; ${role}; arvio: ${evaluation.status}; kerrospiste ${evaluation.score ?? "tuntematon"}`;
}

export function groupEvaluationDetails(layer: LayerMetadata, preferences: AppPreferences, evaluations: Readonly<Record<string, LayerEvaluation>> | undefined): string {
  const details = preferences.groups.flatMap((group) => group.criteria.flatMap((criterion) => {
    if (criterion.layerId !== layer.layer_id) return [];
    const evaluation = evaluations?.[criterion.id];
    if (!evaluation?.configured) return [];
    const soft = criterion.preference.softPreference;
    const accepted = layer.kind === "numeric"
      ? soft
        ? soft.direction === "range"
          ? `täysi ${formatLayerNumber(layer.unit, Math.min(soft.fullScoreAt, soft.zeroScoreAt))}–${formatLayerNumber(layer.unit, Math.max(soft.fullScoreAt, soft.zeroScoreAt))}${unitSuffix(layer.unit)}`
          : `täysi ${formatLayerNumber(layer.unit, soft.fullScoreAt)}${unitSuffix(layer.unit)} → nolla ${formatLayerNumber(layer.unit, soft.zeroScoreAt)}${unitSuffix(layer.unit)}`
        : "ei asetettu"
      : criterion.preference.acceptedCategories.map(finnishValue).join(", ");
    const role = group.dealbreaker ? "pakollinen" : `painoarvo ${group.weight ?? 1}`;
    return [`${accepted}; ${role}; kerrospiste ${evaluation.score ?? "tuntematon"}`];
  }));
  return details.length ? ` — ${details.join(" | ")}` : " — ei pisteytetä";
}


function storageAvailable(): boolean {
  return typeof localStorage !== "undefined" && typeof localStorage.getItem === "function";
}

if (typeof document !== "undefined") {
  createRoot(document.getElementById("root")!).render(createElement(App));
}
