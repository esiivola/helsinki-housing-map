import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { chromium } from "playwright";

const rootIndex = process.argv.indexOf("--root");
const root = rootIndex === -1 ? null : resolve(process.argv[rootIndex + 1]);
const reportIndex = process.argv.indexOf("--performance-report");
const reportPath = reportIndex === -1 ? null : resolve(process.argv[reportIndex + 1]);
const machineIndex = process.argv.indexOf("--reference-machine");
const referenceMachine = machineIndex === -1 ? null : process.argv[machineIndex + 1];
const base = process.env.E2E_BASE_PATH ?? "/helsinki-housing-map/";
if (!root) throw new Error("Usage: node scripts/verify-e2e.mjs --root <static-root>");
if (reportPath && !referenceMachine) throw new Error("--reference-machine is required with --performance-report");
const staticTransfer = { requests: 0, bytes: 0 };

const server = createServer(async (request, response) => {
  const path = new URL(request.url ?? "/", "http://localhost").pathname;
  const relative = path.endsWith("/") ? `${path}index.html` : path;
  const target = resolve(root, `.${relative}`);
  if (!target.startsWith(`${root}${sep}`)) {
    response.writeHead(403).end();
    return;
  }
  try {
    const content = await readFile(target);
    const type = target.endsWith(".html") ? "text/html" : target.endsWith(".js") ? "text/javascript" : target.endsWith(".css") ? "text/css" : "application/octet-stream";
    response.writeHead(200, { "content-type": type });
    response.end(content);
    staticTransfer.requests += 1;
    staticTransfer.bytes += content.byteLength;
  } catch {
    response.writeHead(404).end();
  }
});

await new Promise((resolveServer) => server.listen(0, "127.0.0.1", resolveServer));
const address = server.address();
if (!address || typeof address === "string") throw new Error("Could not start static server");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch();
const page = await browser.newPage();
const requests = [];
page.on("request", (request) => requests.push(request.url()));

async function clickFixtureBuilding(index) {
  const canvas = page.locator(".maplibregl-canvas");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("Map canvas is unavailable");
  const longitude = 24.93975 + index * 0.002;
  const latitude = 60.16975;
  const mercatorY = (value) => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
  const world = 512 * 2 ** 12;
  await canvas.click({ position: {
    x: box.width / 2 + (longitude - 24.94) * world / 360,
    y: box.height / 2 + (mercatorY(60.17) - mercatorY(latitude)) * world / (2 * Math.PI),
  } });
}

async function measureLoadedInspector(index) {
  return page.evaluate(({ index }) => new Promise((resolveMetric, rejectMetric) => {
    const canvas = document.querySelector(".maplibregl-canvas");
    if (!(canvas instanceof HTMLCanvasElement)) {
      rejectMetric(new Error("Map canvas is unavailable"));
      return;
    }
    const box = canvas.getBoundingClientRect();
    const longitude = 24.93975 + index * 0.002;
    const latitude = 60.16975;
    const mercatorY = (value) => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
    const world = 512 * 2 ** 12;
    const target = "Tunnus: fixture-building-mixed";
    const startedAt = performance.now();
    const observer = new MutationObserver(() => {
      if (!document.querySelector('aside[aria-label="Rakennuksen tiedot"]')?.textContent?.includes(target)) return;
      clearTimeout(timeout);
      observer.disconnect();
      resolveMetric(performance.now() - startedAt);
    });
    const timeout = setTimeout(() => {
      observer.disconnect();
      rejectMetric(new Error("Inspector did not open"));
    }, 1_000);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    canvas.dispatchEvent(new MouseEvent("click", {
      bubbles: true,
      button: 0,
      clientX: box.left + box.width / 2 + (longitude - 24.94) * world / 360,
      clientY: box.top + box.height / 2 + (mercatorY(60.17) - mercatorY(latitude)) * world / (2 * Math.PI),
      view: window,
    }));
  }), { index });
}

function percentile(samples, fraction) {
  return [...samples].sort((left, right) => left - right)[Math.ceil(samples.length * fraction) - 1];
}

function transferSnapshot() {
  return { ...staticTransfer };
}

function transferDelta(before) {
  return { requests: staticTransfer.requests - before.requests, bytes: staticTransfer.bytes - before.bytes };
}

try {
  await page.goto(`${origin}${base}`, { waitUntil: "networkidle" });
  const status = page.getByRole("status");
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent !== "Ladataan rakennuksia…", undefined, { timeout: 30_000 });
  if ((await status.textContent())?.includes("epäonnistui")) throw new Error(`Map failed to load: ${await status.textContent()}`);
  const zoomIn = page.getByRole("button", { name: "Lähennä karttaa" });
  const zoomInBox = await zoomIn.boundingBox();
  if (!zoomInBox || zoomInBox.width < 30 || zoomInBox.height < 30) throw new Error("Map controls are missing MapLibre's usable control styling");
  await page.getByRole("button", { name: "Nollaa kartan suunta" }).waitFor();
  const coldStartTransfer = transferSnapshot();
  await page.getByRole("button", { name: "Omat kriteerit" }).click();
  const settingsDialog = page.getByRole("dialog", { name: "Omat kriteerit" });
  const desktopSettings = await settingsDialog.boundingBox();
  if (!desktopSettings || desktopSettings.x < 800) throw new Error("Desktop settings did not open beside its trigger");
  if (!await settingsDialog.getByRole("button", { name: "Sulje", exact: true }).evaluate((element) => document.activeElement === element)) throw new Error("Settings close button did not receive focus");
  await page.keyboard.press("Escape");
  await settingsDialog.waitFor({ state: "detached" });
  if (!await page.getByRole("button", { name: "Omat kriteerit" }).evaluate((element) => document.activeElement === element)) throw new Error("Settings trigger did not regain focus after closing");
  await page.getByLabel("Karttanäkymä", { exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.locator('aside[aria-label="Karttapisteen tiedot"]').waitFor();
  await page.keyboard.press("Escape");
  await page.locator('aside[aria-label="Karttapisteen tiedot"]').waitFor({ state: "detached" });
  const mapMenu = page.locator(".map-menu");
  await mapMenu.locator(":scope > summary").click();
  await mapMenu.getByLabel("Näytettävä karttataso").selectOption("overall");
  await mapMenu.locator(":scope > summary").click();
  await clickFixtureBuilding(3);
  const inspector = page.locator('aside[aria-label="Rakennuksen tiedot"]');
  if (!await inspector.getByRole("heading", { name: "Rakennuksen tiedot" }).evaluate((element) => document.activeElement === element)) throw new Error("Inspector heading did not receive focus");
  await inspector.locator("details.inspector-evidence > summary").click();
  await inspector.getByText("Tunnus: fixture-building-mixed").waitFor();
  await inspector.getByText(/Maanomistus: sekoittunut.*osuudet: kaupunki 60 %, muu omistaja 40 %/).waitFor();
  await inspector.getByRole("button", { name: "Tietoa palvelusta" }).click();
  const info = page.getByRole("dialog", { name: "Tietoa palvelusta" });
  const sourceLink = info.getByRole("link", { name: "Avaa lähde: Espoo city land ownership" });
  await sourceLink.waitFor();
  if (await sourceLink.getAttribute("href") !== "https://example.test/espoo") throw new Error("Evidence source link is missing");
  await info.getByText("CC BY 4.0").waitFor();
  await page.waitForFunction(() => {
    const button = document.querySelector('[role="dialog"] button[data-dialog-initial-focus]');
    return document.activeElement === button;
  });
  await page.keyboard.press("Escape");
  await info.waitFor({ state: "detached" });
  if (!await inspector.getByRole("button", { name: "Tietoa palvelusta" }).evaluate((element) => document.activeElement === element)) throw new Error("Information trigger did not regain focus after closing");
  await inspector.getByRole("button", { name: "Sulje" }).click();
  if (!await page.getByLabel("Karttanäkymä", { exact: true }).evaluate((element) => document.activeElement === element)) throw new Error("Map did not receive focus after closing the inspector");
  await page.getByRole("button", { name: "Omat kriteerit" }).click();
  const settingsPanel = page.getByRole("dialog", { name: "Omat kriteerit" });
  await settingsPanel.getByLabel("Lisää kriteeri").selectOption("noise_day_upper_db");
  await settingsPanel.getByRole("button", { name: "Lisää kriteeri" }).click();
  const noise = settingsPanel.locator(".criterion-row").filter({ hasText: "Päivämelun yläraja" });
  const noiseMaximum = noise.locator('input[type="number"]').nth(1);
  await noiseMaximum.click();
  const initialNoiseMaximum = await noiseMaximum.inputValue();
  const originalNoiseMaximum = await noiseMaximum.elementHandle();
  if (!originalNoiseMaximum) throw new Error("Numeric range input is unavailable");
  await noiseMaximum.pressSequentially("5");
  if (!await originalNoiseMaximum.evaluate((element) => document.activeElement === element)) throw new Error("Numeric range input lost focus after its first character");
  await noiseMaximum.pressSequentially("5");
  if (await noiseMaximum.inputValue() !== `${initialNoiseMaximum}55`) throw new Error("Numeric range input did not retain sequential typing");
  await noise.locator('input[type="number"]').nth(1).fill("55");
  await noise.getByLabel("Pakollinen vaatimus").check();
  await settingsPanel.getByRole("button", { name: "Sulje", exact: true }).click();
  await settingsPanel.waitFor({ state: "detached" });
  await clickFixtureBuilding(1);
  await inspector.locator("details.inspector-evidence > summary").click();
  await inspector.getByText("Tunnus: fixture-building-noise").waitFor();
  await inspector.getByText(/Pakollinen kriteeri ei täyty: Päivämelun yläraja/).waitFor();
  await inspector.getByRole("button", { name: "Sulje" }).click();
  await clickFixtureBuilding(2);
  await inspector.locator("details.inspector-evidence > summary").click();
  await inspector.getByText("Tunnus: fixture-building-partial").waitFor();
  await inspector.getByText("Pakolliset kriteerit täyttyvät").waitFor();
  await inspector.getByText(/Osittainen tieto: Päivämelun yläraja/).waitFor();
  await inspector.getByRole("button", { name: "Sulje" }).click();
  await page.getByRole("button", { name: "Omat kriteerit" }).click();
  await settingsPanel.getByLabel("Älä hyväksy rakennusta, jos pakollisen vaatimuksen tieto puuttuu").check();
  await settingsPanel.getByRole("button", { name: "Sulje", exact: true }).click();
  await settingsPanel.waitFor({ state: "detached" });
  await clickFixtureBuilding(2);
  await inspector.locator("details.inspector-evidence > summary").click();
  await inspector.getByText(/Pakollinen kriteeri ei täyty: Päivämelun yläraja/).waitFor();
  await inspector.getByRole("button", { name: "Sulje" }).click();
  await page.getByRole("button", { name: "Omat kriteerit" }).click();
  await noise.getByRole("button", { name: "Poista" }).click();
  await noise.waitFor({ state: "detached" });
  await settingsPanel.getByRole("button", { name: "Sulje", exact: true }).click();
  await settingsPanel.waitFor({ state: "detached" });
  if (await page.locator(".criterion-row").filter({ hasText: "Päivämelun yläraja" }).count() !== 0) throw new Error("Deleting a criterion left it active");
  await mapMenu.locator(":scope > summary").click();
  const mapLayer = mapMenu.getByLabel("Näytettävä karttataso");
  await mapLayer.selectOption("selected_grocery_walk_m");
  const grocerySelection = mapMenu.locator(".map-display-controls .grocery-store-selection");
  await grocerySelection.getByLabel("Lidl").uncheck();
  if (await grocerySelection.getByLabel("Lidl").isChecked()) throw new Error("Grocery-store selection did not update");
  await grocerySelection.getByLabel("Lidl").check();
  await mapLayer.selectOption("income_median_eur");
  const overviewAggregation = page.locator(".overview-aggregation select");
  await overviewAggregation.selectOption("max");
  if (await overviewAggregation.inputValue() !== "max") throw new Error("Overview aggregation did not update");
  await page.getByLabel("Väriselite").getByText("Mediaanitulot (EUR)").waitFor();
  if (await page.locator(".continuous-steps span").count() < 4) throw new Error("Distribution-based numeric legend did not render its colour classes");
  await mapMenu.locator(":scope > summary").click();
  await mapMenu.locator(".map-display-controls").waitFor({ state: "hidden" });
  await page.reload({ waitUntil: "networkidle" });
  await mapMenu.locator(":scope > summary").click();
  await mapLayer.waitFor({ state: "visible" });
  if (await mapLayer.inputValue() !== "income_median_eur") throw new Error("Saved visualization was not restored");
  await overviewAggregation.waitFor({ state: "visible" });
  if (await overviewAggregation.inputValue() !== "max") throw new Error("Saved overview aggregation was not restored");
  const preferenceUpdateMilliseconds = [];
  const layerSwitchTransfer = transferSnapshot();
  for (let index = 0; index < 20; index += 1) {
    const startedAt = performance.now();
    await mapLayer.selectOption(index % 2 ? "overall" : "income_median_eur");
    await page.waitForTimeout(0);
    preferenceUpdateMilliseconds.push(performance.now() - startedAt);
  }
  await mapMenu.locator(":scope > summary").click();
  await mapMenu.locator(".map-display-controls").waitFor({ state: "hidden" });
  const inspectorMilliseconds = [];
  for (let index = 0; index < 20; index += 1) {
    inspectorMilliseconds.push(await measureLoadedInspector(3));
    await inspector.getByRole("button", { name: "Sulje" }).click();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await mapMenu.locator(":scope > summary").click();
  const mapMenuBox = await mapMenu.boundingBox();
  if (!mapMenuBox || mapMenuBox.width !== 390 || mapMenuBox.y + mapMenuBox.height !== 844) throw new Error("Mobile map controls are not a bottom sheet");
  await mapMenu.locator(":scope > summary").click();
  await mapMenu.locator(".map-display-controls").waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Omat kriteerit" }).click();
  const settingsBox = await settingsPanel.boundingBox();
  if (!settingsBox || settingsBox.width !== 390 || settingsBox.y + settingsBox.height !== 844) throw new Error("Mobile settings are not a bottom sheet");
  await settingsPanel.getByRole("button", { name: "Sulje", exact: true }).click();
  await settingsPanel.waitFor({ state: "detached" });
  await clickFixtureBuilding(3);
  const mobileInspector = await inspector.boundingBox();
  if (!mobileInspector || mobileInspector.width !== 390 || mobileInspector.y + mobileInspector.height !== 844) throw new Error("Mobile inspector is not a bottom sheet");
  await inspector.getByRole("button", { name: "Sulje" }).click();
  const performanceReport = {
    browser: browser.version(),
    reference_machine: referenceMachine,
    preference_update_p95_ms: percentile(preferenceUpdateMilliseconds, 0.95),
    loaded_inspector_p95_ms: percentile(inspectorMilliseconds, 0.95),
    cold_start_static_requests: coldStartTransfer.requests,
    cold_start_static_bytes: coldStartTransfer.bytes,
    layer_switch_static_requests: transferDelta(layerSwitchTransfer).requests,
    layer_switch_static_bytes: transferDelta(layerSwitchTransfer).bytes,
  };
  console.log(JSON.stringify({ performance: performanceReport }));
  if (performanceReport.preference_update_p95_ms > 200) throw new Error(`Preference update p95 exceeded 200 ms: ${performanceReport.preference_update_p95_ms}`);
  if (performanceReport.loaded_inspector_p95_ms > 100) throw new Error(`Loaded inspector p95 exceeded 100 ms: ${performanceReport.loaded_inspector_p95_ms}`);
  if (reportPath) await writeFile(reportPath, JSON.stringify(performanceReport));
  if (requests.some((url) => !url.startsWith(origin))) throw new Error("E2E run made a non-static runtime request");
} finally {
  await browser.close();
  await new Promise((resolveServer) => server.close(resolveServer));
}
