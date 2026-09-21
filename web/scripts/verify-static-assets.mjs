import { access, readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

const assets = join("dist", "assets");
const files = await readdir(assets);
const mapBundle = files.find((name) => name.startsWith("MapView-") && name.endsWith(".js"));
if (!mapBundle) throw new Error("MapView production bundle is missing");
const bundle = await readFile(join(assets, mapBundle), "utf8");
const worker = bundle.match(/maplibre-gl-worker-[\w-]+\.js/)?.[0];
if (!worker || !files.includes(worker)) throw new Error("MapLibre worker asset is missing");
if (/^\s*import(?:\s|\{|\*|["'])/m.test(await readFile(join(assets, worker), "utf8"))) {
  throw new Error("MapLibre worker must be bundled without unresolved imports");
}

const data = join("dist", "data");
const manifest = JSON.parse(await readFile(join(data, "manifest.json"), "utf8"));
if (manifest.layer_distributions) await exists(join(data, manifest.layer_distributions));
const spatial = manifest.spatial_partitions;
if (spatial) {
  const layers = JSON.parse(await readFile(join(data, manifest.layer_catalogue), "utf8"));
  for (const overview of spatial.overview_tiers ?? []) {
    if (typeof overview.geometry_path_template !== "string" || typeof overview.layer_path_template !== "string" || !Array.isArray(overview.tile_keys)) throw new Error("Overview tile metadata is invalid");
    for (const key of overview.tile_keys) {
      const [x, y] = key.split("/");
      await exists(join(data, overview.geometry_path_template.replace("{x}", x).replace("{y}", y)));
      for (const layer of layers) await exists(join(data, overview.layer_path_template.replace("{layer_id}", layer.layer_id).replace("{x}", x).replace("{y}", y)));
    }
  }
  const core = spatial.building_tier.core_attribute_path_template;
  const layerTemplate = spatial.building_tier.layer_attribute_path_template;
  if ((core || layerTemplate) && (typeof core !== "string" || typeof layerTemplate !== "string")) throw new Error("Split tile templates must be declared together");
  for (const key of spatial.building_tier.tile_keys ?? []) {
    const [x, y] = key.split("/");
    await exists(join(data, spatial.building_tier.geometry_path_template.replace("{x}", x).replace("{y}", y)));
    if (core || layerTemplate) {
      await exists(join(data, core.replace("{x}", x).replace("{y}", y)));
    }
  }
}

async function exists(path) {
  try {
    await access(path);
  } catch {
    throw new Error(`Manifest references missing static artifact: ${path}`);
  }
}
