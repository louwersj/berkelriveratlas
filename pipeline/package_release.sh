#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 - <<'PY'
import json
from pathlib import Path
package = json.loads((Path.cwd() / "package.json").read_text())
print(package["version"])
PY
)"
TARGET_DIR="${ROOT_DIR}/releases/${VERSION}/app"

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
cp -R "${ROOT_DIR}/app/." "${TARGET_DIR}/"
cp -R "${ROOT_DIR}/documentation" "${TARGET_DIR}/documentation"

echo "Packaged release at ${TARGET_DIR}"
