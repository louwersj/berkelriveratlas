# Chat History

This file is the local durable summary of important project conversations and decisions.

## Usage Rules

- Append a new dated entry after every meaningful work session.
- Record the user request, what changed, important constraints, verification performed, and open follow-up items.
- Keep summaries concise but sufficient to reconstruct intent and implementation direction.
- Do not store secrets, private credentials, or sensitive personal data here.

## 2026-07-13

### Session Summary

Initial greenfield implementation of **The Berkel River Atlas** based on the master build brief.

### User Request

Build a complete static, client-side, multilingual, map-first historical atlas of the Berkel river with Markdown-driven content, generated indexes, local pipeline scripts, documentation, and public-safe defaults.

### Work Completed

- Scaffolded the repository structure for app, sources, pipeline, docs, releases, and AI guidance.
- Built a static deployable atlas app in `app/` with:
  - multilingual hash routing
  - map-first explore view
  - timeline filtering
  - object detail rendering from Markdown
  - static page rendering
  - graph and sources views
  - layer drawer and hamburger menu
- Added a Vite + TypeScript source implementation in `src/` for future Node-enabled environments.
- Added sample content in `content-source/` and mirrored runtime content in `app/content/`.
- Added sample GeoJSON, graph, timeline, linked-data, manifest, and search indexes in `app/data/`.
- Added local pipeline scripts for validation, OSM placeholder refresh, index builds, graph builds, search builds, secret scanning, and release packaging.
- Added required project documentation in `documentation/`.
- Added required AI guidance files in `ai-vibe-coding/`.
- Produced a packaged static release at `releases/0.1.0/app`.

### Constraints And Decisions

- Runtime must remain static and client-side only.
- No backend, database, SSR, or runtime API dependency.
- No secrets committed to the repository.
- External Google and Topotijdreis-style layers are placeholders only by default.
- Because this workstation did not have `node` or `npm`, a checked-in static browser implementation was added under `app/assets/` so packaging and deployment still work.

### Verification

- `bash pipeline/atlas.sh validate` passed.
- `bash pipeline/atlas.sh release` passed.
- Release packaging includes `documentation/` inside `releases/0.1.0/app`.

### Environment Limits Encountered

- `npm`, `node`, `pnpm`, and `yarn` were not installed on this workstation, so `npm install` and `npm run build` could not be verified here.
- A local HTTP server bind test was blocked by sandbox permissions.

### Next Recommended Steps

- Install Node.js and run the Vite build path (`npm install`, `npm run build`) on a machine with Node available.
- Optionally automate app-side history logging if you want this file updated by a script rather than manually.
- Continue appending new entries to this file after each significant session.

## 2026-07-13 Follow-up

### Session Summary

Added a dedicated OSM/Overpass path for including buildings within a configurable distance of the river banks.

### User Request

Ensure that map data extracted from Overpass Turbo also includes buildings within a set distance on both sides of the river bank.

### Work Completed

- Added `data-source/osm/settings.json` with `riverbankBuildingDistanceM`.
- Added `data-source/osm/queries/05-buildings-near-riverbanks.overpassql`.
- Added sample `buildings-near-riverbanks.geojson` in both source and runtime geo folders.
- Added a `buildings-near-riverbanks` layer entry to `app/config/layers.json`.
- Updated the OSM refresh placeholder script and documentation to describe the new behavior.

### Notes

- The current query uses a centerline `around` buffer as a practical proxy for both banks.
- If you want the exact distance changed later, update `riverbankBuildingDistanceM` and the query distance together.

## 2026-07-13 OSM Pipeline Upgrade

### Session Summary

Replaced the placeholder OSM refresh path with a real Overpass-backed data pipeline.

### User Request

Implement the missing live OpenStreetMap/Overpass refresh behavior and make the project more fully working.

### Work Completed

- Implemented live Overpass POST requests in `pipeline/refresh_osm.py`.
- Added query templating for bbox, timeout, and riverbank building distance.
- Implemented raw OSM JSON to GeoJSON conversion in `pipeline/convert_osm.py`.
- Implemented normalized layer generation in `pipeline/normalize_osm.py`.
- Made `bash pipeline/atlas.sh refresh-osm` fetch, convert, and populate GeoJSON layers end to end.
- Removed forced live refresh from the `release` command so offline packaging still works.
- Updated project documentation and recovery instructions.

### Notes

- `refresh-osm` now needs network access to Overpass.
- `release` remains offline-friendly by reusing existing local data instead of forcing a fresh download.
- Live verification showed successful real fetches for `01-waterways`, `02-roads-paths`, and `03-bridges-waterworks`.
- The heavier Overpass queries can still be slow or rate-limited by the remote service, so retry, backoff, tiling, and query filtering were added.
- Overpass endpoint failover was added so the refresh can try multiple public interpreter URLs instead of only one host.
- `build-layers` now completes successfully on the real downloaded raw OSM files.
- A direct Python `TimeoutError` from slow HTTPS reads is now converted into a retryable `OverpassFetchError` so stalled Overpass responses do not bypass the retry/failover logic.
- OSM refresh now emits explicit per-query `FETCHED`, `FAILED`, or `SKIPPED` terminal messages and writes `data-source/osm/raw/refresh-status.json` so query failures cannot be silent.

## 2026-07-13 Geo Layer Size Hardening

### Session Summary

Redesigned OSM-derived map packaging so tracked files stay small and oversized GeoJSON blobs cannot reappear silently.

### User Request

Identify which files are too large, switch to a smaller-file architecture, and make sure Git tracking remains reliable without recurring oversized-file problems.

### Work Completed

- Identified the worst tracked offenders as `base-roads` at about `94 MB` and `base-paths` at about `77 MB`, mirrored in both `data-source/geo/` and `app/data/geo/`.
- Reworked `pipeline/normalize_osm.py` to emit manifest-driven chunk bundles for large OSM-derived layers, with a strict `5 MB` per-file target.
- Updated both runtimes to support `manifestUrl` and client-side merging of GeoJSON chunks.
- Switched the default `base-linework` layer to manifest-based loading.
- Added validation rules that fail when tracked generated geo assets exceed the size budget.
- Marked Overpass raw status files and packaged release folders as local-only, non-tracked artifacts.

### Notes

- The new architecture keeps Git as the system of record for small public layer artifacts, while treating raw refresh data and packaged releases as disposable local build outputs.
- Future OSM-derived layers should use manifests automatically when they would otherwise exceed the per-file size budget.

## 2026-07-13 Refresh Progress And Interrupt Handling

### Session Summary

Improved OSM refresh visibility after a heavy buildings-near-riverbanks query looked stuck after the heritage query completed.

### User Request

Investigate why refresh appeared stuck at `04-places-heritage` and address the keyboard-interrupt traceback behavior.

### Work Completed

- Confirmed the refresh was actually moving on to `05-buildings-near-riverbanks`, which is substantially heavier than `04-places-heritage`.
- Added `STARTING` output before each query begins.
- Added per-tile progress logging during tiled fetches, including subdivision retries and tile-level failures.
- Added stable nested tile path labels so every individual sub-tile fetch is visible in the terminal output.
- Added explicit interrupt handling so `refresh-status.json` records an `interrupted` run instead of only showing a traceback.
- Added a deeper tile subdivision override for `05-buildings-near-riverbanks` to improve its chance of finishing.
- Added configurable per-query tile grids so heavy queries can start with much smaller tiles, with `05-buildings-near-riverbanks` now starting at `4x4`.
- Added explicit retry logging so tiled fetches now show two retry rounds before the script changes strategy and subdivides further.

## 2026-07-13 Spatial Tile Runtime

### Session Summary

Extended the chunked layer architecture into true spatial tiles so large map layers can be stored and rendered as small bbox-driven files.

### User Request

Move beyond whole-layer GeoJSON storage and implement a structure that stores and renders much smaller spatial tiles.

### Work Completed

- Reworked `pipeline/normalize_osm.py` to emit spatial tile manifests and tile files for large generated OSM layers.
- Added tracked tile outputs under `data-source/geo/_tiles/` and `app/data/geo/_tiles/`.
- Switched the default `base-linework` layer to `tileManifestUrl`.
- Updated the checked-in static runtime to fetch only tiles intersecting the current viewport bounds and dedupe features across tile edges.
- Updated the TypeScript/Leaflet runtime to load and refresh visible spatial tiles on map movement.
- Extended layer validation so tile manifests and tile files are checked alongside bundle manifests.

### Notes

- The current large-layer tile grid is `16x16`, which keeps tracked tile files under the repo size cap while remaining small enough for bbox-based access.
- Tile manifests are now explicit for all `256` cells in the `16x16` grid, including empty tiles, so the layout is fully predictable for downstream tooling and runtime logic.

## 2026-07-13 Fetch And Storage Tile Alignment

### Session Summary

Aligned the Overpass fetch workflow with the same explicit `16x16` grid model used by generated spatial storage.

### User Request

Make sure the fixed `16x16` tile structure is included in both fetching and the backend-style pipeline workflow.

### Work Completed

- Updated `data-source/osm/settings.json` so heavy tiled fetch queries now start on an explicit `16x16` first-pass grid.
- Extended fetch metadata so refresh outputs record the tile grid sequence used for each tiled query.
- Applied the aligned fetch grid model to the heavy tiled Overpass queries.
- Updated project docs so the fetch path and generated storage path are described as one coordinated spatial tiling model.
- Kept two explicit retry rounds before any timeout-driven fetch strategy change, and surfaced those retries directly in the terminal output.

## 2026-07-14 Resumable OSM Refresh

### Session Summary

Added a resumable OSM refresh mode so a failed run can continue from a specific query without redoing earlier successful downloads.

### User Request

Make the failed OSM refresh restartable from the beginning of `05-buildings-near-riverbanks` through a flag, while preserving the earlier successful query outputs and flowing them into the normal tile-building backend workflow.

### Work Completed

- Added `--resume-from` support to `pipeline/refresh_osm.py`.
- Passed extra arguments through `./pipeline/atlas.sh refresh-osm`.
- Added resume logic that validates earlier raw outputs exist, marks them as preserved, and restarts at the requested query.
- Kept the normal `convert_osm.py` and `normalize_osm.py` steps after a resumed fetch so previously fetched raw files and newly fetched raw files are processed together into the generated tile outputs.
