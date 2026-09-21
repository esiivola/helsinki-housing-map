#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
archive_path="${1:?Usage: bash scripts/package_public_data_release.sh <archive.tar.gz>}"

"$project_dir/.venv/bin/python" -m pipeline verify-release "$project_dir/web/public/data"
tar -C "$project_dir/web/public" -czf "$archive_path" data
shasum -a 256 "$archive_path"
