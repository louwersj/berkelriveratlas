from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from common import APP_DIR


SECRET_PATTERN = re.compile(r"AIza[0-9A-Za-z\-_]{20,}")


def main() -> int:
    path = APP_DIR / "config/layers.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    layer_ids: set[str] = set()
    errors: list[str] = []

    for layer in payload.get("layers", []):
        layer_id = layer.get("id")
        if layer_id in layer_ids:
            errors.append(f"duplicate layer id: {layer_id}")
        layer_ids.add(layer_id)

        layer_type = layer.get("type")
        url = layer.get("url")
        if layer_type == "geojson" and url:
            local_path = APP_DIR / "data" / Path(url).relative_to("data")
            if not local_path.exists():
                errors.append(f"missing local layer file for {layer_id}: {url}")

        if layer.get("requiresNetwork") or layer_type in {"wms_tile", "wmts_tile", "xyz_tile", "external_historic_tile"}:
            if not layer.get("attribution"):
                errors.append(f"external layer {layer_id} missing attribution")

        if layer_type in {"google_map_tiles", "google_earth_3d_optional"}:
            text = json.dumps(layer)
            if SECRET_PATTERN.search(text):
                errors.append(f"google layer {layer_id} appears to contain an API key")

    if errors:
        print("Layer validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(layer_ids)} layers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
