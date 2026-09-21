import { useEffect, useRef, useState, type MutableRefObject } from "react";
import * as maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import { loadGzipJson, loadGzipObjectUrl } from "../data/gzip";
import { parseManifest } from "../data/manifest";
import { availableTileKeys, fulfilledValues, retainRecentKeys, tileKeysForBounds, tilePath } from "../data/spatial";
import { buildingLayerValues, buildingYears, type AttributePartition, type BuildingLayerValue } from "../data/attributes";
import { finnishCaveat, finnishUnit, finnishValue, unitSuffix } from "../data/labels";
import { formatLayerNumber, formatNumber } from "../data/format";
import type { LayerMetadata } from "../data/layers";
import { evaluateBuildingGroups } from "../scoring/evaluate";
import type { AppPreferences } from "../types/scoring";
import { groceryStoreLayerIds, selectedGroceryLayerId, withSelectedGroceryValue } from "../data/grocery";
import { selectionForLayerId, serviceLayerIds, serviceSelections, withSelectedServiceValue, withSelectedServiceValues } from "../data/serviceSelections";

const localStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "tausta", type: "background", paint: { "background-color": "#edf2f4" } }],
};
const cartoKey = import.meta.env.VITE_CARTO_KEY as string | undefined;
const useCartoBasemap = Boolean(cartoKey);

export function cartoStyleUrl(key: string | undefined): string {
  return `https://basemaps.cartocdn.com/gl/positron-gl-style/style.json${key ? `?key=${key}` : ""}`;
}

function cartoTransformRequest(url: string): { url: string } {
  if (!cartoKey || !url.includes("basemaps.cartocdn.com") || url.includes("key=")) return { url };
  return { url: `${url}${url.includes("?") ? "&" : "?"}key=${cartoKey}` };
}
const maximumCachedTiles = 48;

export const mapLibreWorkerUrl = workerUrl;
export const mapControlLabels = { zoomIn: "Lähennä karttaa", zoomOut: "Loitonna karttaa", resetNorth: "Nollaa kartan suunta" } as const;

maplibregl.setWorkerUrl(mapLibreWorkerUrl);

type BuildingTier = NonNullable<ReturnType<typeof parseManifest>["spatialPartitions"]>["buildingTier"];
type OverviewTier = NonNullable<ReturnType<typeof parseManifest>["spatialPartitions"]>["overviewTiers"][number];

export function buildingTilePaths(key: string, tier: BuildingTier): string {
  return tilePath(tier.geometryPathTemplate, key);
}

export function layerTilePath(key: string, layerId: string, template: string): string {
  return tilePath(template.replace("{layer_id}", encodeURIComponent(layerId)), key);
}

export function activeLayerIds(preferences: AppPreferences): readonly string[] {
  const ids = [
    ...(preferences.selectedVisualization === "overall" || preferences.selectedVisualization === "none" ? [] : [preferences.selectedVisualization]),
    ...preferences.groups.flatMap((group) => group.criteria.map((criterion) => criterion.layerId)),
  ];
  return [...new Set(ids.flatMap((id) => id === selectedGroceryLayerId ? groceryStoreLayerIds(preferences) : selectionForLayerId(id) ? serviceLayerIds(selectionForLayerId(id)!, preferences) : [id]))];
}

export function serviceDestinationLayerIds(preferences: AppPreferences): readonly string[] {
  const selected = preferences.selectedVisualization;
  if (selected === selectedGroceryLayerId) return groceryStoreLayerIds(preferences);
  const serviceSelection = selectionForLayerId(selected);
  if (serviceSelection) return serviceLayerIds(serviceSelection, preferences);
  return selected.endsWith("_walk_m") ? [selected] : [];
}

export function filteredServiceDestinations(destinations: GeoJSON.FeatureCollection, preferences: AppPreferences): GeoJSON.FeatureCollection {
  const layerIds = new Set(serviceDestinationLayerIds(preferences));
  return { ...destinations, features: destinations.features.filter((feature) => layerIds.has(String(feature.properties?.layer_id))) };
}

export function destinationPopupHtml(names: readonly string[]): string {
  const unique = [...new Set(names.map((name) => name.trim()).filter(Boolean))].sort((left, right) => left.localeCompare(right, "fi"));
  if (!unique.length) return "";
  const title = unique.length === 1 ? "Palvelukohde" : `${unique.length} palvelukohdetta`;
  return `<div class="destination-popup"><strong>${title}</strong><ul>${unique.map((name) => `<li>${escapeHtml(name)}</li>`).join("")}</ul></div>`;
}

export function activePlanPopupHtml(properties: Record<string, unknown> | undefined): string {
  if (!properties) return "";
  const rows = [
    ["Kaavanumero", properties.plan_number],
    ["Hyväksyminen", properties.approval],
  ].filter(([, value]) => typeof value === "string" && value.trim()) as [string, string][];
  if (!rows.length) return "";
  return `<div class="destination-popup"><strong>Vireillä oleva asemakaavamuutos</strong><ul>${rows.map(([label, value]) => `<li>${escapeHtml(label)}: ${escapeHtml(value)}</li>`).join("")}</ul><a href="https://kartta.hel.fi/?link=bZWSYX" target="_blank" rel="noopener noreferrer">Lisätietoa kaavasta</a></div>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
}

export function overviewTierForZoom(tiers: readonly OverviewTier[], zoom: number): OverviewTier | undefined {
  return tiers.find((tier) => zoom >= tier.minZoom && zoom < tier.maxZoom + 1);
}

// After the async overview fetch, the map may have moved. The fetched overview
// is still worth rendering only while the map is still below the building zoom
// (i.e. still in overview mode, not zoomed into building polygons) AND the
// overview tier for the current zoom still matches the one we fetched.
export function overviewStillCurrent(zoom: number, buildingMinZoom: number, fetchedTierTemplate: string, currentTierTemplate: string | undefined): boolean {
  return zoom < buildingMinZoom && currentTierTemplate === fetchedTierTemplate;
}

type OverviewLayerValue = {
  state: "known" | "partial" | "unknown" | "conflict";
  value: number | string | null;
  values: readonly (number | string)[];
};

type OverviewLayerCell = {
  cell_id: string;
  state_counts: Record<string, number>;
  summary: { value?: number | string; min?: number; median?: number; max?: number; mode_share?: number } | null;
  score_inputs: readonly (OverviewLayerValue | null)[];
};

type OverviewLayerPartition = { version: 1; cells: readonly OverviewLayerCell[] };

export function overviewTilePath(tier: OverviewTier, key: string): string {
  return tilePath(tier.geometryPathTemplate, key);
}

export function overviewLayerPath(tier: OverviewTier, layerId: string, key: string): string {
  return tilePath(tier.layerPathTemplate.replace("{layer_id}", encodeURIComponent(layerId)), key);
}

export function overviewTileKeys(tier: OverviewTier, bounds: [number, number, number, number]): string[] {
  return availableTileKeys(tileKeysForBounds(bounds, tier.tileZoom, 1), new Set(tier.tileKeys));
}

export function mergeOverviewTiles(tiles: Iterable<GeoJSON.FeatureCollection>): GeoJSON.FeatureCollection {
  const features = new Map<string, GeoJSON.Feature>();
  for (const tile of tiles) for (const feature of tile.features) features.set(String(feature.properties?.cell_id), feature);
  return { type: "FeatureCollection", features: [...features.values()] };
}

function mergeOverviewLayerPartitions(partitions: Iterable<OverviewLayerPartition>): OverviewLayerPartition {
  const cells = new Map<string, OverviewLayerCell>();
  for (const partition of partitions) for (const cell of partition.cells) cells.set(cell.cell_id, cell);
  return { version: 1, cells: [...cells.values()] };
}

export function mergeOverviewGeometry(geometry: GeoJSON.FeatureCollection, partitions: Readonly<Record<string, OverviewLayerPartition>>): GeoJSON.FeatureCollection {
  const cellsByLayer = Object.fromEntries(Object.entries(partitions).map(([layerId, partition]) => [layerId, new Map(partition.cells.map((cell) => [cell.cell_id, cell]))]));
  const hasLayerInputs = Object.keys(cellsByLayer).length > 0;
  return {
    ...geometry,
    features: geometry.features.map((feature) => {
      const cellId = String(feature.properties?.cell_id);
      const buildingCount = Number(feature.properties?.building_count ?? 0);
      const layerStateCounts: Record<string, Record<string, number>> = {};
      const layerSummaries: Record<string, OverviewLayerCell["summary"]> = {};
      const scoreInputs: Record<string, OverviewLayerValue>[] | undefined = hasLayerInputs ? Array.from({ length: buildingCount }, () => ({})) : undefined;
      for (const [layerId, cells] of Object.entries(cellsByLayer)) {
        const cell = cells.get(cellId);
        if (!cell) continue;
        layerStateCounts[layerId] = cell.state_counts;
        if (cell.summary) layerSummaries[layerId] = cell.summary;
        cell.score_inputs.forEach((value, index) => { if (value && scoreInputs) scoreInputs[index][layerId] = value; });
      }
      return { ...feature, properties: { ...feature.properties, layer_state_counts: layerStateCounts, layer_summaries: layerSummaries, ...(scoreInputs ? { score_inputs: scoreInputs } : {}) } };
    }),
  };
}

export function overviewGeometryForBounds(overview: GeoJSON.FeatureCollection, bounds: readonly [number, number, number, number]): GeoJSON.FeatureCollection {
  const [west, south, east, north] = bounds;
  return { ...overview, features: overview.features.filter((feature) => {
    const featureBounds = geometryBounds(feature.geometry);
    return featureBounds !== undefined && featureBounds[0] <= east && featureBounds[2] >= west && featureBounds[1] <= north && featureBounds[3] >= south;
  }) };
}

function geometryBounds(geometry: GeoJSON.Geometry | null): [number, number, number, number] | undefined {
  if (!geometry) return undefined;
  const coordinates: number[][] = [];
  const collect = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === "number" && typeof value[1] === "number") coordinates.push(value as number[]);
    else value.forEach(collect);
  };
  const collectGeometry = (item: GeoJSON.Geometry): void => {
    if (item.type === "GeometryCollection") item.geometries.forEach(collectGeometry);
    else collect(item.coordinates);
  };
  collectGeometry(geometry);
  if (!coordinates.length) return undefined;
  return [Math.min(...coordinates.map(([longitude]) => longitude)), Math.min(...coordinates.map(([, latitude]) => latitude)), Math.max(...coordinates.map(([longitude]) => longitude)), Math.max(...coordinates.map(([, latitude]) => latitude))];
}

export function overviewMessage(buildingCount: number, layerLabel: string, coverage: number, summary: string | null = null): string {
  const isSuitability = layerLabel === "Kokonaissopivuus" || layerLabel === "Sopivuus";
  return `Alueyhteenveto: ${buildingCount} asuinrakennusta; ${isSuitability ? "pisteytettyjen rakennusten osuus" : `${layerLabel}-tiedon kattavuus`} ${Math.round(coverage * 100)} %${summary ? `; ${summary}` : ""}.`;
}

export function overviewContributors(properties: GeoJSON.GeoJsonProperties | null | undefined, layers: readonly LayerMetadata[], preferences: AppPreferences): string[] {
  return overviewContributorFacts(properties, layers, preferences).map((fact) => `${fact.label}: ${fact.value}`);
}

export type OverviewSummary = {
  title: string;
  value: string | null;
  statistic: string;
  buildingCount: number;
  coverage: number;
  contributors: Array<{ label: string; value: string }>;
};

export function overviewSummary(properties: GeoJSON.GeoJsonProperties | undefined, layer: LayerMetadata | undefined, layers: readonly LayerMetadata[], preferences: AppPreferences): OverviewSummary {
  const aggregation = preferences.overviewAggregation ?? "median";
  const aggregationLabel = { min: "Pienin arvo", median: "Mediaani", max: "Suurin arvo" }[aggregation];
  const isSuitability = preferences.selectedVisualization === "overall";
  const summary = layer ? (properties?.layer_summaries as Record<string, { value?: number | string; min?: number; median?: number; max?: number }> | undefined)?.[layer.layer_id] : undefined;
  const rawValue = isSuitability ? properties?.display_value : layer?.kind === "numeric" ? summary?.[aggregation] : summary?.value;
  const value = typeof rawValue === "number"
    ? isSuitability ? `${Math.round(rawValue * 100)} %` : `${formatLayerNumber(layer?.unit ?? null, rawValue)}${unitSuffix(layer?.unit ?? null)}`
    : typeof rawValue === "string" ? finnishValue(rawValue) : null;
  return {
    title: isSuitability ? "Alueen sopivuus" : layer?.finnish_label ?? "Alueen tiedot",
    value,
    statistic: isSuitability || layer?.kind === "numeric" ? aggregationLabel : "Yleisin luokka",
    buildingCount: Number(properties?.building_count ?? 0),
    coverage: Number(properties?.display_coverage ?? 0),
    contributors: overviewContributorFacts(properties, layers, preferences),
  };
}

function overviewContributorFacts(properties: GeoJSON.GeoJsonProperties | null | undefined, layers: readonly LayerMetadata[], preferences: AppPreferences): Array<{ label: string; value: string }> {
  const summaries = properties?.layer_summaries as Record<string, { value?: number | string; min?: number; median?: number; max?: number }> | undefined;
  return preferences.groups.flatMap((group) => group.criteria.flatMap((criterion) => {
    const layer = layers.find((candidate) => candidate.layer_id === criterion.layerId);
    if (!layer) return [];
    const summary = summaries?.[layer.layer_id];
    const value = layer.kind === "numeric" ? summary?.[preferences.overviewAggregation ?? "median"] : summary?.value;
    const rendered = typeof value === "number" ? formatLayerNumber(layer.unit, value) : typeof value === "string" ? finnishValue(value) : "tuntematon";
    return [{ label: layer.finnish_label, value: `${rendered}${typeof value === "number" ? unitSuffix(layer.unit) : ""}` }];
  }));
}

export function failedTileMessage(count: number): string {
  return `${count} karttalaattaa epäonnistui. Yritä uudelleen.`;
}

export function overviewLoadedMessage(): string {
  return "Lähennä nähdäksesi rakennukset.";
}

export function mergeTileGeometry(tiles: Iterable<GeoJSON.FeatureCollection>): GeoJSON.FeatureCollection {
  const features = new Map<string, GeoJSON.Feature>();
  for (const tile of tiles) for (const feature of tile.features) features.set(String(feature.properties?.building_id), feature);
  return { type: "FeatureCollection", features: [...features.values()] };
}

export function smallestBuildingFeature<T extends { geometry: GeoJSON.Geometry }>(features: readonly T[]): T | undefined {
  return features.reduce<T | undefined>((smallest, feature) => !smallest || geometryArea(feature.geometry) < geometryArea(smallest.geometry) ? feature : smallest, undefined);
}

export function MapView({ layers, preferences, activePlansOverlay = false, mainCycleRoutesOverlay = false, onSelect, onOpenGround, onAreaSummary }: { layers: readonly LayerMetadata[]; preferences: AppPreferences; activePlansOverlay?: boolean; mainCycleRoutesOverlay?: boolean; onSelect?: (building: { id: string; years: readonly number[]; status: string; values: Record<string, BuildingLayerValue> }) => void; onOpenGround?: () => void; onAreaSummary?: (summary: OverviewSummary) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const geometryRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const overviewRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const serviceDestinationsRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const latest = useRef({ layers, preferences });
  latest.current = { layers, preferences };
  const retryTilesRef = useRef<() => void>(() => {});
  const splitTilesRef = useRef(false);
  const [status, setStatus] = useState("Ladataan rakennuksia…");
  const [failedTiles, setFailedTiles] = useState(0);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: useCartoBasemap ? cartoStyleUrl(cartoKey) : localStyle,
      center: [24.94, 60.17],
      zoom: 12,
      attributionControl: useCartoBasemap ? { customAttribution: "© OpenStreetMap, © CARTO" } : false,
      transformRequest: useCartoBasemap ? cartoTransformRequest : undefined,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    container.current.querySelector<HTMLButtonElement>(".maplibregl-ctrl-zoom-in")?.setAttribute("aria-label", mapControlLabels.zoomIn);
    container.current.querySelector<HTMLButtonElement>(".maplibregl-ctrl-zoom-out")?.setAttribute("aria-label", mapControlLabels.zoomOut);
    const compass = container.current.querySelector<HTMLButtonElement>(".maplibregl-ctrl-compass");
    compass?.setAttribute("aria-label", mapControlLabels.resetNorth);
    compass?.setAttribute("title", mapControlLabels.resetNorth);
    container.current.querySelector<HTMLCanvasElement>(".maplibregl-canvas")?.setAttribute("aria-label", "Kartta");
    let cancelled = false;
    map.on("load", async () => {
      try {
        map.addSource("rakennukset", { type: "geojson", data: emptyGeometry() });
        map.addSource("alueet", { type: "geojson", data: emptyGeometry() });
        map.addSource("taustakartta", { type: "geojson", data: emptyGeometry() });
        map.addSource("asemakaavamuutokset", { type: "geojson", data: emptyGeometry() });
        map.addSource("paapyorareitit", { type: "geojson", data: emptyGeometry() });
        map.addSource("palvelukohteet", { type: "geojson", data: emptyGeometry(), cluster: true, clusterRadius: 42, clusterMaxZoom: 14 });
        if (!useCartoBasemap) {
          map.addLayer({ id: "taustavesi", type: "fill", source: "taustakartta", filter: ["==", ["get", "kind"], "water"], paint: { "fill-color": "#c9e3ea", "fill-opacity": 0.7 } });
          map.addLayer({ id: "taustavihrea", type: "fill", source: "taustakartta", filter: ["==", ["get", "kind"], "green"], paint: { "fill-color": "#d8e7d0", "fill-opacity": 0.6 } });
        }
        map.addLayer({ id: "taustaranta", type: "line", source: "taustakartta", filter: ["in", ["get", "kind"], ["literal", ["water", "waterway", "coastline"]]], paint: { "line-color": "#0f5f8f", "line-width": 1.5, "line-opacity": 0.9 } });
        map.addLayer({ id: "taustaraiteet", type: "line", source: "taustakartta", filter: ["==", ["get", "kind"], "rail"], paint: { "line-color": "#475569", "line-width": 1.4, "line-opacity": 0.75, "line-dasharray": [2, 1.5] } });
        map.addLayer({ id: "taustatiet", type: "line", source: "taustakartta", filter: ["==", ["get", "kind"], "road-major"], paint: { "line-color": "#94a3b8", "line-width": 1, "line-opacity": 0.4 } });
        map.addLayer({ id: "asemakaavamuutokset-taytto", type: "fill", source: "asemakaavamuutokset", paint: { "fill-color": "#d97706", "fill-opacity": 0.12 } });
        map.addLayer({ id: "asemakaavamuutokset-reuna", type: "line", source: "asemakaavamuutokset", paint: { "line-color": "#b45309", "line-width": 1.5, "line-opacity": 0.85 } });
        map.addLayer({ id: "paapyorareitit", type: "line", source: "paapyorareitit", paint: { "line-color": "#7c3aed", "line-width": 2.5, "line-opacity": 0.85 } });
        map.setLayoutProperty("asemakaavamuutokset-taytto", "visibility", activePlansOverlay ? "visible" : "none");
        map.setLayoutProperty("asemakaavamuutokset-reuna", "visibility", activePlansOverlay ? "visible" : "none");
        map.setLayoutProperty("paapyorareitit", "visibility", mainCycleRoutesOverlay ? "visible" : "none");
        map.addLayer({ id: "alueet", type: "fill", source: "alueet", layout: { visibility: visualizationVisibility(preferences) }, paint: { "fill-color": overviewPaint(layers, preferences), "fill-opacity": 0.36, "fill-outline-color": "#52616b" } });
        map.addLayer({
          id: "rakennukset",
          type: "fill",
          source: "rakennukset",
          layout: { visibility: visualizationVisibility(preferences) },
          paint: {
            "fill-color": visualizationPaint(emptyGeometry(), layers, preferences),
            "fill-opacity": 0.64,
          },
        });
        map.addLayer({ id: "palvelukohde-klusteri", type: "circle", source: "palvelukohteet", filter: ["has", "point_count"], paint: { "circle-color": "#dc2626", "circle-radius": ["interpolate", ["linear"], ["get", "point_count"], 1, 11, 10, 15, 25, 19], "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } });
        map.addLayer({ id: "palvelukohde-piste", type: "circle", source: "palvelukohteet", filter: ["!", ["has", "point_count"]], paint: { "circle-color": "#dc2626", "circle-radius": 6, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } });
        let destinationPopup: maplibregl.Popup | undefined;
        let destinationPopupRequest = 0;
        const closeDestinationPopup = () => {
          destinationPopup?.remove();
          destinationPopup = undefined;
        };
        const showDestinationPopup = async (event: maplibregl.MapLayerMouseEvent) => {
          const feature = event.features?.[0];
          if (!feature) return;
          const request = ++destinationPopupRequest;
          let names: string[];
          if (feature.properties?.cluster) {
            const source = map.getSource("palvelukohteet") as maplibregl.GeoJSONSource;
            const leaves = await source.getClusterLeaves(Number(feature.properties.cluster_id), Number(feature.properties.point_count), 0);
            names = leaves.map((leaf) => String(leaf.properties?.name ?? "")).filter(Boolean);
          } else names = [String(feature.properties?.name ?? "")].filter(Boolean);
          const html = destinationPopupHtml(names);
          if (request !== destinationPopupRequest || !html) return;
          closeDestinationPopup();
          destinationPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
            .setLngLat(event.lngLat)
            .setHTML(html)
            .addTo(map);
        };
        for (const layerId of ["palvelukohde-klusteri", "palvelukohde-piste"]) {
          map.on("mouseenter", layerId, (event) => {
            map.getCanvas().style.cursor = "pointer";
            void showDestinationPopup(event);
          });
          map.on("click", layerId, (event) => void showDestinationPopup(event));
          map.on("mouseleave", layerId, () => {
            destinationPopupRequest += 1;
            map.getCanvas().style.cursor = "";
            closeDestinationPopup();
          });
        }
        let activePlanPopup: maplibregl.Popup | undefined;
        const closeActivePlanPopup = () => {
          activePlanPopup?.remove();
          activePlanPopup = undefined;
        };
        map.on("mouseenter", "asemakaavamuutokset-taytto", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "asemakaavamuutokset-taytto", () => {
          map.getCanvas().style.cursor = "";
        });
        map.on("click", "asemakaavamuutokset-taytto", (event) => {
          const html = activePlanPopupHtml(event.features?.[0]?.properties);
          if (!html) return;
          closeDestinationPopup();
          closeActivePlanPopup();
          activePlanPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, offset: 10 })
            .setLngLat(event.lngLat)
            .setHTML(html)
            .addTo(map);
        });
        // The ~50 MB background GeoJSON is handed to MapLibre as a blob: URL so it
        // parses inside MapLibre's worker instead of blocking the main thread with a
        // JSON.parse at startup. Revoke the URL once the source has finished loading.
        void loadGzipObjectUrl(`${import.meta.env.BASE_URL}data/background/osm.geojson.gz`)
          .then((url) => {
            (map.getSource("taustakartta") as maplibregl.GeoJSONSource).setData(url);
            const revoke = (event: maplibregl.MapSourceDataEvent) => {
              if (event.sourceId === "taustakartta" && event.isSourceLoaded) {
                URL.revokeObjectURL(url);
                map.off("sourcedata", revoke);
              }
            };
            map.on("sourcedata", revoke);
          })
          .catch(() => undefined);
        void loadGzipJson<GeoJSON.FeatureCollection>(`${import.meta.env.BASE_URL}data/overlays/main-cycle-routes.geojson.gz`).then((overlay) => (map.getSource("paapyorareitit") as maplibregl.GeoJSONSource).setData(overlay)).catch(() => undefined);
        void loadGzipJson<GeoJSON.FeatureCollection>(`${import.meta.env.BASE_URL}data/overlays/active-plans.geojson.gz`)
          .then((overlay) => (map.getSource("asemakaavamuutokset") as maplibregl.GeoJSONSource).setData(overlay))
          .catch(() => undefined);
        void loadGzipJson<GeoJSON.FeatureCollection>(`${import.meta.env.BASE_URL}data/overlays/service-destinations.geojson.gz`)
          .then((destinations) => {
            serviceDestinationsRef.current = destinations;
            (map.getSource("palvelukohteet") as maplibregl.GeoJSONSource).setData(filteredServiceDestinations(destinations, latest.current.preferences));
          })
          .catch(() => undefined);
        let tileTier: BuildingTier | undefined;
        const selectFeature = async (feature: maplibregl.MapGeoJSONFeature) => {
          const tier = tileTier;
          const key = typeof feature.properties?.tile_key === "string" ? feature.properties.tile_key : undefined;
          const values = tier?.layerAttributePathTemplate && key
          ? await loadInspectorValues(key, String(feature.properties?.building_id), tier, latest.current.layers, latest.current.preferences, feature.properties?.layer_values as Record<string, BuildingLayerValue> | undefined)
            : (feature.properties?.layer_values as Record<string, BuildingLayerValue> | undefined) ?? {};
          onSelect?.({
          id: String(feature.properties?.building_id),
          years: (feature.properties?.building_year as number[] | undefined) ?? [],
          status: String(feature.properties?.display_status),
          values,
          });
        };
        map.on("click", "rakennukset", (event) => {
          if (map.queryRenderedFeatures(event.point, { layers: ["asemakaavamuutokset-taytto", "palvelukohde-klusteri", "palvelukohde-piste"] }).length) return;
          const feature = smallestBuildingFeature(event.features ?? []);
          if (!feature) return;
          void selectFeature(feature);
        });
        container.current?.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          const feature = smallestBuildingFeature(map.queryRenderedFeatures(map.project(map.getCenter()), { layers: ["rakennukset"] }));
          if (feature) void selectFeature(feature);
          else onOpenGround?.();
        });
        map.on("click", "alueet", (event) => {
          if (map.queryRenderedFeatures(event.point, { layers: ["asemakaavamuutokset-taytto", "palvelukohde-klusteri", "palvelukohde-piste"] }).length) return;
          const feature = event.features?.[0];
          if (!feature) return;
          const selected = latest.current.layers.find((layer) => layer.layer_id === latest.current.preferences.selectedVisualization);
          onAreaSummary?.(overviewSummary(feature.properties, selected, latest.current.layers, latest.current.preferences));
        });
        map.on("click", (event) => {
          if (!map.queryRenderedFeatures(event.point, { layers: ["rakennukset", "alueet", "asemakaavamuutokset-taytto", "palvelukohde-klusteri", "palvelukohde-piste"] }).length) {
            closeActivePlanPopup();
            onOpenGround?.();
          }
        });
        const manifest = await loadManifest();
        if (cancelled) return;
        if (!manifest.spatialPartitions) {
          const geometry = await loadInitialGeometry(manifest, latest.current.preferences);
          if (cancelled) return;
          setGeometry(map, geometry, latest.current.layers, latest.current.preferences, geometryRef);
          setStatus("Helsingin asuinrakennukset ladattu.");
          return;
        }
        tileTier = manifest.spatialPartitions.buildingTier;
        splitTilesRef.current = true;
        const loadedTiles = new Set<string>();
        const tileGeometry = new Map<string, GeoJSON.FeatureCollection>();
        const overviewGeometry = new Map<string, GeoJSON.FeatureCollection>();
        const overviewLayers = new Map<string, OverviewLayerPartition>();
        const loadedOverviewTiles = new Set<string>();
        const updateVisibleTiles = async () => {
          const tier = manifest.spatialPartitions?.buildingTier;
          if (!tier || cancelled) return;
          if (latest.current.preferences.selectedVisualization === EMPTY_VISUALIZATION) {
            map.setLayoutProperty("alueet", "visibility", "none");
            map.setLayoutProperty("rakennukset", "visibility", "none");
            setStatus("Valitse karttataso.");
            return;
          }
          if (map.getZoom() < tier.minZoom) {
            setGeometry(map, emptyGeometry(), latest.current.layers, latest.current.preferences, geometryRef);
            const overviewTier = overviewTierForZoom(manifest.spatialPartitions?.overviewTiers ?? [], map.getZoom());
            if (!overviewTier) {
            overviewRef.current = null;
            map.setLayoutProperty("alueet", "visibility", "none");
              setStatus(`Lähennä tasolle 10 nähdäksesi aluetiedot; rakennukset ja kokonaissopivuus tasolta ${tier.minZoom}.`);
              return;
            }
            const bounds = map.getBounds();
            const overviewKeys = overviewTileKeys(overviewTier, [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]);
            const requestedLayerIds = activeLayerIds(latest.current.preferences);
            const overviewLayerSignature = [...requestedLayerIds].sort().join(",");
            const keys = overviewKeys.filter((key) => !loadedOverviewTiles.has(`${overviewTier.geometryPathTemplate}|${key}|${overviewLayerSignature}`));
            let overviewFailures = 0;
            if (keys.length) {
              setStatus("Ladataan alueyhteenvetoa…");
              const attempts = await Promise.allSettled(keys.map(async (key) => {
                const geometryPath = overviewTilePath(overviewTier, key);
                const geometry = overviewGeometry.get(geometryPath) ?? await loadGzipJson<GeoJSON.FeatureCollection>(`${import.meta.env.BASE_URL}data/${geometryPath}`);
                const partitions = await Promise.all(requestedLayerIds.map(async (layerId) => {
                  const path = overviewLayerPath(overviewTier, layerId, key);
                  return [path, overviewLayers.get(path) ?? await loadGzipJson<OverviewLayerPartition>(`${import.meta.env.BASE_URL}data/${path}`)] as const;
                }));
                return { key, geometryPath, geometry, partitions };
              }));
              if (cancelled) return;
              const results = fulfilledValues(attempts);
              for (const result of results) {
                loadedOverviewTiles.add(`${overviewTier.geometryPathTemplate}|${result.key}|${overviewLayerSignature}`);
                overviewGeometry.set(result.geometryPath, result.geometry);
                for (const [path, partition] of result.partitions) overviewLayers.set(path, partition);
              }
              overviewFailures = attempts.length - results.length;
              setFailedTiles(overviewFailures);
            }
            if (cancelled || !overviewStillCurrent(map.getZoom(), tier.minZoom, overviewTier.geometryPathTemplate, overviewTierForZoom(manifest.spatialPartitions?.overviewTiers ?? [], map.getZoom())?.geometryPathTemplate)) return;
            if (requestedLayerIds.join(",") !== activeLayerIds(latest.current.preferences).join(",")) {
              void updateVisibleTiles();
              return;
            }
            const source = map.getSource("alueet") as maplibregl.GeoJSONSource;
            const current = latest.current;
            const overview = withSelectedServiceOverview(withSelectedGroceryOverview(mergeOverviewGeometry(
              mergeOverviewTiles(overviewKeys.flatMap((key) => {
                const geometry = overviewGeometry.get(overviewTilePath(overviewTier, key));
                return geometry ? [geometry] : [];
              })),
              Object.fromEntries(requestedLayerIds.map((layerId) => [layerId, mergeOverviewLayerPartitions(overviewKeys.flatMap((key) => {
                const partition = overviewLayers.get(overviewLayerPath(overviewTier, layerId, key));
                return partition ? [partition] : [];
              }))])),
            ), current.preferences), current.preferences);
            overviewRef.current = overview;
            source.setData(scoredOverview(overview, current.preferences.selectedVisualization, current.layers, current.preferences.overviewAggregation ?? "median", current.preferences));
            map.setLayoutProperty("alueet", "visibility", visualizationVisibility(current.preferences));
            map.setPaintProperty("alueet", "fill-color", overviewPaint(current.layers, current.preferences));
            setStatus(overviewFailures ? `Aluetietojen lataus keskeytyi osittain. ${failedTileMessage(overviewFailures)}` : overviewLoadedMessage());
            return;
          }
          overviewRef.current = null;
          map.setLayoutProperty("alueet", "visibility", "none");
          map.setLayoutProperty("rakennukset", "visibility", visualizationVisibility(latest.current.preferences));
          const bounds = map.getBounds();
          const layerSignature = [...activeLayerIds(latest.current.preferences)].sort().join(",");
          const availableTiles = new Set(tier.tileKeys);
          const keys = availableTileKeys(tileKeysForBounds([bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()], tier.tileZoom, tier.bufferTiles), availableTiles)
            .filter((key) => !loadedTiles.has(`${key}|${layerSignature}`));
          if (!keys.length) {
            const geometry = mergeTileGeometry(tileGeometry.values());
            setGeometry(map, geometry, latest.current.layers, latest.current.preferences, geometryRef);
            setStatus(`${geometry.features.length.toLocaleString("fi-FI")} näkyvää asuinrakennusta ladattu.`);
            return;
          }
          setStatus("Ladataan näkyviä rakennuksia…");
          const attempts = await Promise.allSettled(keys.map(async (key) => {
            const geometryPath = buildingTilePaths(key, tier);
            const geometry = await loadGzipJson<GeoJSON.FeatureCollection>(`${import.meta.env.BASE_URL}data/${geometryPath}`);
            const attributes = await loadSplitAttributes(key, tier, latest.current.preferences);
          const attached = attachAttributes(geometry, attributes, latest.current.preferences);
            return { key, geometry: { ...attached, features: attached.features.map((feature) => ({ ...feature, properties: { ...feature.properties, tile_key: key } })) } };
          }));
          if (cancelled) return;
          const results = fulfilledValues(attempts);
          for (const result of results) {
            loadedTiles.add(`${result.key}|${layerSignature}`);
            tileGeometry.set(result.key, result.geometry);
          }
          const retained = new Set(retainRecentKeys([...tileGeometry.keys()], maximumCachedTiles));
          for (const key of tileGeometry.keys()) {
            if (retained.has(key)) continue;
            tileGeometry.delete(key);
            loadedTiles.delete(key);
          }
          const geometry = mergeTileGeometry(tileGeometry.values());
          setGeometry(map, geometry, latest.current.layers, latest.current.preferences, geometryRef);
          const failures = attempts.length - results.length;
          setFailedTiles(failures);
          setStatus(failures ? `${geometry.features.length.toLocaleString("fi-FI")} asuinrakennusta ladattu; ${failedTileMessage(failures)}` : `${geometry.features.length.toLocaleString("fi-FI")} näkyvää asuinrakennusta ladattu.`);
        };
        retryTilesRef.current = () => { void updateVisibleTiles(); };
        map.on("moveend", () => { void updateVisibleTiles(); });
        await updateVisibleTiles();
      } catch (error) {
        if (!cancelled) setStatus(`Rakennusaineiston lataus epäonnistui: ${error instanceof Error ? error.message : "tuntematon virhe"}`);
      }
    });
    return () => {
      cancelled = true;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    for (const layerId of ["asemakaavamuutokset-taytto", "asemakaavamuutokset-reuna"]) {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", activePlansOverlay ? "visible" : "none");
    }
  }, [activePlansOverlay]);

  useEffect(() => { const map = mapRef.current; if (map?.isStyleLoaded() && map.getLayer("paapyorareitit")) map.setLayoutProperty("paapyorareitit", "visibility", mainCycleRoutesOverlay ? "visible" : "none"); }, [mainCycleRoutesOverlay]);

  useEffect(() => {
    if (splitTilesRef.current) retryTilesRef.current();
    const source = mapRef.current?.getSource("rakennukset") as maplibregl.GeoJSONSource | undefined;
    if (source && geometryRef.current) {
      source.setData(scoredGeometry(geometryRef.current, layers, preferences));
      mapRef.current?.setPaintProperty("rakennukset", "fill-color", visualizationPaint(geometryRef.current, layers, preferences));
      mapRef.current?.setLayoutProperty("rakennukset", "visibility", visualizationVisibility(preferences));
    }
    const overviewSource = mapRef.current?.getSource("alueet") as maplibregl.GeoJSONSource | undefined;
    if (overviewSource && overviewRef.current) {
      overviewSource.setData(scoredOverview(overviewRef.current, preferences.selectedVisualization, layers, preferences.overviewAggregation ?? "median", preferences));
      mapRef.current?.setPaintProperty("alueet", "fill-color", overviewPaint(layers, preferences));
      if (preferences.selectedVisualization === EMPTY_VISUALIZATION) mapRef.current?.setLayoutProperty("alueet", "visibility", "none");
    }
    const destinationsSource = mapRef.current?.getSource("palvelukohteet") as maplibregl.GeoJSONSource | undefined;
    if (destinationsSource && serviceDestinationsRef.current) destinationsSource.setData(filteredServiceDestinations(serviceDestinationsRef.current, preferences));
  }, [layers, preferences]);

  const selectedLayer = layers.find((layer) => layer.layer_id === preferences.selectedVisualization);
  const emptySelected = preferences.selectedVisualization === EMPTY_VISUALIZATION;
  const suitabilitySelected = preferences.selectedVisualization === "overall";
  const selectedBreaks = suitabilitySelected ? scoreBreaks : selectedLayer?.kind === "numeric" ? numericBreaks(emptyGeometry(), selectedLayer) : null;
  const legendItems = suitabilitySelected ? suitabilityLegendItems() : selectedLayer && selectedBreaks ? [...numericLegendItems(selectedLayer, selectedBreaks), { label: "Tieto puuttuu", color: "#475569" }] : [];

  return (
    <>
      <p role="status">{status}</p>
      {failedTiles ? <button type="button" onClick={() => retryTilesRef.current()}>Yritä uudelleen</button> : null}
      {!emptySelected && ((suitabilitySelected || selectedLayer?.kind === "numeric") && selectedBreaks ? <div className="map-continuous-legend" aria-label="Väriselite">
        <strong>{suitabilitySelected ? "Sopivuus (%)" : `${selectedLayer?.finnish_label}${selectedLayer && finnishUnit(selectedLayer.unit) ? ` (${finnishUnit(selectedLayer.unit)})` : ""}`}</strong>
        <div className="continuous-steps">{legendItems.slice().reverse().map((item) => <span key={item.label}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}</div>
      </div> : <div className="map-legend-swatches" aria-label="Väriselite">
        {visualizationLegendItems(geometryRef.current ?? emptyGeometry(), layers, preferences).map((item) => <span key={item.label}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}
      </div>)}
      <div aria-label="Karttanäkymä" ref={container} tabIndex={0} style={{ height: "min(70vh, 680px)", width: "100%" }} />
    </>
  );
}

export function scoredGeometry(geometry: GeoJSON.FeatureCollection, layers: readonly LayerMetadata[], preferences: AppPreferences): GeoJSON.FeatureCollection {
  return {
    ...geometry,
    features: geometry.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        ...displayProperties(
          (feature.properties?.layer_values as Record<string, { state: "known" | "partial" | "unknown" | "conflict"; value: number | string | null; values: readonly (number | string)[] }> | undefined) ?? {},
          layers,
          preferences,
        ),
      },
    })),
  };
}

export function scoredOverview(overview: GeoJSON.FeatureCollection, selectedVisualization: string, layers: readonly LayerMetadata[] = [], aggregation: "min" | "median" | "max" = "median", preferences?: AppPreferences): GeoJSON.FeatureCollection {
  const layer = layers.find((item) => item.layer_id === selectedVisualization);
  return {
    ...overview,
    features: overview.features.map((feature) => {
      const total = Number(feature.properties?.building_count ?? 0);
      const suitability = selectedVisualization === "overall" && preferences ? overviewSuitability(feature.properties, layers, preferences, aggregation) : null;
      const states = (feature.properties?.layer_state_counts as Record<string, Record<string, number>> | undefined)?.[selectedVisualization] ?? {};
      const covered = (states.known ?? 0) + (states.partial ?? 0);
      const summary = (feature.properties?.layer_summaries as Record<string, { value?: number | string; min?: number; median?: number; max?: number; mode_share?: number }> | undefined)?.[selectedVisualization];
      const displayValue = suitability?.value ?? (layer?.kind === "numeric" ? summary?.[aggregation] : summary?.value);
      const displayStatus = suitability?.status ?? (!summary ? "unknown" : covered < total ? "partial" : "known");
      return {
        ...feature,
        properties: {
          ...feature.properties,
          display_coverage: !total ? 0 : selectedVisualization === "overall" ? suitability?.coverage ?? 0 : covered / total,
          display_status: displayStatus,
          display_value: displayValue ?? "unknown",
          ...(layer?.kind === "categorical" && typeof summary?.mode_share === "number" ? { display_mode_share: summary.mode_share } : {}),
        },
      };
    }),
  };
}

type OverviewScoreInput = Record<string, {
  state: "known" | "partial" | "unknown" | "conflict";
  value: number | string | null;
  values: readonly (number | string)[];
}>;

function overviewSuitability(properties: GeoJSON.GeoJsonProperties | undefined, layers: readonly LayerMetadata[], preferences: AppPreferences, aggregation: "min" | "median" | "max"): { status: string; value?: number; coverage: number } {
  const inputs = (properties?.score_inputs as OverviewScoreInput[] | undefined) ?? [];
  const evaluations = inputs.map((values) => evaluateForPreferences(values, layers, preferences));
  const scores = evaluations.flatMap((evaluation) => evaluation.eligible && evaluation.score !== null ? [evaluation.score] : []).sort((left, right) => left - right);
  if (!scores.length) return { status: evaluations.some((evaluation) => !evaluation.eligible) ? "failed_dealbreaker" : "unknown", coverage: 0 };
  const middle = Math.floor(scores.length / 2);
  const value = aggregation === "min" ? scores[0] : aggregation === "max" ? scores[scores.length - 1] : scores.length % 2 ? scores[middle] : (scores[middle - 1] + scores[middle]) / 2;
  return { status: "known", value, coverage: scores.length / inputs.length };
}

export function initialGeometryPartition(partitions: readonly string[]): string {
  const partition = partitions.find((path) => path.includes("Helsinki"));
  if (!partition) throw new Error("Helsinki geometry partition is missing");
  return partition;
}

async function loadManifest() {
  const basePath = import.meta.env.BASE_URL;
  const response = await fetch(`${basePath}data/manifest.json`);
  if (!response.ok) throw new Error("Static data manifest request failed");
  return parseManifest(await response.text());
}

async function loadInitialGeometry(manifest: ReturnType<typeof parseManifest>, preferences: AppPreferences): Promise<GeoJSON.FeatureCollection> {
  const basePath = import.meta.env.BASE_URL;
  const [geometry, attributes] = await Promise.all([
    loadGzipJson<GeoJSON.FeatureCollection>(
    `${basePath}data/${initialGeometryPartition(manifest.geometryPartitions)}`,
    ),
    loadGzipJson<AttributePartition>(
      `${basePath}data/${initialAttributePartition(manifest.attributePartitions)}`,
    ),
  ]);
  return attachAttributes(geometry, attributes, preferences);
}

async function loadSplitAttributes(key: string, tier: BuildingTier, preferences: AppPreferences): Promise<AttributePartition> {
  const basePath = import.meta.env.BASE_URL;
  const core = await loadGzipJson<AttributePartition>(`${basePath}data/${tilePath(tier.coreAttributePathTemplate!, key)}`);
  const layers = await Promise.all(activeLayerIds(preferences).filter((layerId) => layerTileIsAvailable(tier, layerId, key)).map((layerId) => loadGzipJson<AttributePartition>(`${basePath}data/${layerTilePath(key, layerId, tier.layerAttributePathTemplate!)}`)));
  return { building_values: [
    ...(core.building_values ?? []),
    ...layers.flatMap((partition) => partition.building_values),
  ] };
}

async function loadInspectorValues(key: string, buildingId: string, tier: BuildingTier, layers: readonly LayerMetadata[], preferences: AppPreferences, current: Record<string, BuildingLayerValue> | undefined): Promise<Record<string, BuildingLayerValue>> {
  const basePath = import.meta.env.BASE_URL;
  const partitions = await Promise.all(layers.filter((layer) => layer.layer_id !== selectedGroceryLayerId && !selectionForLayerId(layer.layer_id) && layerTileIsAvailable(tier, layer.layer_id, key)).map((layer) => loadGzipJson<AttributePartition>(`${basePath}data/${layerTilePath(key, layer.layer_id, tier.layerAttributePathTemplate!)}`)));
  return withSelectedServiceValues(withSelectedGroceryValue({ ...(current ?? {}), ...Object.assign({}, ...partitions.map((partition) => buildingLayerValues(partition).get(buildingId) ?? {})) }, preferences), preferences);
}

export function layerTileIsAvailable(tier: BuildingTier, layerId: string, key: string): boolean {
  return tier.layerTileKeys === undefined || tier.layerTileKeys[layerId]?.includes(key) === true;
}

export function withSelectedGroceryOverview(overview: GeoJSON.FeatureCollection, preferences: AppPreferences): GeoJSON.FeatureCollection {
  return {
    ...overview,
    features: overview.features.map((feature) => {
      const inputs = Array.isArray(feature.properties?.score_inputs) ? feature.properties.score_inputs as Array<Record<string, { state: BuildingLayerValue["state"]; value: number | string | null; values: readonly (number | string)[] }>> : [];
      if (!inputs.length) return feature;
      const selected = inputs.map((input) => withSelectedGroceryValue(Object.fromEntries(Object.entries(input).map(([id, value]) => [id, { ...value, distribution: {}, coverage: value.state === "unknown" ? 0 : 1, evidenceIds: [], method: "derived", confidence: null }])) as Record<string, BuildingLayerValue>, preferences)[selectedGroceryLayerId]);
      const counts = selected.reduce<Record<string, number>>((result, value) => ({ ...result, [value.state]: (result[value.state] ?? 0) + 1 }), {});
      const values = selected.flatMap((value) => typeof value.value === "number" ? [value.value] : []).sort((left, right) => left - right);
      const middle = values.length ? values.length / 2 % 1 ? values[Math.floor(values.length / 2)] : (values[values.length / 2 - 1] + values[values.length / 2]) / 2 : undefined;
      const stateCounts = (feature.properties?.layer_state_counts as Record<string, object> | undefined) ?? {};
      const summaries = (feature.properties?.layer_summaries as Record<string, object> | undefined) ?? {};
      return { ...feature, properties: { ...feature.properties, score_inputs: inputs.map((input, index) => ({ ...input, [selectedGroceryLayerId]: selected[index] })), layer_state_counts: { ...stateCounts, [selectedGroceryLayerId]: counts }, layer_summaries: { ...summaries, [selectedGroceryLayerId]: values.length ? { min: values[0], median: middle, max: values.at(-1) } : null } } };
    }),
  };
}

export function withSelectedServiceOverview(overview: GeoJSON.FeatureCollection, preferences: AppPreferences): GeoJSON.FeatureCollection {
  return serviceSelections.reduce((result, selection) => ({
    ...result,
    features: result.features.map((feature) => {
      const inputs = Array.isArray(feature.properties?.score_inputs) ? feature.properties.score_inputs as Array<Record<string, { state: BuildingLayerValue["state"]; value: number | string | null; values: readonly (number | string)[] }>> : [];
      if (!inputs.length) return feature;
      const selected = inputs.map((input) => withSelectedServiceValue(Object.fromEntries(Object.entries(input).map(([id, value]) => [id, { ...value, distribution: {}, coverage: value.state === "unknown" ? 0 : 1, evidenceIds: [], method: "derived", confidence: null }])) as Record<string, BuildingLayerValue>, selection, preferences)[selection.layerId]);
      const counts = selected.reduce<Record<string, number>>((items, value) => ({ ...items, [value.state]: (items[value.state] ?? 0) + 1 }), {});
      const values = selected.flatMap((value) => typeof value.value === "number" ? [value.value] : []).sort((left, right) => left - right);
      const median = values.length ? values.length / 2 % 1 ? values[Math.floor(values.length / 2)] : (values[values.length / 2 - 1] + values[values.length / 2]) / 2 : undefined;
      const states = (feature.properties?.layer_state_counts as Record<string, object> | undefined) ?? {};
      const summaries = (feature.properties?.layer_summaries as Record<string, object> | undefined) ?? {};
      return { ...feature, properties: { ...feature.properties, score_inputs: inputs.map((input, index) => ({ ...input, [selection.layerId]: selected[index] })), layer_state_counts: { ...states, [selection.layerId]: counts }, layer_summaries: { ...summaries, [selection.layerId]: values.length ? { min: values[0], median, max: values.at(-1) } : null } } };
    }),
  }), overview);
}

function attachAttributes(geometry: GeoJSON.FeatureCollection, attributes: AttributePartition, preferences: AppPreferences): GeoJSON.FeatureCollection {
  const years = buildingYears(attributes);
  const values = buildingLayerValues(attributes);
  return {
    ...geometry,
    features: geometry.features.map((feature) => ({
      ...feature,
      properties: { ...feature.properties, building_year: years.get(String(feature.properties?.building_id)), layer_values: withSelectedServiceValues(withSelectedGroceryValue(values.get(String(feature.properties?.building_id)) ?? {}, preferences), preferences) },
    })),
  };
}

function emptyGeometry(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

function geometryArea(geometry: GeoJSON.Geometry): number {
  const polygonArea = (rings: GeoJSON.Position[][]) => rings.length ? Math.abs(ringArea(rings[0])) - rings.slice(1).reduce((sum, ring) => sum + Math.abs(ringArea(ring)), 0) : Infinity;
  if (geometry.type === "Polygon") return polygonArea(geometry.coordinates);
  if (geometry.type === "MultiPolygon") return geometry.coordinates.reduce((sum, polygon) => sum + polygonArea(polygon), 0);
  return Infinity;
}

function ringArea(ring: GeoJSON.Position[]): number {
  return ring.slice(1).reduce((sum, point, index) => sum + ring[index][0] * point[1] - point[0] * ring[index][1], 0) / 2;
}

function setGeometry(
  map: maplibregl.Map,
  geometry: GeoJSON.FeatureCollection,
  layers: readonly LayerMetadata[],
  preferences: AppPreferences,
  geometryRef: MutableRefObject<GeoJSON.FeatureCollection | null>,
): void {
  geometryRef.current = geometry;
  const source = map.getSource("rakennukset") as maplibregl.GeoJSONSource;
  source.setData(scoredGeometry(geometry, layers, preferences));
  map.setPaintProperty("rakennukset", "fill-color", visualizationPaint(geometry, layers, preferences));
}

function displayProperties(values: Record<string, { state: "known" | "partial" | "unknown" | "conflict"; value: number | string | null; values: readonly (number | string)[] }>, layers: readonly LayerMetadata[], preferences: AppPreferences): Record<string, string | number> {
  if (preferences.selectedVisualization !== "overall") {
    const value = values[preferences.selectedVisualization];
    return { display_status: value?.state ?? "unknown", display_value: typeof value?.value === "number" || typeof value?.value === "string" ? value.value : "unknown" };
  }
  const evaluation = evaluateForPreferences(values, layers, preferences);
  if (!evaluation.eligible) return { display_status: "failed_dealbreaker", display_value: "unknown" };
  if (evaluation.score === null) return { display_status: "no_score", display_value: "unknown" };
  return { display_status: evaluation.missingLayers.length ? "partial" : "scored", display_value: evaluation.score };
}

function evaluateForPreferences(values: Record<string, { state: "known" | "partial" | "unknown" | "conflict"; value: number | string | null; values: readonly (number | string)[] }>, layers: readonly LayerMetadata[], preferences: AppPreferences) {
  const definitions = layers.map((layer) => ({ id: layer.layer_id, kind: layer.kind }));
  return evaluateBuildingGroups(values, definitions, preferences.groups, preferences.missingDealbreakerPolicy);
}

export const EMPTY_VISUALIZATION = "none";

export function visualizationVisibility(preferences: AppPreferences): "none" | "visible" {
  return preferences.selectedVisualization === EMPTY_VISUALIZATION ? "none" : "visible";
}

export function visualizationPaint(geometry: GeoJSON.FeatureCollection, layers: readonly LayerMetadata[], preferences: AppPreferences): maplibregl.DataDrivenPropertyValueSpecification<string> {
  const layer = layers.find((item) => item.layer_id === preferences.selectedVisualization);
  if (!layer) return overallScorePaint;
  if (layer.kind === "numeric") {
    const breaks = numericBreaks(geometry, layer);
    if (breaks) return numericPaint(layer, breaks);
  }
  return categoricalPaint(layer);
}

export function visualizationLegend(geometry: GeoJSON.FeatureCollection, layers: readonly LayerMetadata[], preferences: AppPreferences, scaleBreaks: readonly number[] | null = null): string {
  const layer = layers.find((item) => item.layer_id === preferences.selectedVisualization);
  if (!layer) return "Selite: Sopivuus 0–100 %; tummanvihreä = parempi, tummanharmaa = tieto puuttuu, punainen = ehdoton vaatimus ei täyty.";
  const caveat = layer.caveat_ids.length ? ` Huomio: ${layer.caveat_ids.map(finnishCaveat).join(", ")}.` : "";
  if (layer.kind === "numeric") {
    const range = numericRange(geometry, layer);
    const breaks = scaleBreaks ?? numericBreaks(geometry, layer);
    const unit = unitSuffix(layer.unit);
    const direction = numericScheme(layer).direction;
    if (breaks && isMedianBoardingLayer(layer)) {
      return `Selite: ${layer.finnish_label}; jokaisella nousumäärällä on oma väri (${boardingCounts(layer, breaks).join(", ")}${unit}), tummanharmaa = tieto puuttuu.${caveat}`;
    }
    return range
      ? `Selite: ${layer.finnish_label}, julkaistu viitealue ${formatLayerNumber(layer.unit, range[0])}–${formatLayerNumber(layer.unit, range[1])}${unit}; värivälit perustuvat aineiston jakaumaan${breaks ? ` (${breaks.map((value) => formatLayerNumber(layer.unit, value)).join(", ")})` : ""}; ${direction}, tummanharmaa = tieto puuttuu.${caveat}`
      : `Selite: ${layer.finnish_label}, raaka-arvo${unit}; tummanharmaa = tieto puuttuu.${caveat}`;
  }
  return `Selite: ${layer.finnish_label}; jokaisella luokalla on oma väri, harmaa = tuntematon.${caveat}`;
}

export function visualizationLegendItems(geometry: GeoJSON.FeatureCollection, layers: readonly LayerMetadata[], preferences: AppPreferences): Array<{ label: string; color: string }> {
  const layer = layers.find((item) => item.layer_id === preferences.selectedVisualization);
  if (!layer) return [
    { label: "Pisteytetty", color: "#216869" }, { label: "Ei täytä ehtoa", color: "#b91c1c" }, { label: "Tieto puuttuu", color: "#475569" },
  ];
  if (layer.kind === "numeric") {
    const breaks = numericBreaks(geometry, layer);
    return breaks ? [...numericLegendItems(layer, breaks), { label: "Tieto puuttuu", color: "#475569" }] : [{ label: "Tieto puuttuu", color: "#475569" }];
  }
  return [
    ...layer.allowed_categories.filter((category) => category !== "mixed" && category !== "unknown").map((category, index) => ({ label: finnishValue(category), color: categoricalColors[index % categoricalColors.length] })),
    { label: "Sekoitus", color: "#6b7280" },
    { label: "Tieto puuttuu", color: "#475569" },
  ];
}

function overviewValueLabel(properties: GeoJSON.GeoJsonProperties | undefined, layer: LayerMetadata | undefined, aggregation: "min" | "median" | "max"): string | null {
  if (!layer) return null;
  const summary = (properties?.layer_summaries as Record<string, { value?: number | string; min?: number; median?: number; max?: number; mode_share?: number }> | undefined)?.[layer.layer_id];
  if (!summary) return null;
  if (layer.kind === "numeric" && typeof summary[aggregation] === "number") return `${({ min: "minimi", median: "mediaani", max: "maksimi" }[aggregation])} ${formatLayerNumber(layer.unit, summary[aggregation])}${unitSuffix(layer.unit)}`;
  if (layer.kind === "categorical" && typeof summary.value === "string") return `yleisin luokka ${finnishValue(summary.value)}${summary.mode_share === undefined ? "" : ` (${Math.round(summary.mode_share * 100)} % rakennuksista)`}`;
  return null;
}

const scoreBreaks = [0.02, 0.15, 0.36, 0.56, 0.72, 0.84, 0.92] as const;
const scoreColors = ["#e0f2fe", "#bae6fd", "#7dd3fc", "#5eead4", "#2dd4bf", "#0f766e", "#14532d"] as const;
const overallScorePaint = ["case", ["==", ["get", "display_status"], "failed_dealbreaker"], "#b91c1c", ["==", ["get", "display_status"], "no_score"], "#475569", ["==", ["get", "display_status"], "unknown"], "#475569", ["step", ["get", "display_value"], scoreColors[0], ...scoreBreaks.flatMap((value, index) => [value, scoreColors[index]])]] as maplibregl.DataDrivenPropertyValueSpecification<string>;

function overviewPaint(layers: readonly LayerMetadata[], preferences: AppPreferences): maplibregl.DataDrivenPropertyValueSpecification<string> {
  const layer = layers.find((item) => item.layer_id === preferences.selectedVisualization);
  if (!layer) return overallScorePaint;
  if (layer.kind === "numeric") {
    const scale = numericBreaks(emptyGeometry(), layer);
    if (scale) return numericPaint(layer, scale);
  }
  return categoricalPaint(layer);
}

const categoricalColors = ["#0072b2", "#e69f00", "#cc79a7", "#009e73", "#d55e00", "#56b4e9"];

function categoricalPaint(layer: LayerMetadata): maplibregl.DataDrivenPropertyValueSpecification<string> {
  const matches = layer.allowed_categories.filter((category) => category !== "mixed" && category !== "unknown").flatMap((category, index) => [category, categoricalColors[index % categoricalColors.length]]);
  return ["case", ["==", ["get", "display_status"], "unknown"], "#475569", ["match", ["get", "display_value"], ...matches, "mixed", "#6b7280", "unknown", "#475569", "#475569"]] as unknown as maplibregl.DataDrivenPropertyValueSpecification<string>;
}

function numericPaint(layer: LayerMetadata, breaks: readonly number[]): maplibregl.DataDrivenPropertyValueSpecification<string> {
  if (isMedianBoardingLayer(layer)) {
    const counts = boardingCounts(layer, breaks);
    const colors = counts.map((_, index) => numericScheme(layer).colors[index % numericScheme(layer).colors.length]);
    return ["case", ["==", ["get", "display_status"], "unknown"], "#475569", ["step", ["get", "display_value"], colors[0], ...counts.slice(1).flatMap((value, index) => [value - 0.5, colors[index + 1]])]] as maplibregl.DataDrivenPropertyValueSpecification<string>;
  }
  const colors = numericScheme(layer).colors.slice(0, breaks.length);
  return ["case", ["==", ["get", "display_status"], "unknown"], "#475569", ["step", ["get", "display_value"], colors[0], ...breaks.flatMap((value, index) => [value, colors[index]])]] as maplibregl.DataDrivenPropertyValueSpecification<string>;
}

function numericScheme(layer: LayerMetadata): { colors: readonly string[]; direction: string } {
  if (layer.layer_id === "building_year") return { colors: ["#f1f5f9", "#dbeafe", "#bfdbfe", "#93c5fd", "#60a5fa", "#2563eb", "#1e3a8a"], direction: "vaalea sininen = varhaisempi, tumma sininen = myöhempi" };
  if (layer.layer_id === "income_median_eur") return { colors: ["#e0f2fe", "#bae6fd", "#7dd3fc", "#5eead4", "#2dd4bf", "#0f766e", "#14532d"], direction: "tummanvihreä = parempi (suurempi); asteikko erottaa hyviä arvoja tarkemmin" };
  return { colors: ["#14532d", "#0f766e", "#2dd4bf", "#5eead4", "#7dd3fc", "#bae6fd", "#e0f2fe"], direction: "tummanvihreä = parempi (pienempi); asteikko erottaa hyviä arvoja tarkemmin" };
}

function numericLegendItems(layer: LayerMetadata, breaks: readonly number[]): Array<{ label: string; color: string }> {
  if (isMedianBoardingLayer(layer)) {
    const colors = numericScheme(layer).colors;
    const unit = unitSuffix(layer.unit);
    return boardingCounts(layer, breaks).map((value, index) => ({ color: colors[index % colors.length], label: `${value}${unit}` }));
  }
  const colors = numericScheme(layer).colors.slice(0, breaks.length);
  const unit = unitSuffix(layer.unit);
  const format = (value: number) => formatLayerNumber(layer.unit, value);
  return colors.map((color, index) => ({
    color,
    label: index === 0 ? `≤ ${format(breaks[1] ?? breaks[0])}${unit}` : index === colors.length - 1 ? `≥ ${format(breaks[breaks.length - 1])}${unit}` : `${format(breaks[index])}–${format(breaks[index + 1] ?? breaks[index])}${unit}`,
  }));
}

function isMedianBoardingLayer(layer: LayerMetadata): boolean {
  return layer.layer_id.startsWith("transit_workplace_") && layer.layer_id.endsWith("_median_boarding");
}

function boardingCounts(layer: LayerMetadata, breaks: readonly number[]): readonly number[] {
  const maximum = Math.max(0, Math.ceil(layer.visualization_range?.[1] ?? 0), ...breaks.map(Math.ceil));
  return Array.from({ length: maximum + 1 }, (_, index) => index);
}

export function suitabilityLegendItems(): Array<{ label: string; color: string }> {
  return [...scoreColors.map((color, index) => ({
    color,
    label: index === 0 ? `≤ ${formatNumber(scoreBreaks[1] * 100)} %` : index === scoreColors.length - 1 ? `≥ ${formatNumber(scoreBreaks[scoreBreaks.length - 1] * 100)} %` : `${formatNumber(scoreBreaks[index] * 100)}–${formatNumber(scoreBreaks[index + 1] * 100)} %`,
  })),
  { label: "Ehdoton vaatimus ei täyty", color: "#b91c1c" },
  { label: "Tieto puuttuu", color: "#475569" }];
}

function numericRange(geometry: GeoJSON.FeatureCollection, layer: LayerMetadata): [number, number] | null {
  if (layer.visualization_range) return layer.visualization_range;
  const values = geometry.features.flatMap((feature) => {
    const value = (feature.properties?.layer_values as Record<string, { value: number | string | null }> | undefined)?.[layer.layer_id]?.value;
    return typeof value === "number" && Number.isFinite(value) ? [value] : [];
  });
  if (!values.length) return null;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  return minimum === maximum ? [minimum - 1, maximum + 1] : [minimum, maximum];
}

function numericBreaks(geometry: GeoJSON.FeatureCollection, layer: LayerMetadata): readonly number[] | null {
  if (layer.visualization_breaks?.length && layer.visualization_breaks.every((value, index, values) => index === 0 || value > values[index - 1])) return layer.visualization_breaks;
  const range = numericRange(geometry, layer);
  return range ? visualizationPercentiles(layer).map((percentile) => range[0] + (range[1] - range[0]) * percentile) : null;
}

function visualizationPercentiles(layer: LayerMetadata): readonly number[] {
  if (layer.layer_id === "income_median_eur") return [0.02, 0.15, 0.36, 0.56, 0.72, 0.84, 0.92];
  if (layer.layer_id !== "building_year") return [0.02, 0.08, 0.16, 0.28, 0.44, 0.64, 0.85];
  return [0.02, 0.12, 0.28, 0.44, 0.60, 0.76, 0.92];
}


export function initialAttributePartition(partitions: readonly string[]): string {
  const partition = partitions.find((path) => path.includes("Helsinki"));
  if (!partition) throw new Error("Helsinki attribute partition is missing");
  return partition;
}
