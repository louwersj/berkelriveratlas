# Markdown Object Format

Each object begins with front matter wrapped in `---` markers, followed by language sections.

- Required fields: `id`, `type`, `status`, `title`, `summary`
- Mappable records should include `spatial.geometry`
- Time-aware records should include `time`, `coverage`, or `date`
- Relations are stored in `relations`
- External identifiers can be stored in `same_as`

This implementation uses JSON-formatted front matter, which is also valid YAML subset content and is easy to validate with standard library tooling.

