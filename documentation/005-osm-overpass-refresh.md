# OSM Overpass Refresh

Overpass is a local build-time concern only.

- Query templates are stored in `data-source/osm/queries/`.
- Browser runtime must never query Overpass directly.
- Raw and normalized refresh outputs live under `data-source/osm/raw/` and `data-source/osm/normalized/`.
- OSM-derived public layers should preserve attribution to OpenStreetMap contributors.
- Raw and normalized refresh outputs are local-only caches and should not be committed.

The default public runtime still stays self-contained, but the local refresh pipeline can now perform a live Overpass download when you explicitly run it.

## Run The Refresh

Use:

```bash
bash pipeline/atlas.sh refresh-osm
```

This will:

1. render the stored `.overpassql` templates with the configured bbox and buffer distance
2. POST them to the configured Overpass interpreter endpoint
3. save raw JSON under `data-source/osm/raw/`
4. convert raw OSM data to GeoJSON under `data-source/osm/normalized/`
5. regenerate derived project layer manifests and GeoJSON chunks under `data-source/geo/`
6. sync the generated runtime layer bundles into `app/data/geo/`

## Output Shape

Generated OSM-derived layers now follow a Git-safe bundle layout:

- small `.geojson` files for small layers
- `.manifest.json` files for large layers
- chunk files under `data-source/geo/_bundles/` and `app/data/geo/_bundles/`

The browser runtime reads the manifest, fetches the listed chunks, and merges them client-side.

## Buildings Near Riverbanks

The project now includes a dedicated nearby-building extraction path:

- settings live in `data-source/osm/settings.json`
- the configurable distance is `riverbankBuildingDistanceM`
- the Overpass template lives in `data-source/osm/queries/05-buildings-near-riverbanks.overpassql`
- the normalized output target is `data-source/osm/normalized/buildings-near-riverbanks.geojson`

The current query uses an `around` distance from the Berkel-related waterway centerline. In practice this captures buildings on both sides of the river within the configured buffer distance.

If you want a wider or narrower riverside context, change `riverbankBuildingDistanceM` and update the query distance accordingly before running a real refresh.
The current implementation now renders that distance automatically from `settings.json`, so changing the setting is sufficient.
