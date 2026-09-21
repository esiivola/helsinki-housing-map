#!/bin/sh
set -eu

task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT

.venv/bin/python -m pytest
.venv/bin/python -m pipeline fixture-release tests/fixtures/release_fixture.json "$task_tmp/public/data"
.venv/bin/python -m pipeline verify-release web/public/data
(cd web && npm test && npm run build)
if [ -n "${PERFORMANCE_REPORT:-}" ]; then
  (cd web && VITE_PUBLIC_DIR="$task_tmp/public" VITE_BASE_PATH=/helsinki-housing-map/ ./node_modules/.bin/vite build --outDir "$task_tmp/site/helsinki-housing-map" && E2E_BASE_PATH=/helsinki-housing-map/ npm run test:e2e -- --root "$task_tmp/site" --performance-report "$PERFORMANCE_REPORT" --reference-machine "${REFERENCE_MACHINE:?REFERENCE_MACHINE is required with PERFORMANCE_REPORT}")
else
  (cd web && VITE_PUBLIC_DIR="$task_tmp/public" VITE_BASE_PATH=/helsinki-housing-map/ ./node_modules/.bin/vite build --outDir "$task_tmp/site/helsinki-housing-map" && E2E_BASE_PATH=/helsinki-housing-map/ npm run test:e2e -- --root "$task_tmp/site")
fi
