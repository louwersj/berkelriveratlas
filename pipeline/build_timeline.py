from __future__ import annotations

from common import APP_DIR, load_all_documents, now_iso, parse_year, published_documents, write_json


def main() -> int:
    documents = published_documents(load_all_documents())
    items = []
    min_year: int | None = None
    max_year: int | None = None

    for document in documents:
        front_matter = document.front_matter
        time_data = front_matter.get("time") or front_matter.get("coverage") or {}
        if "date" in front_matter:
            time_data = {
                "from": front_matter.get("date", {}).get("value"),
                "to": front_matter.get("date", {}).get("value"),
                "certainty": front_matter.get("date", {}).get("certainty"),
            }
        from_value = time_data.get("from")
        to_value = time_data.get("to", from_value)
        item = {
            "id": front_matter["id"],
            "content_path": f"content/{document.relative_path}",
            "type": front_matter.get("type"),
            "category": front_matter.get("category", front_matter.get("media_type", front_matter.get("type"))),
            "from": from_value,
            "to": to_value,
            "certainty": time_data.get("certainty", front_matter.get("time", {}).get("certainty")),
            "title": front_matter.get("title", {}),
            "geometry_id": front_matter["id"],
        }
        items.append(item)

        year_from = parse_year(from_value)
        year_to = parse_year(to_value)
        if year_from is not None:
            min_year = year_from if min_year is None else min(min_year, year_from)
        if year_to is not None:
            max_year = year_to if max_year is None else max(max_year, year_to)

    payload = {
        "generated_at": now_iso(),
        "range": {
            "from": str(min_year or 1200),
            "to": str(max_year) if max_year is not None else "present",
        },
        "items": items,
    }
    write_json(APP_DIR / "data/index/timeline.index.json", payload)
    print(f"Built timeline index with {len(items)} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

