# Deployment

Deployment is simple static hosting.

1. Run `./pipeline/atlas.sh release`.
2. Copy `releases/<version>/app/` to any static web server root.
3. Serve standard MIME types for HTML, CSS, JS, JSON, GeoJSON, SVG, and images.

No server-side rewrites are required because the atlas uses hash routing.

