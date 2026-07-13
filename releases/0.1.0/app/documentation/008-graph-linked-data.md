# Graph And Linked Data

Graph data is stored as static JSON.

- `app/data/graph/nodes.json`
- `app/data/graph/edges.json`
- `app/data/linked-data/objects.jsonld`

Internal nodes use project IDs. External nodes use CURIE-like references such as `wikidata:Q123456` and `osm:way/123456789`.

Relation types such as `same_as`, `depicts`, `evidence`, and `located_near` are represented as edges.

