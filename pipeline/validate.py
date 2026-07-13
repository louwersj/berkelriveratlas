from __future__ import annotations

import json
import sys
from pathlib import Path

from common import ALLOWED_EXTERNAL_PREFIXES, APP_DIR, ROOT, is_external_reference, load_all_documents, published_documents, validate_geometry


def main() -> int:
    documents = load_all_documents()
    published = published_documents(documents)
    errors: list[str] = []
    ids: dict[str, Path] = {}

    all_ids = {document.front_matter.get("id") for document in published}
    for document in published:
        front_matter = document.front_matter
        object_id = front_matter.get("id")
        if not object_id:
            errors.append(f"{document.relative_path}: missing id")
            continue
        if object_id in ids:
            errors.append(f"{document.relative_path}: duplicate id also in {ids[object_id]}")
        ids[object_id] = document.path

        required_fields = ["id", "type", "status", "title"]
        if front_matter.get("type") != "page":
            required_fields.append("summary")
        for field in required_fields:
            if field not in front_matter:
                errors.append(f"{document.relative_path}: missing required field {field}")

        if "spatial" in front_matter:
            geometry = front_matter.get("spatial", {}).get("geometry")
            if not validate_geometry(geometry):
                errors.append(f"{document.relative_path}: invalid spatial.geometry")

        if front_matter.get("type") == "media" and "rights" not in front_matter:
            errors.append(f"{document.relative_path}: media object missing rights metadata")

        relations = front_matter.get("relations", [])
        if isinstance(relations, list):
            for relation in relations:
                target = relation.get("target") if isinstance(relation, dict) else None
                if not target:
                    errors.append(f"{document.relative_path}: relation missing target")
                    continue
                if target not in all_ids and not is_external_reference(target):
                    errors.append(f"{document.relative_path}: relation target {target} does not exist")

        same_as = front_matter.get("same_as", [])
        if isinstance(same_as, list):
            for target in same_as:
                if isinstance(target, str) and not is_external_reference(target):
                    errors.append(f"{document.relative_path}: same_as target {target} is not a valid external reference")

        if "title" in front_matter and not isinstance(front_matter["title"], dict):
            errors.append(f"{document.relative_path}: title must be a language map")
        if "summary" in front_matter and not isinstance(front_matter["summary"], dict):
            errors.append(f"{document.relative_path}: summary must be a language map")

    navigation_path = APP_DIR / "config" / "navigation.json"
    navigation = json.loads(navigation_path.read_text(encoding="utf-8"))
    for item in navigation.get("main", []):
        content_path = item.get("contentPath")
        if content_path:
            if not (APP_DIR / content_path).exists():
                errors.append(f"navigation item {item.get('id')}: missing page at {content_path}")

    for config_path in [APP_DIR / "config" / "layers.json", APP_DIR / "config" / "site.json"]:
        if not config_path.exists():
            errors.append(f"missing required config file {config_path}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(published)} published Markdown documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
