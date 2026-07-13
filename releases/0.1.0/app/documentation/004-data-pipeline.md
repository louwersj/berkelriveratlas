# Data Pipeline

Use `./pipeline/atlas.sh` as the main entry point.

- `validate` checks content, layers, media references, and secret patterns.
- `refresh-osm` writes offline placeholder OSM refresh artifacts.
- `build-layers` copies local GeoJSON layers into `app/data/geo`.
- `build-indexes` copies runtime Markdown content and builds `map.objects.geojson`.
- `build-timeline` creates `timeline.index.json`.
- `build-graph` creates graph JSON plus JSON-LD.
- `build-search` creates language-specific search indexes.
- `release` runs the full sequence, builds frontend assets, and packages a release copy.

