# Helsinki Metropolitan Apartment Location Explorer

Static map application with an offline Python spatial-data pipeline.

## Verified commands

Create a project-local environment and install the currently required packages:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install shapely pytest
```

Run the pipeline contract tests:

```sh
.venv/bin/python -m pytest
```

Build the deterministic static fixture bundle:

```sh
.venv/bin/python -m pipeline fixture-release tests/fixtures/release_fixture.json /tmp/helsinki-housing-fixture
```

Build the validated HSY release from its immutable local snapshot. The command writes only public building IDs, geometry, construction-year values, and explicit unknown values; it does not publish source address fields.

```sh
.venv/bin/python -m pipeline hsy-release data/raw/hsy_buildings_complete.geojson web/public/data \
  --retrieved-at 2026-08-26T23:15:17+03:00 \
  --vintage 2026-08-26 \
  --checksum sha256:9b7e3fb33bd162d9036d68be83b74a7162134ea7c10a0e64055ea83bf9c31c44
```

### Education and wellbeing service snapshots

Download the published Service Map units for the daycare and school groups:

```sh
.venv/bin/python scripts/download_service_map_snapshot.py data/raw/service_map_education_YYYY-MM-DD.geojson
```

The PTV downloader requires an API key through the environment. It records physical locations for the configurable health and social-service groups, using linked PTV service classes for dental care, neuvola, mental-health/substance-use, and social services. Set `PTV_API_KEY` in your shell without adding it to a file or command history, then run:

```sh
.venv/bin/python scripts/download_ptv_health_snapshot.py data/raw/ptv_wellbeing_YYYY-MM-DD.geojson
```

Record the two SHA-256 checksums and pass their snapshot-specific retrieval time, vintage, and checksum to `hsy-release`:

```sh
shasum -a 256 data/raw/service_map_education_YYYY-MM-DD.geojson data/raw/ptv_wellbeing_YYYY-MM-DD.geojson

.venv/bin/python -m pipeline hsy-release data/raw/hsy_buildings_complete.geojson web/public/data \
  --retrieved-at ... --vintage ... --checksum ... \
  --service-map-snapshot data/raw/service_map_education_YYYY-MM-DD.geojson \
  --service-map-retrieved-at ... --service-map-vintage YYYY-MM-DD --service-map-checksum sha256:... \
  --ptv-health-snapshot data/raw/ptv_wellbeing_YYYY-MM-DD.geojson \
  --ptv-health-retrieved-at ... --ptv-health-vintage YYYY-MM-DD --ptv-health-checksum sha256:...
```

### Local HSY green-cover snapshot

The green-cover source remains local until the public release builder derives the permitted per-building percentage. Download the five 2024 vegetation classes with the resumable script; it preserves its checkpoint after network errors and keeps retrying transient HSY 429/502/503/504 responses. Use Ctrl-C to stop safely; rerunning resumes at the last completed page:

```sh
node scripts/download_hsy_green_cover.mjs
```

The script pauses ten seconds between WFS pages. To use a slower interval during HSY service instability:

```sh
HSY_WFS_DELAY_MS=30000 node scripts/download_hsy_green_cover.mjs
```

To re-download just one damaged source, append its layer identifier:

```sh
HSY_WFS_DELAY_MS=30000 node scripts/download_hsy_green_cover.mjs maanpeite_muu_avoin_matala_kasvillisuus_2024
```

If the five snapshots were downloaded with the earlier page-separator bug, repair the known first-page defect locally without downloading them again. This command validates the expected defect and replaces each source only after its repaired copy is complete:

```sh
node scripts/repair_hsy_green_cover_geojson.mjs --replace
```

Validate all local snapshots before starting the expensive release build:

```sh
.venv/bin/python scripts/verify_hsy_green_cover.py
```

After all five files are complete, include the cycling network and each green-cover class in the public build:

```sh
.venv/bin/python -m pipeline hsy-release data/raw/hsy_buildings_complete.geojson web/public/data \
  --retrieved-at 2026-08-26T23:15:17+03:00 \
  --vintage 2026-08-26 \
  --checksum sha256:9b7e3fb33bd162d9036d68be83b74a7162134ea7c10a0e64055ea83bf9c31c44 \
  --main-cycle-network-snapshot data/raw/helsinki_cycle_network_2026-08-31.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_2_10m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_10_15m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_15_20m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_yli20m_2024.geojson
```

For the normal local release, prefer the resumable staging script instead. It builds and verifies `data/work/web-public-data-next` before synchronizing it to `web/public/data`; if the final synchronization is interrupted, rerun the same command to reuse the verified staging output. It retains the green-cover checkpoints under `data/work/green-cover-300m`.

```sh
bash scripts/build_local_release_with_green_cover.sh
bash scripts/build_web_release.sh
```

To resume any green-cover download, build or reuse validated public data artifacts, and then build the web application in one command, run:

```sh
bash scripts/update_public_release.sh
```

Completed green-cover downloads are skipped, a verified staging bundle is reused, and the final data copy transfers only changed files. Rerun this same command after an interruption.

Run the static web application checks and production build:

```sh
cd web
npm test
npm run build
python3 -m http.server 4174 --directory dist
```

The production build copies the large static data set after compiling the app. If it is interrupted, rerun the same `npm run build` command: the data copy continues from retained partial files instead of starting over. It can take a long time when the data has changed substantially; the progress display reports the current transfer.

The build prints which basemap it will ship. To ship CARTO's Positron vector basemap instead of the bundled offline OSM fallback, provide a build-time `VITE_CARTO_KEY`, either by exporting it or by writing an untracked `web/.env.production.local`:

```sh
echo 'VITE_CARTO_KEY=your-carto-key' > web/.env.production.local
```

Vite inlines the value at build time, so the key is public in the deployed bundle — use a CARTO key restricted to the deployment's domain. Without a key the build ships the offline basemap and prints a note saying so.

From the repository root, the equivalent direct command is:

```sh
bash scripts/build_web_release.sh
```

Run the complete local end-to-end proof, including a GitHub Pages subpath and an automated browser:

```sh
sh scripts/verify_e2e.sh
```

Record the browser performance run in the public release audit after the data release is complete. This builds the deterministic fixture through the real pipeline, tests it with a local-only static server, writes the retained raw report to `data/work/reference-performance.json`, validates the p95 targets, updates `web/public/data/audit.json`, then rebuilds the deployable static files.

```sh
sh scripts/record_release_performance.sh "Apple Silicon MacBook Pro"
```

Benchmark the offline OSM supermarket routing path:

```sh
time .venv/bin/python scripts/benchmark_osm_routing.py
```

## Dataset publication status

The public release contains the unified residential location dataset for the Helsinki metropolitan area. It contains only data listed in the public `sources.json`; that manifest provides the applicable attribution, licence, vintage, and processing notes.

Before deployment, verify that every source ID referenced by `layers.json` appears in `sources.json`, no excluded input appears in a public artifact, and the visible source list carries the required attribution. The checked-in public artifacts pass the source-reference check; rerun it after every data build.

### GitHub Pages data release

The published web-data bundle is a GitHub Release asset, not a Git-tracked directory. This keeps the repository usable while the Pages workflow still deploys the complete static site. Package the already validated `web/public/data` directory with a date-based tag:

```sh
bash scripts/package_public_data_release.sh /private/tmp/public-data-YYYY-MM-DD.tar.gz
```

Record the reported SHA-256 and release tag in `web/public-data-release.json`. Create the matching GitHub Release and upload the archive before pushing `main`; the Pages workflow downloads, verifies, and extracts that exact asset before building `web/dist`.

## Pending release tasks

### Install the local OpenTripPlanner JAR

The JAR is a local build tool, not a published web artifact. Do not keep it in `/private/tmp`, which macOS may clear. Download the official OpenTripPlanner 2.9.0 artifact once to a durable project-local tools directory and verify its published SHA-1:

```sh
mkdir -p data/tools
curl -fL --retry 3 -o data/tools/otp-shaded-2.9.0.jar \
  https://repo.maven.apache.org/maven2/org/opentripplanner/otp-shaded/2.9.0/otp-shaded-2.9.0.jar
echo 'ba2a582650fd3703c37ddd2ebe3fa92494cc7406  data/tools/otp-shaded-2.9.0.jar' | shasum -a 1 -c -
```

### Build the morning-commute layer input

This is the published public-transit layer. It routes the configured representative Wednesday from 07:00 through 08:00 inclusive at five-minute intervals and stores resumable local Parquet batches. Supply the completed directory with `--morning-transit-batches` when building the static release; it becomes the map layer `Pisin paras aamumatka keskustaan`.

```sh
.venv/bin/python scripts/build_transit_batches.py \
  data/raw/hsy_buildings_complete.geojson \
  --osm data/raw/hsl_osm_2026-08-25.pbf \
  --gtfs data/raw/hsl_gtfs_2026-08-27.zip \
  --java /opt/homebrew/opt/openjdk@25/bin/java \
  --jar data/tools/otp-shaded-2.9.0.jar \
  --output data/work/transit-morning-batches \
  --morning-commute
```

### Build workplace morning-commute research batches

This local-only research run uses the same representative Wednesday and 07:00–08:00 five-minute samples for Ruoholahti, Keilaniemi, Rautatieasema, Kamppi, Pasila, Kalasatama, Tapiola, Leppävaara, Aviapolis, Tikkurila, and Myyrmäki. Each destination and batch has its own Parquet file, so `Ctrl-C` is safe: rerunning the exact command skips valid completed batches. Every sample keeps duration, transfers, walking seconds, and the distinct non-walking OTP transport modes.

```sh
.venv/bin/python scripts/build_transit_batches.py \
  data/raw/hsy_buildings_complete.geojson \
  --osm data/raw/hsl_osm_2026-08-25.pbf \
  --gtfs data/raw/hsl_gtfs_2026-08-27.zip \
  --java /opt/homebrew/opt/openjdk@25/bin/java \
  --jar data/tools/otp-shaded-2.9.0.jar \
  --output data/work/transit-workplace-morning-batches \
  --workplace-commute
```
