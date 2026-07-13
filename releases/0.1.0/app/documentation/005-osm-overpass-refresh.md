# OSM Overpass Refresh

Overpass is a local build-time concern only.

- Query templates are stored in `data-source/osm/queries/`.
- Browser runtime must never query Overpass directly.
- Raw and normalized refresh outputs live under `data-source/osm/raw/` and `data-source/osm/normalized/`.
- OSM-derived public layers should preserve attribution to OpenStreetMap contributors.

The current implementation ships offline placeholders so the public default build remains self-contained.

