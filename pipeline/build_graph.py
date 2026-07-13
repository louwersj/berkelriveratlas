from __future__ import annotations

from common import APP_DIR, is_external_reference, load_all_documents, now_iso, published_documents, write_json


def main() -> int:
    documents = published_documents(load_all_documents())
    nodes = []
    edges = []
    seen_external: set[str] = set()

    for document in documents:
        front_matter = document.front_matter
        node = {
            "id": front_matter["id"],
            "kind": "internal",
            "type": front_matter.get("type"),
            "category": front_matter.get("category", front_matter.get("media_type", front_matter.get("type"))),
            "label": front_matter.get("title", {}),
            "url": route_for_document(front_matter),
        }
        nodes.append(node)

        for relation in front_matter.get("relations", []):
            if not isinstance(relation, dict):
                continue
            target = relation.get("target")
            if not target:
                continue
            edges.append({"source": front_matter["id"], "target": target, "type": relation.get("type", "related_to")})
            if isinstance(target, str) and is_external_reference(target) and target not in seen_external:
                nodes.append(
                    {
                        "id": target,
                        "kind": "external",
                        "type": target.split(":", 1)[0],
                        "label": {"en": target},
                        "url": external_url(target),
                    }
                )
                seen_external.add(target)

        for target in front_matter.get("same_as", []):
            if not isinstance(target, str):
                continue
            edges.append({"source": front_matter["id"], "target": target, "type": "same_as"})
            if target not in seen_external:
                nodes.append(
                    {
                        "id": target,
                        "kind": "external",
                        "type": target.split(":", 1)[0],
                        "label": {"en": target},
                        "url": external_url(target),
                    }
                )
                seen_external.add(target)

    write_json(APP_DIR / "data/graph/nodes.json", nodes)
    write_json(APP_DIR / "data/graph/edges.json", edges)
    write_json(
        APP_DIR / "data/linked-data/objects.jsonld",
        {
            "@context": {
                "schema": "https://schema.org/",
                "sameAs": {"@id": "schema:sameAs", "@type": "@id"},
            },
            "generated_at": now_iso(),
            "@graph": [
                {
                    "@id": node["id"],
                    "@type": "schema:Thing",
                    "schema:name": next(iter(node["label"].values()), node["id"]),
                }
                for node in nodes
                if node["kind"] == "internal"
            ],
        },
    )
    print(f"Built graph with {len(nodes)} nodes and {len(edges)} edges.")
    return 0


def external_url(identifier: str) -> str:
    prefix, suffix = identifier.split(":", 1)
    if prefix in {"wikidata", "wd"}:
        return f"https://www.wikidata.org/wiki/{suffix}"
    if prefix == "geonames":
        return f"https://www.geonames.org/{suffix}"
    if prefix == "osm":
        return f"https://www.openstreetmap.org/{suffix}"
    return f"https://example.org/{identifier}"


def route_for_document(front_matter: dict) -> str:
    if front_matter.get("type") == "page":
        page_id = str(front_matter["id"]).removeprefix("page-")
        return f"#/en/page/{page_id}"
    return f"#/en/object/{front_matter['id']}"


if __name__ == "__main__":
    raise SystemExit(main())
