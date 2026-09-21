import type { LayerDistributions } from "../data/distributions";
import type { LayerMetadata } from "../data/layers";
import { finnishUnit } from "../data/labels";

export function LayerHistogram({ layer, distributions, distribution: suppliedDistribution, minimum, maximum, fullScoreAt, zeroScoreAt, fullBand }: { layer?: LayerMetadata; distributions: LayerDistributions; distribution?: LayerDistributions[string]; minimum?: number; maximum?: number; fullScoreAt?: number; zeroScoreAt?: number; fullBand?: { from: number; to: number } }) {
  const distribution = suppliedDistribution ?? (layer && distributions[layer.layer_id]);
  if (!layer || layer.kind !== "numeric" || !distribution || !distribution.knownCount || distribution.max <= distribution.min) return null;
  const breaks = layer.visualization_breaks ?? Array.from({ length: 7 }, (_, index) => distribution.min + (distribution.max - distribution.min) * index / 6);
  const { counts, min, max } = distribution;
  const bins = counts.length;
  const maximumCount = Math.max(...counts, 1);
  const binWidth = (max - min) / bins;
  // The bins are equal width in value, so the x-axis is linear; markers, the
  // selected range, and the ticks all map value → percent the same way. Colour
  // still comes from the skewed percentile breaks, so the colour bands appear at
  // uneven widths across the linear axis.
  const percent = (value: number) => Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const colorBand = (value: number) => breaks.slice(1).filter((edge) => value >= edge).length;
  const selected = minimum !== undefined || maximum !== undefined;
  const scheme = layer.layer_id === "building_year" ? "years" : layer.layer_id === "income_median_eur" ? "income" : "lower";
  const ticks = niceTicks(min, max).map((value) => ({ left: `${percent(value)}%`, label: compactTick(layer.unit, value) }));
  const unit = finnishUnit(layer.unit);
  return <div className={`layer-histogram histogram-${scheme}`} aria-label={`Arvojakauma: ${layer.finnish_label}`}>
    <div className="layer-histogram-bars" aria-hidden="true">
      {counts.map((count, index) => <i key={index} className={`histogram-bin histogram-bin-${colorBand(min + (index + 0.5) * binWidth)}`} style={{ height: `${Math.max(3, count / maximumCount * 100)}%` }} />)}
      {selected && <i className="histogram-range" style={{ left: `${percent(minimum ?? min)}%`, right: `${100 - percent(maximum ?? max)}%` }} />}
      {fullBand && <i className="histogram-full-band" style={{ left: `${percent(fullBand.from)}%`, right: `${100 - percent(fullBand.to)}%` }} />}
      {fullBand && <i className="histogram-marker full-score" style={{ left: `${percent(fullBand.from)}%` }} />}
      {fullBand && <i className="histogram-marker full-score" style={{ left: `${percent(fullBand.to)}%` }} />}
      {fullScoreAt !== undefined && <i className="histogram-marker full-score" style={{ left: `${percent(fullScoreAt)}%` }} />}
      {zeroScoreAt !== undefined && <i className="histogram-marker zero-score" style={{ left: `${percent(zeroScoreAt)}%` }} />}
    </div>
    <div className="layer-histogram-axis" aria-hidden="true">
      {ticks.map((tick, index) => <span key={index} className="hist-tick" style={{ left: tick.left }}><b />{tick.label}</span>)}
    </div>
    <small>{distribution.knownCount.toLocaleString("fi-FI")} tunnettua arvoa{unit ? ` · ${unit}` : ""}</small>
  </div>;
}

export function niceTicks(min: number, max: number, target = 7): number[] {
  const span = max - min;
  if (!(span > 0)) return [];
  const rough = span / target;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const normalized = rough / magnitude;
  const step = (normalized >= 5 ? 10 : normalized >= 2 ? 5 : normalized >= 1 ? 2 : 1) * magnitude;
  const ticks: number[] = [];
  for (let value = Math.ceil(min / step) * step; value <= max + step * 1e-6; value += step) ticks.push(Number(value.toFixed(6)));
  return ticks;
}

function compactTick(unit: string | null, value: number): string {
  if (unit === "year") return String(Math.round(value));
  const magnitude = Math.abs(value);
  if (magnitude >= 10000) return `${Math.round(value / 1000)}k`;
  if (magnitude >= 1000) return `${trimDecimal((value / 1000).toFixed(1))}k`;
  return String(Math.round(value));
}

function trimDecimal(value: string): string {
  return value.endsWith(".0") ? value.slice(0, -2) : value;
}
