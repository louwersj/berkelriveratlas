# The Berkel River Atlas

Static files, living river, layered time.

The Berkel River Atlas is a multilingual, map-first, timeline-first, graph-aware historical atlas of the Berkel river. The runtime application is fully static and client-side: no backend, no database, no server-side rendering, and no runtime API dependency.

## Quick start

```bash
npm install
npm run build
npm run dev
```

In a second terminal:

```bash
./pipeline/atlas.sh validate
./pipeline/atlas.sh refresh-osm   # optional live OSM refresh
./pipeline/atlas.sh release
```

The built static application lives in `app/`. A packaged deployable copy is created under `releases/<version>/app/`.

## Data Size Strategy

- Live Overpass refresh outputs under `data-source/osm/raw/` and `data-source/osm/normalized/` are local build caches and are not tracked in Git.
- OSM-derived public map layers are generated as small GeoJSON chunks and spatial tiles plus manifest files instead of giant monolithic files.
- Heavy Overpass refresh queries use the same explicit `16x16` first-pass tiling model, so fetching and generated storage follow one spatial grid strategy.
- `pipeline/validate_layers.py` enforces a strict tracked-asset size budget so oversized generated files fail validation before commit or release work.
- Release packages under `releases/` are local build artifacts and are not tracked in Git.

## Project shape

- `src/` contains the frontend source built with Vite and TypeScript.
- `content-source/` contains canonical Markdown content objects and pages.
- `data-source/` contains source GeoJSON, OSM query templates, and vocab inputs.
- `data-source/geo/` contains small tracked map source files plus generated OSM layer manifests and chunks.
- `app/` contains the deployable static runtime files, config, generated indexes, and copied content.
- `pipeline/` contains local validation, index generation, release packaging, and secret scanning.
- `documentation/` contains project documentation.
- `ai-vibe-coding/` contains AI-oriented implementation guidance.
- `CHAT_HISTORY.md` is the local running project conversation log.
- `ROBOTS.md` is the local reconstruction and continuation guide for AI agents and humans.

## Public safety

This repository is public by design.

- Never commit `.env` files, credentials, or API keys.
- Google and other external provider layers are placeholders by default.
- The default build works entirely from local static files.
- Oversized generated GeoJSON files are intentionally blocked by validation.

## Recovery

If this workstation is lost, start with:

- [CHAT_HISTORY.md](/Users/jlouwers/codexProjects/berkelriveratlas/CHAT_HISTORY.md)
- [ROBOTS.md](/Users/jlouwers/codexProjects/berkelriveratlas/ROBOTS.md)
- [ai-vibe-coding](/Users/jlouwers/codexProjects/berkelriveratlas/ai-vibe-coding)
- [documentation](/Users/jlouwers/codexProjects/berkelriveratlas/documentation)

## License

See [LICENSE](/Users/jlouwers/codexProjects/berkelriveratlas/LICENSE).
