#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"

node "$project_dir/scripts/download_hsy_green_cover.mjs"
bash "$project_dir/scripts/build_local_release_with_green_cover.sh"
bash "$project_dir/scripts/build_web_release.sh"
