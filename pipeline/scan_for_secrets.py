from __future__ import annotations

import re
import sys
from pathlib import Path

from common import ROOT


PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"BEGIN PRIVATE KEY"),
    re.compile(r"password\s*="),
    re.compile(r"secret\s*="),
    re.compile(r"api_key\s*="),
    re.compile(r"token\s*="),
]

IGNORED_PARTS = {"node_modules", ".git", "dist"}
IGNORED_FILES = {"scan_for_secrets.py"}


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name in IGNORED_FILES:
            continue
        if path.name == ".env":
            errors.append(f"unexpected .env file tracked: {path.relative_to(ROOT)}")
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                errors.append(f"potential secret match in {path.relative_to(ROOT)} for pattern {pattern.pattern}")

    if errors:
        print("Secret scan failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
