# External Map Layers

The atlas supports placeholders for external layer families without requiring them in the default build.

- `wmts_tile`, `wms_tile`, and `xyz_tile` can represent public historical services.
- `external_historic_tile` is suitable for Topotijdreis-like configurations.
- `google_map_tiles` and `google_earth_3d_optional` are intentionally disabled by default.

Important rules:

- Do not commit API keys.
- Use browser-restricted local-only keys if these providers are enabled later.
- Verify provider terms, licensing, attribution, and CORS behavior before production activation.

