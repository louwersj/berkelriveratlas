# Map Layer System

Layer definitions live in `app/config/layers.json`.

- Layers are grouped into base, river, historic, and external groups.
- Local GeoJSON layers are the default public runtime.
- Local OSM-derived building overlays can be added for near-river context, such as buildings within a configured distance of both river banks.
- External historic and commercial layers are placeholders by default.
- Attribution should be present whenever a layer depends on third-party data or services.
- The UI separates layer controls from site navigation.
