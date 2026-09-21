export function tileKeysForBounds(bounds: [number, number, number, number], zoom: number, buffer: number): string[] {
  const [west, south, east, north] = bounds;
  const limit = 2 ** zoom - 1;
  const x0 = tileX(west, zoom);
  const x1 = tileX(east, zoom);
  const y0 = tileY(north, zoom);
  const y1 = tileY(south, zoom);
  const keys: string[] = [];
  for (let x = Math.max(0, x0 - buffer); x <= Math.min(limit, x1 + buffer); x += 1) {
    for (let y = Math.max(0, y0 - buffer); y <= Math.min(limit, y1 + buffer); y += 1) keys.push(`${x}/${y}`);
  }
  return keys;
}

export function tilePath(template: string, key: string): string {
  const [x, y] = key.split("/");
  return template.replace("{x}", x).replace("{y}", y);
}

export function availableTileKeys(keys: readonly string[], available: ReadonlySet<string>): string[] {
  return keys.filter((key) => available.has(key));
}

export function retainRecentKeys(keys: readonly string[], maximum: number): string[] {
  return keys.slice(-maximum);
}

export function fulfilledValues<T>(attempts: readonly PromiseSettledResult<T>[]): T[] {
  return attempts.flatMap((attempt) => attempt.status === "fulfilled" ? [attempt.value] : []);
}

function tileX(longitude: number, zoom: number): number {
  return Math.floor((longitude + 180) / 360 * 2 ** zoom);
}

function tileY(latitude: number, zoom: number): number {
  const clipped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
  return Math.floor((1 - Math.asinh(Math.tan(clipped * Math.PI / 180)) / Math.PI) / 2 * 2 ** zoom);
}
