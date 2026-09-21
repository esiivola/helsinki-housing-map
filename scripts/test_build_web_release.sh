#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
build_script="$script_dir/build_web_release.sh"
data_build_script="$script_dir/build_local_release_with_green_cover.sh"
release_script="$script_dir/update_public_release.sh"
green_cover_download_script="$script_dir/download_hsy_green_cover.mjs"

if rg -q -- '--info=progress2' "$build_script"; then
  echo "build script uses rsync --info=progress2, unsupported by macOS openrsync" >&2
  exit 1
fi

rg -q -- '--delete-delay --partial --no-whole-file --progress' "$build_script"
rg -q -- 'staging_dir="\$project_dir/data/work/web-public-data-next"' "$data_build_script"
rg -q -- 'scripts/verify_hsy_green_cover.py' "$data_build_script"
rg -q -- 'verify-release "\$staging_dir"' "$data_build_script"
rg -q -- 'service-destinations.geojson.gz' "$data_build_script"
rg -q -- '24.92991' "$data_build_script"
rg -q -- 'rsync -a --delete-delay --partial --no-whole-file "\$staging_dir/" "\$project_dir/web/public/data/"' "$data_build_script"

test -x "$release_script"
rg -q -- 'cd "\$project_dir"' "$release_script"
rg -q -- 'node "\$project_dir/scripts/download_hsy_green_cover.mjs"' "$release_script"
rg -q -- 'bash "\$project_dir/scripts/build_local_release_with_green_cover.sh"' "$release_script"
rg -q -- 'bash "\$project_dir/scripts/build_web_release.sh"' "$release_script"
rg -q -- 'for (let attempt = 0;; attempt += 1)' "$green_cover_download_script"
! rg -q -- 'attempt < 8' "$green_cover_download_script"
