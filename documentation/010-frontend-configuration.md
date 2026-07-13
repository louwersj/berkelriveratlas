# Frontend Configuration

The runtime frontend is driven by JSON config files in `app/config/`.

- `site.json` defines title, tagline, languages, and repository URL.
- `navigation.json` defines menu entries.
- `layers.json` defines local and external layers.
- `languages.json` defines UI labels for language selection.
- `theme.json` defines color tokens.
- `feature-flags.json` enables optional interface areas.

Avoid hardcoding labels and navigational structure when configuration is available.

