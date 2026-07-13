# API Key And Secrets Policy

This repository is public by design.

- Never commit `.env` files.
- Never commit Google or other provider credentials.
- Never commit private archive credentials.
- Never place API keys in `layers.json`.
- Never package secrets into `releases/`.

`app/config/local.private.json` is intentionally gitignored for local-only runtime configuration.

