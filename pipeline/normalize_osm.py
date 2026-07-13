from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from common import APP_DIR, DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json

CHUNK_SIZE_LIMIT_BYTES = 4_750_000
GENERATED_LAYER_BASENAMES = (
    "base-linework.min",
    "base-paths.min",
    "base-roads.min",
    "base-waterways.min",
    "bridges.min",
    "waterworks.min",
    "heritage.min",
    "settlements.min",
    "landuse.min",
    "boundaries.min",
    "buildings-near-riverbanks",
)
CHUNK_DIRECTORY_NAME = "_bundles"


def main() -> int:
    normalized_dir = DATA_SOURCE_DIR / "osm/normalized"
    geo_dir = DATA_SOURCE_DIR / "geo"
    app_geo_dir = APP_DIR / "data/geo"
    ensure_directory(geo_dir)
    ensure_directory(app_geo_dir)

    features = load_normalized_features(normalized_dir)
    if not features:
        print("No normalized OSM features found; preserved existing GeoJSON layers.")
        return 0

    clear_generated_outputs(geo_dir)
    clear_generated_outputs(app_geo_dir)
    layers = build_layers(features)

    write_layers(geo_dir, layers)
    sync_geo_directory(geo_dir, app_geo_dir)

    print(f"Built {len(layers)} OSM-derived GeoJSON layers.")
    return 0


def load_normalized_features(normalized_dir: Path) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for path in sorted(normalized_dir.glob("*.geojson")):
        if path.name == "all-features.geojson":
            continue
        payload = json.loads(read_text(path))
        features.extend(payload.get("features", []))
    return features


def build_layers(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    layers = {
        "base-roads.min.geojson": collection(),
        "base-paths.min.geojson": collection(),
        "base-waterways.min.geojson": collection(),
        "bridges.min.geojson": collection(),
        "waterworks.min.geojson": collection(),
        "heritage.min.geojson": collection(),
        "settlements.min.geojson": collection(),
        "landuse.min.geojson": collection(),
        "boundaries.min.geojson": collection(),
        "buildings-near-riverbanks.geojson": collection(),
    }

    for feature in features:
        tags = feature.get("properties", {}).get("tags", {})
        query_name = feature.get("properties", {}).get("query_name", "")
        geometry_type = feature.get("geometry", {}).get("type")
        normalized_props = normalize_properties(feature)
        feature["properties"] = normalized_props

        if "highway" in tags:
            if tags["highway"] in {"path", "footway", "cycleway", "track", "bridleway", "steps"}:
                layers["base-paths.min.geojson"]["features"].append(feature)
            else:
                layers["base-roads.min.geojson"]["features"].append(feature)

        if "waterway" in tags:
            layers["base-waterways.min.geojson"]["features"].append(feature)

        if tags.get("bridge") not in (None, "no") or feature.get("properties", {}).get("category") == "bridge":
            layers["bridges.min.geojson"]["features"].append(feature)

        if "man_made" in tags or tags.get("water") or tags.get("waterworks"):
            if feature not in layers["waterworks.min.geojson"]["features"]:
                layers["waterworks.min.geojson"]["features"].append(feature)

        if "historic" in tags:
            layers["heritage.min.geojson"]["features"].append(feature)

        if tags.get("place"):
            layers["settlements.min.geojson"]["features"].append(feature)

        if tags.get("landuse"):
            layers["landuse.min.geojson"]["features"].append(feature)

        if query_name == "05-buildings-near-riverbanks" or ("building" in tags and geometry_type in {"Polygon", "MultiPolygon"}):
            if query_name == "05-buildings-near-riverbanks":
                layers["buildings-near-riverbanks.geojson"]["features"].append(feature)

        if tags.get("boundary") or feature.get("properties", {}).get("category") == "boundary":
            layers["boundaries.min.geojson"]["features"].append(feature)

    base_linework = collection()
    base_linework["features"] = [
        *layers["base-roads.min.geojson"]["features"],
        *layers["base-paths.min.geojson"]["features"],
        *layers["base-waterways.min.geojson"]["features"],
    ]
    layers["base-linework.min.geojson"] = base_linework

    for payload in layers.values():
        payload["generated_at"] = now_iso()

    return layers


def collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": []}


def sync_geo_directory(source_dir: Path, target_dir: Path) -> None:
    for item in source_dir.glob("*.geojson"):
        shutil.copy2(item, target_dir / item.name)
    for item in source_dir.glob("*.json"):
        shutil.copy2(item, target_dir / item.name)
    bundle_dir = source_dir / CHUNK_DIRECTORY_NAME
    target_bundle_dir = target_dir / CHUNK_DIRECTORY_NAME
    if bundle_dir.exists():
        shutil.copytree(bundle_dir, target_bundle_dir, dirs_exist_ok=True)


def write_layers(target_dir: Path, layers: dict[str, dict[str, Any]]) -> None:
    bundle_dir = target_dir / CHUNK_DIRECTORY_NAME
    ensure_directory(bundle_dir)
    for filename, payload in layers.items():
        write_layer(target_dir, bundle_dir, filename, payload)


def write_layer(target_dir: Path, bundle_dir: Path, filename: str, payload: dict[str, Any]) -> None:
    chunks = chunk_features(payload["features"])
    if len(chunks) <= 1:
        write_json(target_dir / filename, payload, indent=None)
        return

    layer_id = filename.removesuffix(".geojson")
    layer_bundle_dir = bundle_dir / layer_id
    ensure_directory(layer_bundle_dir)
    manifest_chunks: list[dict[str, Any]] = []

    for index, chunk_features_payload in enumerate(chunks, start=1):
        chunk_filename = f"{layer_id}-{index:03d}.geojson"
        chunk_relative_url = f"data/geo/{CHUNK_DIRECTORY_NAME}/{layer_id}/{chunk_filename}"
        chunk_collection = {
            "type": "FeatureCollection",
            "generated_at": payload.get("generated_at"),
            "features": chunk_features_payload,
        }
        write_json(layer_bundle_dir / chunk_filename, chunk_collection, indent=None)
        manifest_chunks.append(
            {
                "url": chunk_relative_url,
                "featureCount": len(chunk_features_payload),
                "bytes": json_size_bytes(chunk_collection),
            }
        )

    manifest = {
        "type": "geojson_bundle",
        "generatedAt": payload.get("generated_at"),
        "layerId": layer_id,
        "featureCount": len(payload["features"]),
        "chunkCount": len(manifest_chunks),
        "chunkSizeLimitBytes": CHUNK_SIZE_LIMIT_BYTES,
        "chunks": manifest_chunks,
    }
    write_json(target_dir / f"{layer_id}.manifest.json", manifest)


def clear_generated_outputs(directory: Path) -> None:
    bundle_dir = directory / CHUNK_DIRECTORY_NAME
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    for basename in GENERATED_LAYER_BASENAMES:
        for suffix in (".geojson", ".manifest.json"):
            path = directory / f"{basename}{suffix}"
            if path.exists():
                path.unlink()


def chunk_features(features: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current_chunk: list[dict[str, Any]] = []
    current_size = collection_overhead_bytes()

    for feature in features:
        feature_size = feature_size_bytes(feature)
        feature_entry_size = feature_size + (1 if current_chunk else 0)

        if current_chunk and current_size + feature_entry_size > CHUNK_SIZE_LIMIT_BYTES:
            chunks.append(current_chunk)
            current_chunk = [feature]
            current_size = collection_overhead_bytes() + feature_size
            continue

        current_chunk.append(feature)
        current_size += feature_entry_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def collection_overhead_bytes() -> int:
    return len('{"type":"FeatureCollection","features":[]}\n'.encode("utf-8"))


def feature_size_bytes(feature: dict[str, Any]) -> int:
    return len(json.dumps(feature, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def json_size_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1


def normalize_properties(feature: dict[str, Any]) -> dict[str, Any]:
    raw = feature.get("properties", {})
    tags = raw.get("tags", {})
    highway = tags.get("highway")
    category = infer_category(tags)
    subtype = (
        highway
        or tags.get("waterway")
        or tags.get("building")
        or tags.get("historic")
        or tags.get("place")
        or tags.get("landuse")
        or tags.get("boundary")
        or tags.get("man_made")
    )
    display_class = infer_display_class(tags, category)
    is_bridge = tags.get("bridge") not in (None, "no")
    return {
        "source": "osm",
        "query_name": raw.get("query_name"),
        "osm_type": raw.get("osm_type"),
        "osm_id": raw.get("osm_id"),
        "category": category,
        "subtype": subtype,
        "name": raw.get("name"),
        "is_bridge": is_bridge,
        "display_class": display_class,
        "source_url": raw.get("source_url"),
        "riverbank_distance_m": raw.get("riverbank_distance_m") or tags.get("riverbank_distance_m"),
    }


def infer_category(tags: dict[str, Any]) -> str:
    if "highway" in tags:
        return "path" if tags["highway"] in {"path", "footway", "cycleway", "track", "bridleway", "steps"} else "road"
    if "waterway" in tags:
        return "waterway"
    if "building" in tags:
        return "building"
    if "historic" in tags:
        return "heritage"
    if "place" in tags:
        return "settlement"
    if "landuse" in tags:
        return "landuse"
    if "boundary" in tags:
        return "boundary"
    if "man_made" in tags:
        return "waterwork"
    return "feature"


def infer_display_class(tags: dict[str, Any], category: str) -> str:
    if category == "road":
        return f"road_{tags.get('highway', 'unknown')}"
    if category == "path":
        return "path"
    if category == "building":
        return "building_riverside"
    if category == "waterway":
        return f"waterway_{tags.get('waterway', 'unknown')}"
    return category


if __name__ == "__main__":
    raise SystemExit(main())
