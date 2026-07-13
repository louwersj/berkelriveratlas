# Layer Configuration Reference

Common fields in `layers.json`:

- `id`: unique layer identifier
- `group`: UI grouping
- `type`: runtime layer type
- `role`: base or overlay
- `enabledByDefault`: initial state
- `label`: multilingual label map
- `url`: local or external layer source
- `manifestUrl`: manifest-driven local GeoJSON bundle source for large layers
- `tileManifestUrl`: bbox-driven spatial tile manifest for large map layers
- `style`: simple line and fill styling for GeoJSON
- `opacity`: default opacity
- `time`: optional time coverage
- `provider`: external provider name
- `requiresNetwork`: marks runtime network dependency
- `requiresApiKey`: marks local-only provider setup need
- `attribution`: attribution text
- `documentation`: documentation anchor for setup notes

Example project-specific overlay:

- `buildings-near-riverbanks`: OSM-derived building polygons within the configured riverbank buffer distance
