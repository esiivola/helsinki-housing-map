#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"

.venv/bin/python -m pipeline hsy-release data/raw/hsy_buildings_complete.geojson web/public/data \
  --retrieved-at 2026-08-26T23:15:17+03:00 \
  --vintage 2026-08-26 \
  --checksum sha256:9b7e3fb33bd162d9036d68be83b74a7162134ea7c10a0e64055ea83bf9c31c44
