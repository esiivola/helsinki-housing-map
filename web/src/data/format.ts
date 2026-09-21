export function formatNumber(value: number): string {
  return new Intl.NumberFormat("fi-FI", { maximumFractionDigits: 1 }).format(value).replace(/ /g, " ");
}

export function formatLayerNumber(unit: string | null, value: number): string {
  return unit === "year" ? String(Math.round(value)) : formatNumber(value);
}
