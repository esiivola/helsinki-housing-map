import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const prefix = '{"type":"FeatureCollection","features":[';

test("repairs exactly the first 1,000 missing feature separators", async () => {
  const directory = await mkdtemp(join(tmpdir(), "green-cover-repair-"));
  const source = join(directory, "broken.geojson");
  const features = Array.from({ length: 1_001 }, (_, index) => `{"type":"Feature","id":${index + 1},"geometry":null,"properties":{}}`);
  await writeFile(source, `${prefix}${features.slice(0, 1_000).join("")},${features[1_000]}]}`);
  try {
    await execFileAsync("node", ["scripts/repair_hsy_green_cover_geojson.mjs", source], { cwd: process.cwd() });
    const repaired = await readFile(`${source}.repaired`, "utf8");
    assert.equal(JSON.parse(repaired).features.length, 1_001);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("preserves data when the damaged page crosses stream chunks", async () => {
  const directory = await mkdtemp(join(tmpdir(), "green-cover-repair-"));
  const source = join(directory, "broken-large.geojson");
  const features = Array.from({ length: 1_001 }, (_, index) => JSON.stringify({ type: "Feature", id: index + 1, geometry: { type: "Point", coordinates: [25.17726 + index / 100_000, 60.2613572] }, properties: { padding: "x".repeat(200) } }));
  await writeFile(source, `${prefix}${features.slice(0, 1_000).join("")},${features[1_000]}]}`);
  try {
    await execFileAsync("node", ["scripts/repair_hsy_green_cover_geojson.mjs", source], { cwd: process.cwd() });
    const repaired = await readFile(`${source}.repaired`, "utf8");
    assert.equal(repaired, `${prefix}${features.join(",")}]}`);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
