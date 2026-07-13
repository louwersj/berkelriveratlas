from __future__ import annotations

from common import APP_DIR, load_all_documents, published_documents, write_json


def main() -> int:
    documents = published_documents(load_all_documents())
    languages = ["en", "de", "nl"]
    for language in languages:
        records = []
        for document in documents:
            title_map = document.front_matter.get("title", {})
            summary_map = document.front_matter.get("summary", {})
            records.append(
                {
                    "id": document.front_matter["id"],
                    "title": title_map.get(language) or title_map.get("en") or next(iter(title_map.values()), ""),
                    "summary": summary_map.get(language) or summary_map.get("en") or next(iter(summary_map.values()), ""),
                    "content_path": f"content/{document.relative_path}",
                }
            )
        write_json(APP_DIR / f"data/search/search.{language}.json", records)
    print(f"Built search indexes for {len(languages)} languages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

