from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
CONTENT_SOURCE_DIR = ROOT / "content-source"
DATA_SOURCE_DIR = ROOT / "data-source"
MEDIA_SOURCE_DIR = ROOT / "media-source"

FRONT_MATTER_RE = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.MULTILINE)
LANG_SECTION_RE = re.compile(r"^##\s+(en|de|nl)\s*$", re.MULTILINE)
ALLOWED_EXTERNAL_PREFIXES = ("wikidata:", "wd:", "geonames:", "osm:", "external:", "schema:", "dcterms:", "skos:")


@dataclass
class MarkdownDocument:
    path: Path
    relative_path: str
    front_matter: dict[str, Any]
    body: str
    body_by_language: dict[str, str]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    ensure_directory(path.parent)
    if indent is None:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    else:
        serialized = json.dumps(payload, indent=indent, ensure_ascii=False)
    path.write_text(serialized + "\n", encoding="utf-8")


def copy_tree(source: Path, target: Path) -> None:
    ensure_directory(target)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def load_markdown_document(path: Path) -> MarkdownDocument:
    raw = read_text(path)
    match = FRONT_MATTER_RE.match(raw)
    if not match:
        raise ValueError(f"{path} is missing front matter.")
    front_matter = json.loads(match.group(1))
    body = match.group(2).strip()
    return MarkdownDocument(
        path=path,
        relative_path=str(path.relative_to(CONTENT_SOURCE_DIR)).replace("\\", "/"),
        front_matter=front_matter,
        body=body,
        body_by_language=split_body_by_language(body),
    )


def split_body_by_language(body: str) -> dict[str, str]:
    matches = list(LANG_SECTION_RE.finditer(body))
    if not matches:
        return {"en": body.strip()}
    output: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        output[match.group(1)] = body[start:end].strip()
    return output


def load_all_documents() -> list[MarkdownDocument]:
    documents: list[MarkdownDocument] = []
    for path in sorted(CONTENT_SOURCE_DIR.rglob("*.md")):
        documents.append(load_markdown_document(path))
    return documents


def published_documents(documents: list[MarkdownDocument]) -> list[MarkdownDocument]:
    return [document for document in documents if document.front_matter.get("status") == "published"]


def local_app_content_path(document: MarkdownDocument) -> str:
    return f"content/{document.relative_path}"


def parse_year(value: Any) -> int | None:
    if value in (None, "", "unknown"):
        return None
    if value == "present":
        return datetime.now().year
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def is_external_reference(value: str) -> bool:
    return value.startswith(ALLOWED_EXTERNAL_PREFIXES)


def validate_geometry(geometry: Any) -> bool:
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    return isinstance(geometry_type, str) and coordinates is not None
