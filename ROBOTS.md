# ROBOTS.md

Purpose: make this project recoverable and resumable by another workstation, another person, or another AI agent with minimal lost context.

## First Files To Read

Read these first, in order:

1. [README.md](/Users/jlouwers/codexProjects/berkelriveratlas/README.md)
2. [CHAT_HISTORY.md](/Users/jlouwers/codexProjects/berkelriveratlas/CHAT_HISTORY.md)
3. [ai-vibe-coding/codex-master-prompt.md](/Users/jlouwers/codexProjects/berkelriveratlas/ai-vibe-coding/codex-master-prompt.md)
4. [documentation/001-architecture.md](/Users/jlouwers/codexProjects/berkelriveratlas/documentation/001-architecture.md)
5. [documentation/004-data-pipeline.md](/Users/jlouwers/codexProjects/berkelriveratlas/documentation/004-data-pipeline.md)

## Project Intent

The Berkel River Atlas is a public, static, client-side historical atlas of the Berkel river.

Core non-negotiables:

- no backend runtime
- no database runtime
- no SSR
- no secrets
- multilingual support for `en`, `de`, and `nl`
- Markdown as canonical content source
- generated static indexes for map, timeline, graph, and search

## Where The Real Sources Of Truth Live

- Canonical content source: [content-source](/Users/jlouwers/codexProjects/berkelriveratlas/content-source)
- Runtime static app: [app](/Users/jlouwers/codexProjects/berkelriveratlas/app)
- Future source app: [src](/Users/jlouwers/codexProjects/berkelriveratlas/src)
- Pipeline and validation: [pipeline](/Users/jlouwers/codexProjects/berkelriveratlas/pipeline)
- Human docs: [documentation](/Users/jlouwers/codexProjects/berkelriveratlas/documentation)
- AI guidance: [ai-vibe-coding](/Users/jlouwers/codexProjects/berkelriveratlas/ai-vibe-coding)
- Session continuity log: [CHAT_HISTORY.md](/Users/jlouwers/codexProjects/berkelriveratlas/CHAT_HISTORY.md)

## Recovery Procedure

If the original workstation or chat is lost:

1. Clone the repository.
2. Read `CHAT_HISTORY.md` for the decision trail and latest state.
3. Read `ROBOTS.md` and the top-level docs to understand architecture and constraints.
4. Inspect `git status` and the latest commits to identify unfinished work.
5. Run:

```bash
bash pipeline/atlas.sh validate
bash pipeline/atlas.sh refresh-osm   # optional, requires network access
bash pipeline/atlas.sh release
```

6. If Node is available, also run:

```bash
npm install
npm run build
```

7. Continue by appending a new dated entry to `CHAT_HISTORY.md` before or after each meaningful session.

## Current Known State

As of `2026-07-13`:

- Static deployable app exists in `app/`.
- Packaged release exists in `releases/0.1.0/app`.
- Validation and release pipeline pass in the current environment.
- Vite source code exists but was not build-verified on this workstation because Node was unavailable.
- The OSM pipeline is implemented for live Overpass refresh, but it depends on network access when `refresh-osm` is used.

## Update Rules

Whenever significant work is done:

- update `CHAT_HISTORY.md`
- update `ROBOTS.md` if recovery instructions or project state materially change
- update documentation if architecture, pipeline, or content conventions change

## What Not To Do

- Do not commit secrets.
- Do not replace the static architecture with a server-backed runtime.
- Do not assume external map providers are available by default.
- Do not delete the history or recovery files.
