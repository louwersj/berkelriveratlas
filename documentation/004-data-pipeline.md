# Data Pipeline

Use `./pipeline/atlas.sh` as the main entry point.

- `validate` checks content, layers, media references, and secret patterns.
- `refresh-osm` runs the stored Overpass queries, saves raw OSM JSON, converts it to GeoJSON, and updates derived map layers.
- `build-layers` regenerates OSM-derived GeoJSON layers from previously downloaded normalized data and syncs them into `app/data/geo`.
- `build-indexes` copies runtime Markdown content and builds `map.objects.geojson`.
- `build-timeline` creates `timeline.index.json`.
- `build-graph` creates graph JSON plus JSON-LD.
- `build-search` creates language-specific search indexes.
- `release` runs the full sequence, builds frontend assets, and packages a release copy.

`release` intentionally does not force a live OSM refresh, so packaging remains possible when network access is unavailable.
