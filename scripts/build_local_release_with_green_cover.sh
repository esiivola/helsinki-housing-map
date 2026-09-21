#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
staging_dir="$project_dir/data/work/web-public-data-next"
input_fingerprint="$({
  shasum pipeline/build.py pipeline/export/web_bundle.py pipeline/sources/osm.py pipeline/sources/planning.py pipeline/sources/service_map.py pipeline/sources/ptv.py
  stat -f '%N:%z:%m' \
    data/raw/hsy_buildings_complete.geojson data/raw/helsinki_cycle_network_2026-08-31.geojson \
    data/raw/service_map_education_2026-09-09.geojson data/raw/ptv_wellbeing_2026-09-10.geojson \
    data/raw/hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson \
    data/raw/hsy_maanpeite_puusto_2_10m_2024.geojson data/raw/hsy_maanpeite_puusto_10_15m_2024.geojson \
    data/raw/hsy_maanpeite_puusto_15_20m_2024.geojson data/raw/hsy_maanpeite_puusto_yli20m_2024.geojson
} | shasum -a 256 | awk '{print $1}')"

if ! .venv/bin/python scripts/verify_hsy_green_cover.py; then
  echo "Green-cover snapshots are missing or incomplete. Resume them with:" >&2
  echo "  node scripts/download_hsy_green_cover.mjs" >&2
  exit 1
fi

if [[ -d "$staging_dir" ]]; then
  .venv/bin/python scripts/migrate_overview_artifacts.py "$staging_dir"
fi

if [[ -d "$staging_dir" ]] \
  && [[ -f "$staging_dir/.build-inputs.sha256" ]] \
  && [[ "$(<"$staging_dir/.build-inputs.sha256")" == "$input_fingerprint" ]] \
  && .venv/bin/python -m pipeline verify-release "$staging_dir" \
  && jq -e '.[] | select(.layer_id == "health_service_social_services_walk_m")' "$staging_dir/layers.json" >/dev/null \
  && jq -e '.overlays["service-destinations"] == "overlays/service-destinations.geojson.gz"' "$staging_dir/manifest.json" >/dev/null \
  && gzip -cd "$staging_dir/overlays/service-destinations.geojson.gz" | jq -e 'any(.features[]; .properties.layer_id == "grocery_store_prisma_walk_m" and .geometry.coordinates == [24.92991, 60.19846])' >/dev/null; then
  :
else
  rm -rf "$staging_dir"
  .venv/bin/python -m pipeline hsy-release data/raw/hsy_buildings_complete.geojson "$staging_dir" \
  --retrieved-at 2026-08-26T23:15:17+03:00 \
  --vintage 2026-08-26 \
  --checksum sha256:9b7e3fb33bd162d9036d68be83b74a7162134ea7c10a0e64055ea83bf9c31c44 \
  --main-cycle-network-snapshot data/raw/helsinki_cycle_network_2026-08-31.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_2_10m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_10_15m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_15_20m_2024.geojson \
  --green-cover-snapshot data/raw/hsy_maanpeite_puusto_yli20m_2024.geojson \
  --service-map-snapshot data/raw/service_map_education_2026-09-09.geojson \
  --service-map-retrieved-at 2026-09-09T23:44:40+03:00 \
  --service-map-vintage 2026-09-09 \
  --service-map-checksum sha256:80456f2b81c4659cf12122d719410dd0df595407b4b262ed12e94351b0d6a2b7 \
  --ptv-health-snapshot data/raw/ptv_wellbeing_2026-09-10.geojson \
  --ptv-health-retrieved-at 2026-09-10T08:22:06+0300 \
  --ptv-health-vintage 2026-09-10 \
  --ptv-health-checksum sha256:b392442a9fd53a132358f21a35b76bdb2028ce6846eb8851a47da1d15332ced6 \
  --green-cover-checkpoint-dir data/work/green-cover-300m
  .venv/bin/python -m pipeline verify-release "$staging_dir"
  printf '%s\n' "$input_fingerprint" > "$staging_dir/.build-inputs.sha256"
fi

rsync -a --delete-delay --partial --no-whole-file "$staging_dir/" "$project_dir/web/public/data/"
.venv/bin/python -m pipeline verify-release "$project_dir/web/public/data"
