import { appendFile, open, readFile, rename, rm, stat, writeFile } from "node:fs/promises";

import { serializeFeatures } from "./green_cover_serialization.mjs";

const allLayers = [
  "maanpeite_muu_avoin_matala_kasvillisuus_2024",
  "maanpeite_puusto_2_10m_2024",
  "maanpeite_puusto_10_15m_2024",
  "maanpeite_puusto_15_20m_2024",
  "maanpeite_puusto_yli20m_2024",
];
const requestedLayers = process.argv.slice(2);
const unknownLayers = requestedLayers.filter((layer) => !allLayers.includes(layer));
if (unknownLayers.length) throw new Error(`Unknown green-cover layer: ${unknownLayers.join(", ")}`);
const layers = requestedLayers.length ? requestedLayers : allLayers;
const pageSize = 1_000;
const geoJsonPrefix = '{"type":"FeatureCollection","features":[';
const coverageBbox = [24.3, 59.8, 25.5, 60.5];
const pageDelayMilliseconds = Number(process.env.HSY_WFS_DELAY_MS ?? 10_000);
if (!Number.isFinite(pageDelayMilliseconds) || pageDelayMilliseconds < 0) throw new Error("HSY_WFS_DELAY_MS must be a non-negative number");

for (const layer of layers) {
  const output = `data/raw/hsy_${layer}.geojson`;
  const temporary = `${output}.partial`;
  const statePath = `${temporary}.json`;
  const completionPath = `${output}.complete.json`;
  if (await isCompleteGeoJson(output)) continue;
  try {
    await rename(output, `${output}.corrupt-${Date.now()}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  let state;
  try {
    state = JSON.parse(await readFile(statePath, "utf8"));
    if (!Number.isInteger(state.nextStartIndex) || state.nextStartIndex < 0 || typeof state.first !== "boolean" || !await hasGeoJsonPrefix(temporary)) throw new Error(`${layer}: invalid resumable download state`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    try {
      await stat(temporary);
      throw new Error(`${layer}: partial download exists without state`);
    } catch (statError) {
      if (statError.code !== "ENOENT") throw statError;
    }
    state = { nextStartIndex: 0, first: true };
    await writeFile(temporary, geoJsonPrefix);
    await writeFile(statePath, JSON.stringify(state));
  }
  try {
    for (let startIndex = state.nextStartIndex;; startIndex += pageSize) {
      const query = new URLSearchParams({ service: "WFS", version: "2.0.0", request: "GetFeature", typeNames: `asuminen_ja_maankaytto:${layer}`, outputFormat: "application/json", srsName: "EPSG:4326", bbox: `${coverageBbox.join(",")},EPSG:4326`, count: String(pageSize), startIndex: String(startIndex) });
      const page = await fetchPage(`https://kartta.hsy.fi/geoserver/wfs?${query}`, layer);
      if (!Array.isArray(page.features)) throw new Error(`${layer}: invalid GeoJSON page`);
      await appendFile(temporary, serializeFeatures(page.features, state.first));
      state = { nextStartIndex: startIndex + page.features.length, first: state.first && page.features.length === 0 };
      await writeFile(statePath, JSON.stringify(state));
      if (page.features.length < pageSize) {
        if (page.features.length === 0 && Number(page.numberMatched) > startIndex) throw new Error(`${layer}: empty page before ${page.numberMatched} matched features`);
        await appendFile(temporary, "]}");
        await rename(temporary, output);
        await writeFile(completionPath, JSON.stringify({ version: 2, size: (await stat(output)).size, bbox: coverageBbox }));
        await rm(statePath, { force: true });
        break;
      }
      process.stderr.write(`${layer}: ${startIndex + page.features.length}\n`);
      await new Promise((resolve) => setTimeout(resolve, pageDelayMilliseconds));
    }
  } catch (error) {
    throw error;
  }
}

async function fetchPage(url, layer) {
  let lastError;
  for (let attempt = 0;; attempt += 1) {
    let response;
    try {
      response = await fetch(url);
    } catch (error) {
      lastError = error;
      await retry(layer, attempt);
      continue;
    }
    if (!response.ok) {
      lastError = new Error(`${layer}: ${response.status}`);
      if (![429, 502, 503, 504].includes(response.status)) throw lastError;
    } else {
      try {
        return await response.json();
      } catch (error) {
        lastError = error;
      }
    }
    await retry(layer, attempt);
  }
}

async function retry(layer, attempt) {
  const delayMilliseconds = Math.min(30_000, 1_000 * 2 ** attempt);
  process.stderr.write(`${layer}: retrying after ${delayMilliseconds / 1_000} s\n`);
  await new Promise((resolve) => setTimeout(resolve, delayMilliseconds));
}

async function isCompleteGeoJson(path) {
  let file;
  try {
    file = await open(path);
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
  try {
    const { size } = await file.stat();
    if (size < Buffer.byteLength(geoJsonPrefix) + 2) return false;
    try {
      const completion = JSON.parse(await readFile(`${path}.complete.json`, "utf8"));
      return completion.version === 2 && completion.size === size && JSON.stringify(completion.bbox) === JSON.stringify(coverageBbox);
    } catch (error) {
      if (error.code === "ENOENT" || error instanceof SyntaxError) return false;
      throw error;
    }
  } finally {
    await file.close();
  }
}

async function hasGeoJsonPrefix(path) {
  let file;
  try {
    file = await open(path);
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
  try {
    const first = Buffer.alloc(Buffer.byteLength(geoJsonPrefix));
    await file.read(first, 0, first.length, 0);
    return first.toString("utf8") === geoJsonPrefix;
  } finally {
    await file.close();
  }
}
