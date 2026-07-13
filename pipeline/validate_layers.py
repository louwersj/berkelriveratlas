from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from common import APP_DIR


SECRET_PATTERN = re.compile(r"AIza[0-9A-Za-z\-_]{20,}")
MAX_TRACKED_GEO_ASSET_BYTES = 5 * 1024 * 1024


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
        manifest_url = layer.get("manifestUrl")
        if layer_type == "geojson":
            if url:
                local_path = APP_DIR / "data" / Path(url).relative_to("data")
                if not local_path.exists():
                    errors.append(f"missing local layer file for {layer_id}: {url}")
            elif manifest_url:
                errors.extend(validate_manifest(layer_id, manifest_url))
            else:
                errors.append(f"geojson layer {layer_id} is missing both url and manifestUrl")

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


def validate_manifest(layer_id: str, manifest_url: str) -> list[str]:
    errors: list[str] = []
    manifest_path = APP_DIR / "data" / Path(manifest_url).relative_to("data")
    if not manifest_path.exists():
        return [f"missing local layer manifest for {layer_id}: {manifest_url}"]

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks", [])
    if not chunks:
        errors.append(f"layer manifest {layer_id} has no chunks")
        return errors

    for chunk in chunks:
        chunk_url = chunk.get("url")
        if not chunk_url:
            errors.append(f"layer manifest {layer_id} has a chunk without a url")
            continue
        chunk_path = APP_DIR / "data" / Path(chunk_url).relative_to("data")
        if not chunk_path.exists():
            errors.append(f"missing local layer chunk for {layer_id}: {chunk_url}")

    return errors


def validate_geo_asset_sizes() -> list[str]:
    errors: list[str] = []
    for root in (APP_DIR / "data/geo", Path("data-source/geo")):
        for path in root.rglob("*.geojson"):
            size = path.stat().st_size
            if size > MAX_TRACKED_GEO_ASSET_BYTES:
                errors.append(
                    f"tracked geo asset exceeds {MAX_TRACKED_GEO_ASSET_BYTES} bytes: {path} ({size} bytes)"
                )
        for path in root.rglob("*.json"):
            if path.name.endswith(".manifest.json"):
                size = path.stat().st_size
                if size > MAX_TRACKED_GEO_ASSET_BYTES:
                    errors.append(
                        f"tracked manifest exceeds {MAX_TRACKED_GEO_ASSET_BYTES} bytes: {path} ({size} bytes)"
                    )
    return errors


if __name__ == "__main__":
    size_errors = validate_geo_asset_sizes()
    if size_errors:
        print("Layer validation failed:")
        for error in size_errors:
            print(f"- {error}")
        sys.exit(1)
    sys.exit(main())
