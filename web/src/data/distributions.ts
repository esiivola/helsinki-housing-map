export interface LayerDistribution {
  counts: readonly number[];
  knownCount: number;
  min: number;
  max: number;
}

export type LayerDistributions = Readonly<Record<string, LayerDistribution>>;

export function linearHistogram(values: readonly number[], fixedRange?: readonly [number, number]): LayerDistribution | undefined {
  const known = values.filter(Number.isFinite).sort((left, right) => left - right);
  if (!known.length) return undefined;
  let [min, max] = fixedRange ?? histogramSpan(known);
  if (max <= min) max = min + 1;
  const counts = Array.from({ length: 40 }, () => 0);
  const width = (max - min) / counts.length;
  for (const value of known) {
    if (value < min || value > max) continue;
    counts[Math.min(counts.length - 1, Math.max(0, Math.floor((value - min) / width)))] += 1;
  }
  return { counts, knownCount: known.length, min, max };
}

function histogramSpan(values: readonly number[]): [number, number] {
  const percentile = (fraction: number) => {
    const index = (values.length - 1) * fraction;
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    return values[lower] + (values[upper] - values[lower]) * (index - lower);
  };
  const low = percentile(0.01);
  const high = percentile(0.99);
  const guard = (high - low) / 2;
  return [guard > 0 && low - values[0] <= guard ? values[0] : low, guard > 0 && values.at(-1)! - high <= guard ? values.at(-1)! : high];
}

export function parseLayerDistributions(serialized: string): LayerDistributions {
  const value: unknown = JSON.parse(serialized);
  if (typeof value !== "object" || value === null || (value as Record<string, unknown>).version !== 1 || !Array.isArray((value as Record<string, unknown>).distributions)) throw new Error("Invalid layer distributions");
  const entries = (value as { distributions: unknown[] }).distributions.map((item) => {
    if (typeof item !== "object" || item === null) throw new Error("Invalid layer distribution");
    const distribution = item as Record<string, unknown>;
    const knownCount = typeof distribution.known_count === "number" ? distribution.known_count : Number.NaN;
    const min = distribution.min;
    const max = distribution.max;
    if (typeof distribution.layer_id !== "string" || !Array.isArray(distribution.counts) || !distribution.counts.every((count) => Number.isInteger(count) && count >= 0) || !Number.isInteger(knownCount) || knownCount < 0) throw new Error("Invalid layer distribution");
    if (typeof min !== "number" || typeof max !== "number" || !Number.isFinite(min) || !Number.isFinite(max) || max < min) throw new Error("Invalid layer distribution span");
    // Bars cover the 1st..99th percentile window; out-of-range values are dropped,
    // so the counts sum to at most (not exactly) the full known population.
    if (distribution.counts.reduce<number>((total, count) => total + count, 0) > knownCount) throw new Error("Invalid layer distribution counts");
    return [distribution.layer_id, { counts: distribution.counts as number[], knownCount, min, max }] as const;
  });
  return Object.fromEntries(entries);
}
