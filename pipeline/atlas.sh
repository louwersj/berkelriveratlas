#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMMAND="${1:-}"

run_python() {
  python3 "$@"
}

case "${COMMAND}" in
  validate)
    run_python pipeline/validate.py
    run_python pipeline/validate_layers.py
    run_python pipeline/process_media.py
    run_python pipeline/scan_for_secrets.py
    ;;
  refresh-osm)
    run_python pipeline/refresh_osm.py
    run_python pipeline/convert_osm.py
    run_python pipeline/normalize_osm.py
    ;;
  build-indexes)
    run_python pipeline/build_geo_indexes.py
    run_python pipeline/build_manifest.py
    ;;
  build-layers)
    run_python pipeline/convert_osm.py
    run_python pipeline/normalize_osm.py
    run_python pipeline/validate_layers.py
    ;;
  build-timeline)
    run_python pipeline/build_timeline.py
    ;;
  build-graph)
    run_python pipeline/build_graph.py
    ;;
  build-search)
    run_python pipeline/build_search.py
    ;;
  package-release)
    bash pipeline/package_release.sh
    ;;
  release)
    bash pipeline/atlas.sh validate
    bash pipeline/atlas.sh build-layers
    bash pipeline/atlas.sh build-indexes
    bash pipeline/atlas.sh build-timeline
    bash pipeline/atlas.sh build-graph
    bash pipeline/atlas.sh build-search
    run_python pipeline/build_manifest.py
    if command -v npm >/dev/null 2>&1; then
      npm run build
    else
      echo "npm not found; using checked-in static app assets."
    fi
    bash pipeline/package_release.sh
    ;;
  *)
    cat <<'USAGE'
Usage:
  ./pipeline/atlas.sh validate
  ./pipeline/atlas.sh refresh-osm
  ./pipeline/atlas.sh build-indexes
  ./pipeline/atlas.sh build-layers
  ./pipeline/atlas.sh build-timeline
  ./pipeline/atlas.sh build-graph
  ./pipeline/atlas.sh build-search
  ./pipeline/atlas.sh package-release
  ./pipeline/atlas.sh release
USAGE
    exit 1
    ;;
esac
