import type { ReactNode } from "react";
import { commuteLayerParts, type LayerMetadata } from "../data/layers";
import { finnishValue } from "../data/labels";
import type { LayerPreference } from "../types/scoring";

interface Props {
  layers: readonly LayerMetadata[];
  preferences: LegacyPreferences;
  onChange(preferences: LegacyPreferences): void;
}

interface LegacyPreferences {
  version: number;
  layers: Readonly<Record<string, LayerPreference>>;
  selectedVisualization: string;
  missingDealbreakerPolicy: "pass" | "fail";
  overviewAggregation?: "min" | "median" | "max";
}

interface SoftPreferenceDraft {
  direction: "lower_is_better" | "higher_is_better";
  fullScoreAt: string;
  zeroScoreAt: string;
}

export function LayerControls({ layers, preferences, onChange }: Props) {
  const [editing, setEditing] = useState<{ layerId: string; configured: boolean } | null>(null);
  const [softDrafts, setSoftDrafts] = useState<Record<string, SoftPreferenceDraft>>({});
  function update(layerId: string, change: Partial<LayerPreference>) {
    const current = preferences.layers[layerId] ?? { enabled: false, acceptedCategories: [] };
    const layer = layers.find((candidate) => candidate.layer_id === layerId);
    const next = { ...current, ...change };
    onChange({
      ...preferences,
      layers: {
        ...preferences.layers,
        [layerId]: { ...next, enabled: layer ? hasSelection(layer, next) : next.enabled },
      },
    });
  }

  function softDraft(layerId: string, preference: LayerPreference): SoftPreferenceDraft {
    return softDrafts[layerId] ?? {
      direction: preference.softPreference?.direction ?? "lower_is_better",
      fullScoreAt: preference.softPreference?.fullScoreAt.toString() ?? "",
      zeroScoreAt: preference.softPreference?.zeroScoreAt.toString() ?? "",
    };
  }

  function updateSoftPreference(layerId: string, preference: LayerPreference, change: Partial<SoftPreferenceDraft>) {
    const next = { ...softDraft(layerId, preference), ...change };
    setSoftDrafts((current) => ({ ...current, [layerId]: next }));
    const fullScoreAt = numberOrUndefined(next.fullScoreAt);
    const zeroScoreAt = numberOrUndefined(next.zeroScoreAt);
    const valid = fullScoreAt !== undefined && zeroScoreAt !== undefined
      && (next.direction === "lower_is_better" ? fullScoreAt < zeroScoreAt : fullScoreAt > zeroScoreAt);
    update(layerId, { softPreference: valid ? { direction: next.direction, fullScoreAt, zeroScoreAt } : undefined });
  }

  const ordinaryLayers = layers.filter((layer) => !commuteLayerParts(layer.layer_id));
  const configuredLayers = ordinaryLayers.filter((layer) => hasSelection(layer, preferences.layers[layer.layer_id] ?? { enabled: false, acceptedCategories: [] }) || editing?.layerId === layer.layer_id && editing.configured);
  const availableLayers = ordinaryLayers.filter((layer) => !hasSelection(layer, preferences.layers[layer.layer_id] ?? { enabled: false, acceptedCategories: [] }) || editing?.layerId === layer.layer_id && !editing.configured);

  function beginEditing(layer: LayerMetadata) {
    setEditing((current) => current?.layerId === layer.layer_id ? current : { layerId: layer.layer_id, configured: hasSelection(layer, preferences.layers[layer.layer_id] ?? { enabled: false, acceptedCategories: [] }) });
  }

  function finishEditing(event: React.FocusEvent<HTMLElement>, layerId: string) {
    const control = event.currentTarget;
    queueMicrotask(() => {
      if (!control.contains(document.activeElement)) setEditing((current) => current?.layerId === layerId ? null : current);
    });
  }

  function control(layer: LayerMetadata) {
    const preference = preferences.layers[layer.layer_id] ?? { enabled: false, acceptedCategories: [] };
    const clear = layer.kind === "numeric"
      ? () => {
        setSoftDrafts((current) => ({ ...current, [layer.layer_id]: { direction: "lower_is_better", fullScoreAt: "", zeroScoreAt: "" } }));
        update(layer.layer_id, { minimum: undefined, maximum: undefined, softPreference: undefined });
      }
      : () => update(layer.layer_id, { acceptedCategories: [] });
    return <details className="layer-control" key={layer.layer_id} onFocusCapture={() => beginEditing(layer)} onBlurCapture={(event) => finishEditing(event, layer.layer_id)}>
      <summary><span>{layer.finnish_label}</span><span className="layer-control-summary">{selectionSummary(layer, preference)}</span></summary>
      <fieldset className="layer-control-fields">
      <legend className="sr-only">{layer.finnish_label}</legend>
      {layer.kind === "numeric" ? <>
        <label className="numeric-range"><span>Arvo välillä ({layer.unit ?? "arvo"})</span><input aria-label={`${layer.finnish_label} alin arvo (${layer.unit ?? "arvo"})`} type="number" placeholder="alin" value={preference.minimum ?? ""} onChange={(event) => update(layer.layer_id, { minimum: numberOrUndefined(event.target.value) })} /><span aria-hidden="true">≤ arvo ≤</span><input aria-label={`${layer.finnish_label} ylin arvo (${layer.unit ?? "arvo"})`} type="number" placeholder="ylin" value={preference.maximum ?? ""} onChange={(event) => update(layer.layer_id, { maximum: numberOrUndefined(event.target.value) })} /></label>
        <div className="soft-preference">
          <span>Liukuva etu</span>
          <label><input aria-label={`${layer.finnish_label} suurempi arvo on parempi`} type="checkbox" checked={softDraft(layer.layer_id, preference).direction === "higher_is_better"} onChange={(event) => updateSoftPreference(layer.layer_id, preference, { direction: event.target.checked ? "higher_is_better" : "lower_is_better" })} /> Suurempi arvo on parempi</label>
          <label>Täysi etu <input aria-label={`${layer.finnish_label} täysi etu`} type="number" value={softDraft(layer.layer_id, preference).fullScoreAt} onChange={(event) => updateSoftPreference(layer.layer_id, preference, { fullScoreAt: event.target.value })} /></label>
          <label>Ei etua enää <input aria-label={`${layer.finnish_label} ei etua enää`} type="number" value={softDraft(layer.layer_id, preference).zeroScoreAt} onChange={(event) => updateSoftPreference(layer.layer_id, preference, { zeroScoreAt: event.target.value })} /></label>
          <small>Piste vähenee tasaisesti välillä {softPreferenceSummary(layer, softDraft(layer.layer_id, preference))}.</small>
        </div>
      </> : <div className="category-options">{layer.allowed_categories.map((category) => <label key={category}><input type="checkbox" checked={preference.acceptedCategories.includes(category)} onChange={(event) => update(layer.layer_id, { acceptedCategories: event.target.checked ? [...preference.acceptedCategories, category] : preference.acceptedCategories.filter((value) => value !== category) })} /> {finnishValue(category)}</label>)}</div>}
      <div className="layer-actions"><button type="button" onClick={clear}>{layer.kind === "numeric" ? "Tyhjennä rajat" : "Tyhjennä luokat"}</button>{!preference.dealbreaker && <details className="weight-control"><summary>{(preference.weight ?? 1) === 1 ? "Tärkeys: tärkeä" : `Tärkeys: paino ${preference.weight}`}</summary><label>Paino <input aria-label={`${layer.finnish_label} paino`} type="number" min="0" value={preference.weight ?? 1} onChange={(event) => update(layer.layer_id, { weight: numberOrUndefined(event.target.value) })} /></label></details>}<label className="toggle"><input type="checkbox" checked={preference.dealbreaker ?? false} onChange={(event) => update(layer.layer_id, { dealbreaker: event.target.checked })} /> Ehdoton vaatimus</label></div>
      </fieldset>
    </details>;
  }

  return <section className="criteria" aria-label="Kriteerit">
    <div className="criteria-heading"><h3>Kriteerit</h3><span>{configuredLayers.length} käytössä</span></div>
    <p>Valitse vain asiat, jotka vaikuttavat päätökseesi.</p>
    <CommuteControls layers={layers} control={control} />
    {configuredLayers.map(control)}
    <details className="add-layer">
      <summary>Lisää kriteeri</summary>
      {availableLayers.map(control)}
    </details>
  </section>;
}

function CommuteControls({ layers, control }: { layers: readonly LayerMetadata[]; control(layer: LayerMetadata): ReactNode }) {
  const grouped = new Map<string, LayerMetadata[]>();
  for (const layer of layers) {
    const parts = commuteLayerParts(layer.layer_id);
    if (!parts) continue;
    grouped.set(`${parts.mode}:${parts.destination}`, [...(grouped.get(`${parts.mode}:${parts.destination}`) ?? []), layer]);
  }
  const sections = (["transit", "bike"] as const).map((mode) => [...grouped.entries()].filter(([key]) => key.startsWith(`${mode}:`)));
  if (!sections.some((items) => items.length)) return null;
  return <section className="commute-criteria" aria-label="Matkakriteerit">
    {sections.map((items, index) => items.length ? <details key={index} className="commute-group">
      <summary>{index === 0 ? "Aamumatka" : "Pyörämatka"}</summary>
      {items.map(([, destinationLayers]) => <details key={destinationLayers[0].layer_id} className="commute-destination">
        <summary>Kohde: {destinationName(destinationLayers[0])}</summary>
        {destinationLayers.sort((left, right) => statisticOrder(left.layer_id) - statisticOrder(right.layer_id)).map(control)}
      </details>)}
    </details> : null)}
  </section>;
}

function destinationName(layer: LayerMetadata): string {
  return layer.finnish_label.split(": ")[1]?.split(",")[0] ?? layer.finnish_label;
}

function statisticOrder(layerId: string): number {
  const statistic = commuteLayerParts(layerId)?.statistic;
  return statistic === "min" ? 0 : statistic === "median" ? 1 : 2;
}

export function hasSelection(layer: LayerMetadata, preference: LayerPreference): boolean {
  return layer.kind === "numeric"
    ? preference.minimum !== undefined || preference.maximum !== undefined || preference.softPreference !== undefined
    : preference.acceptedCategories.length > 0;
}

function selectionSummary(layer: LayerMetadata, preference: LayerPreference): string {
  if (layer.kind === "numeric") {
    if (preference.minimum !== undefined || preference.maximum !== undefined) return `${preference.minimum === undefined ? "−∞" : formatNumber(preference.minimum)}–${preference.maximum === undefined ? "∞" : formatNumber(preference.maximum)}${layer.unit ? ` ${layer.unit}` : ""}`;
    if (preference.softPreference) return `liukuva etu: ${formatNumber(preference.softPreference.fullScoreAt)}–${formatNumber(preference.softPreference.zeroScoreAt)}${layer.unit ? ` ${layer.unit}` : ""}`;
    return "ei rajaa";
  }
  return preference.acceptedCategories.length ? `${preference.acceptedCategories.length} valittu` : "ei valintaa";
}

function numberOrUndefined(value: string): number | undefined {
  if (value === "") return undefined;
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function softPreferenceSummary(layer: LayerMetadata, preference: SoftPreferenceDraft): string {
  const full = preference.fullScoreAt === "" ? "–" : preference.fullScoreAt;
  const zero = preference.zeroScoreAt === "" ? "–" : preference.zeroScoreAt;
  return `${full}–${zero}${layer.unit ? ` ${layer.unit}` : ""}`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fi-FI", { maximumFractionDigits: 1 }).format(value).replace(/\u00a0/g, " ");
}
import { useState } from "react";
