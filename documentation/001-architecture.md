# Architecture

The Berkel River Atlas runs as a static-only web application.

- Runtime is client-side only.
- No SSR, backend API, database, or application server is required.
- Hash routing avoids server rewrite rules.
- Markdown, JSON, GeoJSON, SVG, and configuration files are fetched directly in the browser.
- Public source and generated data can live in GitHub and be deployed from a simple static web root.

The build pipeline validates source content in `content-source/`, generates indexes into `app/data/`, and packages a deployable release under `releases/<version>/app/`.

