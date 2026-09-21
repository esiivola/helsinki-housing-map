import { evaluateLayer } from "../scoring/evaluate";
import type { LayerPreference } from "../types/scoring";

export function yearStatus(years: readonly number[] | undefined, preference: LayerPreference | undefined): string {
  if (!preference) return "not_scored";
  return evaluateLayer(
    { state: years?.length ? "known" : "unknown", value: null, values: years },
    { id: "building_year", kind: "numeric" },
    preference,
  ).status;
}
