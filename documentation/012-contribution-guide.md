# Contribution Guide

To add new atlas content:

1. Create a Markdown file under `content-source/objects/`, `media/`, `stories/`, or `pages/`.
2. Add multilingual titles and summaries where available.
3. Add geometry and time metadata where appropriate.
4. Run `./pipeline/atlas.sh validate`.
5. Rebuild indexes with the pipeline commands or run `./pipeline/atlas.sh release`.

Add new static layers under `data-source/geo/` and register them in `app/config/layers.json`.

