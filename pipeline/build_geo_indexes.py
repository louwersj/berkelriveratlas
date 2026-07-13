from __future__ import annotations

import shutil
from pathlib import Path

from common import APP_DIR, CONTENT_SOURCE_DIR, DATA_SOURCE_DIR, copy_tree, ensure_directory, load_all_documents, now_iso, published_documents, write_json


def main() -> int:
    documents = published_documents(load_all_documents())
    copy_runtime_content()
    copy_geo_layers()
    features = []

    for document in documents:
        spatial = document.front_matter.get("spatial")
        if not isinstance(spatial, dict):
            continue
        geometry = spatial.get("geometry")
        if not geometry:
            continue

        front_matter = document.front_matter
        title = front_matter.get("title", {})
        summary = front_matter.get("summary", {})
        feature = {
            "type": "Feature",
            "id": front_matter["id"],
            "geometry": geometry,
            "properties": {
                "id": front_matter["id"],
                "type": front_matter.get("type"),
                "category": front_matter.get("category", front_matter.get("media_type", front_matter.get("type"))),
                "content_path": f"content/{document.relative_path}",
                "title": title,
                "summary": summary,
                "time": front_matter.get("time")
                or {
                    "from": front_matter.get("coverage", {}).get("from") or front_matter.get("date", {}).get("value"),
                    "to": front_matter.get("coverage", {}).get("to") or front_matter.get("date", {}).get("value"),
                    "certainty": front_matter.get("date", {}).get("certainty"),
                },
                "river_relation": front_matter.get("river_relation"),
                "tags": front_matter.get("tags", []),
                "media_preview": preview_path(front_matter),
                "source_count": len(front_matter.get("sources", [])),
                "language_available": sorted(document.body_by_language.keys()),
                "graph_node_id": front_matter["id"],
                "geometry_certainty": spatial.get("certainty"),
            },
        }
        features.append(feature)

    payload = {
        "type": "FeatureCollection",
        "generated_at": now_iso(),
        "features": features,
    }
    write_json(APP_DIR / "data/index/map.objects.geojson", payload)
    print(f"Built map index with {len(features)} features.")
    return 0


def copy_runtime_content() -> None:
    copy_tree(CONTENT_SOURCE_DIR, APP_DIR / "content")


def copy_geo_layers() -> None:
    copy_tree(DATA_SOURCE_DIR / "geo", APP_DIR / "data/geo")


def preview_path(front_matter: dict) -> str | None:
    files = front_matter.get("files", {})
    if isinstance(files, dict):
        return files.get("thumbnail") or files.get("image")
    media = front_matter.get("media", [])
    if media:
        return "media/images/image-borculo-mill-001-thumb.svg"
    return None


if __name__ == "__main__":
    raise SystemExit(main())

