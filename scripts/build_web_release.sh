#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
web_dir="$project_dir/web"

cd "$web_dir"

# Report which basemap the bundle will ship. CARTO Positron requires a build-time
# VITE_CARTO_KEY (a public, domain-restricted CARTO key); provide it via the
# environment or an untracked web/.env.production.local, both of which Vite inlines.
# Without it the build falls back to the bundled offline OSM basemap.
if [[ -n "${VITE_CARTO_KEY:-}" ]]; then
  echo "Basemap: CARTO Positron (VITE_CARTO_KEY set in environment)."
elif [[ -f .env.production.local ]] && grep -q '^VITE_CARTO_KEY=.' .env.production.local; then
  echo "Basemap: CARTO Positron (VITE_CARTO_KEY from web/.env.production.local)."
else
  echo "Basemap: bundled offline OSM fallback (set VITE_CARTO_KEY to ship CARTO Positron)."
fi

./node_modules/.bin/tsc --noEmit
VITE_SKIP_PUBLIC=1 ./node_modules/.bin/vite build --emptyOutDir false

mkdir -p dist/data
rsync -a --delete-delay --partial --no-whole-file --progress public/data/ dist/data/
node scripts/verify-static-assets.mjs
