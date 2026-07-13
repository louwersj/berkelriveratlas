# Timeline Model

The atlas timeline is a first-class control.

- Timeline items are generated into `app/data/index/timeline.index.json`.
- `from` and `to` ranges define visibility across time.
- `certainty` can communicate exact, approximate, inferred, or unknown dates.
- Media can use `date` and `coverage`; long-lived objects can use `time`.

The sample frontend filters visible markers by a selected year.

