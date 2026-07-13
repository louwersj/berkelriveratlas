# Data Pipeline

Use `./pipeline/atlas.sh` as the main entry point.

- `validate` checks content, layers, media references, and secret patterns.
- `refresh-osm` runs the stored Overpass queries, saves raw OSM JSON, converts it to GeoJSON, and updates derived map layers.
- `build-layers` regenerates OSM-derived GeoJSON layer bundles from previously downloaded normalized data and syncs them into `app/data/geo`.
- Large generated map layers also emit spatial tile sets for bbox-driven loading in the runtime.
- `build-indexes` copies runtime Markdown content and builds `map.objects.geojson`.
- `build-timeline` creates `timeline.index.json`.
- `build-graph` creates graph JSON plus JSON-LD.
- `build-search` creates language-specific search indexes.
- `release` runs the full sequence, builds frontend assets, and packages a release copy.

`release` intentionally does not force a live OSM refresh, so packaging remains possible when network access is unavailable.

## Size Guardrails

- Raw and normalized OSM refresh outputs are local caches and should remain untracked.
- OSM-derived runtime layers are written as manifest-driven chunk bundles under `data-source/geo/` and `app/data/geo/`.
- Heavy spatial runtime layers are also written as tile manifests plus small tile files under `_tiles/`.
- `pipeline/validate_layers.py` fails when a tracked generated geo asset exceeds the configured size budget.
- Release folders under `releases/` are disposable local artifacts, not source-of-truth files to commit.
