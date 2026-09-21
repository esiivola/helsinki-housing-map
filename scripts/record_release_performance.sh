#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: sh scripts/record_release_performance.sh 'reference machine'" >&2
  exit 2
fi

mkdir -p data/work
report_path="$(pwd)/data/work/reference-performance.json"
PERFORMANCE_REPORT="$report_path" REFERENCE_MACHINE="$1" sh scripts/verify_e2e.sh
.venv/bin/python scripts/record_performance.py web/public/data/audit.json "$report_path"
(cd web && npm run build)
