import { useEffect, useState } from "react";

import type { AppPreferences, CriterionGroup } from "../types/scoring";
import { commuteDestinations, commuteLayerParts, layerGroupFor, layerGroups, transitStatisticLabel, transitStatistics, type LayerMetadata } from "../data/layers";
import { finnishCaveat, finnishMethodology, finnishUnit, finnishValue } from "../data/labels";
import type { LayerDistributions } from "../data/distributions";
import { LayerHistogram } from "./LayerHistogram";

interface RampDraft { low: string; high: string; fullLow: boolean; fullHigh: boolean; }
type SoftPreference = NonNullable<CriterionGroup["criteria"][number]["preference"]["softPreference"]>;

export function CriteriaControls({ layers, distributions = {}, preferences, onChange }: { layers: readonly LayerMetadata[]; distributions?: LayerDistributions; preferences: AppPreferences; onChange(next: AppPreferences): void }) {
  const groups = preferences.groups;
  const update = (group: CriterionGroup) => onChange({ ...preferences, groups: groups.map((item) => item.id === group.id ? group : item) });
  const remove = (group: CriterionGroup) => onChange({ ...preferences, groups: groups.filter((item) => item.id !== group.id) });
  const add = (group: CriterionGroup) => onChange({ ...preferences, groups: [...groups, group] });
  return <section className="criteria" aria-label="Kriteerit">
    <div className="criteria-heading"><h3>Kriteerit</h3></div>
    <p>Lisää ominaisuuksia, jotka vaikuttavat sopivuuteen. Merkitse vain ehdottomat vaatimukset pakollisiksi. Voit lisätä aamumatkan useaan kohteeseen.</p>
    {groups.map((group) => <div className="layer-control criterion-row" key={group.id}>
      <CriterionRow group={group} layer={layers.find((item) => item.layer_id === group.criteria[0]?.layerId)} distributions={distributions} onChange={update} onDelete={() => remove(group)} />
    </div>)}
    <div className="add-criterion"><AddCriterion layers={layers} onAdd={add} /></div>
  </section>;
}

function CriterionRow({ group, layer, distributions, onChange, onDelete }: { group: CriterionGroup; layer?: LayerMetadata; distributions: LayerDistributions; onChange(next: CriterionGroup): void; onDelete(): void }) {
  const criterion = group.criteria[0];
  const soft = criterion?.preference.softPreference;
  const [ramp, setRamp] = useState<RampDraft>(() => rampDraftFrom(soft));
  useEffect(() => setRamp(rampDraftFrom(soft)), [soft]);
  if (!layer || !criterion) return null;
  const updatePreference = (patch: Partial<typeof criterion.preference>) => onChange({ ...group, criteria: [{ ...criterion, preference: { ...criterion.preference, ...patch } }] });
  const changeRamp = (change: Partial<RampDraft>) => {
    const next = { ...ramp, ...change };
    setRamp(next);
    updatePreference({ softPreference: softFromRampDraft(next) });
  };
  // Each end toggles independently, but at least one end must stay full: turning
  // off the last full end flips the other end on instead, so ● ○ / ○ ● (ramps)
  // and ● ● (full-score band) are reachable but ○ ○ never is.
  const toggleEnd = (end: "low" | "high") => {
    let { fullLow, fullHigh } = ramp;
    if (end === "low") fullLow = !fullLow; else fullHigh = !fullHigh;
    if (!fullLow && !fullHigh) { if (end === "low") fullHigh = true; else fullLow = true; }
    changeRamp({ fullLow, fullHigh });
  };
  const band = soft?.direction === "range" ? { from: Math.min(soft.fullScoreAt, soft.zeroScoreAt), to: Math.max(soft.fullScoreAt, soft.zeroScoreAt) } : undefined;
  return <div className="layer-control-fields">
    <div className="criterion-title"><strong>{layer.finnish_label}</strong><button type="button" className="criterion-remove" aria-label={`Poista kriteeri: ${layer.finnish_label}`} onClick={onDelete}>Poista</button></div>
    <details><summary>Lisätiedot</summary><p>{layer.description}</p>{layer.methodology ? <p>{finnishMethodology(layer.methodology)}</p> : null}{layer.caveat_ids.length ? <p>Huomio: {layer.caveat_ids.map(finnishCaveat).join(" ")}</p> : null}</details>
    {layer.kind === "numeric" ? <>
      <LayerHistogram layer={layer} distributions={distributions} fullScoreAt={band ? undefined : soft?.fullScoreAt} zeroScoreAt={band ? undefined : soft?.zeroScoreAt} fullBand={band} />
      <div className="score-ramp">
        <div className="ramp-row">
          <button type="button" className={rampDotClass(ramp.fullLow)} aria-pressed={ramp.fullLow} aria-label="Täysi pistemäärä pienillä arvoilla" onClick={() => toggleEnd("low")}>{ramp.fullLow ? "●" : "○"}</button>
          <input type="number" aria-label={`${layer.finnish_label}: rampin alaraja`} value={ramp.low} onChange={(event) => changeRamp({ low: event.target.value })} />
          <span className="ramp-line" aria-hidden="true">→</span>
          <input type="number" aria-label={`${layer.finnish_label}: rampin yläraja`} value={ramp.high} onChange={(event) => changeRamp({ high: event.target.value })} />
          <button type="button" className={rampDotClass(ramp.fullHigh)} aria-pressed={ramp.fullHigh} aria-label="Täysi pistemäärä suurilla arvoilla" onClick={() => toggleEnd("high")}>{ramp.fullHigh ? "●" : "○"}</button>
          {finnishUnit(layer.unit) ? <span className="ramp-unit">{finnishUnit(layer.unit)}</span> : null}
        </div>
        <small>{rampSummary(ramp, layer)}</small>
      </div>
    </> : <div className="category-options">{layer.allowed_categories.map((category) => <label key={category}><input type="checkbox" checked={criterion.preference.acceptedCategories.includes(category)} onChange={(event) => updatePreference({ acceptedCategories: event.target.checked ? [...criterion.preference.acceptedCategories, category] : criterion.preference.acceptedCategories.filter((item) => item !== category) })} /> {finnishValue(category)}</label>)}</div>}
    <div className="layer-actions">
      <label className="toggle"><input type="checkbox" checked={group.dealbreaker ?? false} onChange={(event) => onChange({ ...group, dealbreaker: event.target.checked })} /> Pakollinen vaatimus</label>
      {!group.dealbreaker && <label className="weight-control">Tärkeys <input aria-label={`${layer.finnish_label}: tärkeys`} type="number" min="0" value={group.weight ?? 1} onChange={(event) => onChange({ ...group, weight: Number(event.target.value) })} /></label>}
    </div>
  </div>;
}

function AddCriterion({ layers, onAdd }: { layers: readonly LayerMetadata[]; onAdd(group: CriterionGroup): void }) {
  const [mode, setMode] = useState<"ordinary" | "transit" | "bike">("ordinary");
  const [layerId, setLayerId] = useState("");
  const commuteLayers = layers.filter((layer) => commuteLayerParts(layer.layer_id)?.mode === mode);
  const destinations = [...new Set(commuteLayers.map((layer) => commuteLayerParts(layer.layer_id)!.destination))];
  const [destination, setDestination] = useState("");
  const [statistic, setStatistic] = useState("median");
  const selected = mode === "ordinary" ? layers.find((layer) => layer.layer_id === layerId) : commuteLayers.find((layer) => { const parts = commuteLayerParts(layer.layer_id)!; return parts.destination === destination && parts.statistic === (mode === "bike" ? "effective" : statistic); });
  const ordinaryLayers = layers.filter((layer) => layer.visible !== false && !commuteLayerParts(layer.layer_id));
  return <div className="layer-control-fields">
    <label className="add-criterion-label">Lisää kriteeri <select value={mode === "ordinary" ? layerId : mode} onChange={(event) => { const value = event.target.value as typeof mode; if (value === "transit" || value === "bike") { setMode(value); setDestination(""); } else { setMode("ordinary"); setLayerId(value); } }}>
      <option value="">Valitse tieto</option>
      {layerGroups.map((group) => {
        const options = [
          ...ordinaryLayers.filter((layer) => layerGroupFor(layer.layer_id) === group).map((layer) => <option key={layer.layer_id} value={layer.layer_id}>{layer.finnish_label}</option>),
          ...(group === "Liikkuminen" ? [<option key="transit" value="transit">Aamumatka</option>, <option key="bike" value="bike">Pyörämatka</option>] : []),
        ];
        return options.length ? <optgroup key={group} label={group}>{options}</optgroup> : null;
      })}
    </select></label>
    {mode !== "ordinary" && <><label>Kohde <select value={destination} onChange={(event) => setDestination(event.target.value)}><option value="">Valitse kohde</option>{destinations.map((value) => <option key={value} value={value}>{commuteLayers.find((layer) => commuteLayerParts(layer.layer_id)?.destination === value)?.finnish_label.split(": ")[1]?.split(",")[0] ?? value}</option>)}</select></label>{mode === "transit" && <label>Arvo <select value={statistic} onChange={(event) => setStatistic(event.target.value)}>{transitStatistics.map((value) => <option key={value} value={value}>{transitStatisticLabel(value)}</option>)}</select></label>}</>}
    <button type="button" disabled={!selected} onClick={() => { if (selected) onAdd(newCriterionGroup(selected)); }}>Lisää kriteeri</button>
  </div>;
}

export function newCriterionGroup(layer: LayerMetadata): CriterionGroup {
  const id = makeId();
  const softPreference = layer.kind === "numeric" ? softFromRampDraft(defaultRampDraft(layer)) : undefined;
  return { id, operator: "and", weight: 1, dealbreaker: false, criteria: [{ id, layerId: layer.layer_id, preference: { enabled: true, acceptedCategories: [], ...(softPreference ? { softPreference } : {}) } }] };
}

export function defaultRampDraft(layer: LayerMetadata): RampDraft {
  const breaks = layer.visualization_breaks;
  if (breaks && breaks.length >= 2) return { low: String(niceRound(breaks[Math.max(1, Math.floor(breaks.length * 0.25))])), high: String(niceRound(breaks[Math.min(breaks.length - 1, Math.floor(breaks.length * 0.75))])), fullLow: true, fullHigh: false };
  const range = layer.visualization_range;
  if (range) return { low: String(niceRound(range[0] + (range[1] - range[0]) * 0.25)), high: String(niceRound(range[0] + (range[1] - range[0]) * 0.75)), fullLow: true, fullHigh: false };
  return { low: "", high: "", fullLow: true, fullHigh: false };
}

function niceRound(value: number): number {
  const magnitude = Math.abs(value);
  if (magnitude >= 100) return Math.round(value);
  if (magnitude >= 10) return Math.round(value);
  return Math.round(value * 10) / 10;
}

export function softFromRampDraft(draft: RampDraft): SoftPreference | undefined {
  if (draft.low === "" || draft.high === "") return undefined;
  const low = Number(draft.low);
  const high = Number(draft.high);
  if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) return undefined;
  if (draft.fullLow && draft.fullHigh) return { direction: "range", fullScoreAt: low, zeroScoreAt: high };
  if (draft.fullLow) return { direction: "lower_is_better", fullScoreAt: low, zeroScoreAt: high };
  if (draft.fullHigh) return { direction: "higher_is_better", fullScoreAt: high, zeroScoreAt: low };
  return undefined;
}

function rampDraftFrom(soft: SoftPreference | undefined): RampDraft {
  if (!soft) return { low: "", high: "", fullLow: true, fullHigh: false };
  return {
    low: String(Math.min(soft.fullScoreAt, soft.zeroScoreAt)),
    high: String(Math.max(soft.fullScoreAt, soft.zeroScoreAt)),
    fullLow: soft.direction === "range" || soft.direction === "lower_is_better",
    fullHigh: soft.direction === "range" || soft.direction === "higher_is_better",
  };
}

function rampSummary(draft: RampDraft, layer: LayerMetadata): string {
  if (!softFromRampDraft(draft)) return "Aseta molemmat luvut. ● = täysi pistemäärä, ○ = nolla pistettä.";
  const unit = finnishUnit(layer.unit) ? ` ${finnishUnit(layer.unit)}` : "";
  if (draft.fullLow && draft.fullHigh) return `Täysi pistemäärä välillä ${draft.low}–${draft.high}${unit}, muualla nolla pistettä.`;
  return draft.fullLow
    ? `Täysi pistemäärä alle ${draft.low}${unit}, laskee lineaarisesti nollaan arvossa ${draft.high}${unit}.`
    : `Täysi pistemäärä yli ${draft.high}${unit}, laskee lineaarisesti nollaan arvossa ${draft.low}${unit}.`;
}

function rampDotClass(active: boolean): string { return active ? "ramp-dot full" : "ramp-dot"; }
function makeId(): string { return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `criterion-${Date.now()}-${Math.random()}`; }
