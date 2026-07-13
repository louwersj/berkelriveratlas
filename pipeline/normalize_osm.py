from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from common import APP_DIR, DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json

CHUNK_SIZE_LIMIT_BYTES = 4_750_000
SPATIAL_TILE_DIRECTORY_NAME = "_tiles"
SPATIAL_TILE_GRID = (16, 16)
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
    tile_dir = source_dir / SPATIAL_TILE_DIRECTORY_NAME
    target_tile_dir = target_dir / SPATIAL_TILE_DIRECTORY_NAME
    if tile_dir.exists():
        shutil.copytree(tile_dir, target_tile_dir, dirs_exist_ok=True)


def write_layers(target_dir: Path, layers: dict[str, dict[str, Any]]) -> None:
    bundle_dir = target_dir / CHUNK_DIRECTORY_NAME
    tile_dir = target_dir / SPATIAL_TILE_DIRECTORY_NAME
    ensure_directory(bundle_dir)
    ensure_directory(tile_dir)
    for filename, payload in layers.items():
        write_layer(target_dir, bundle_dir, tile_dir, filename, payload)


def write_layer(target_dir: Path, bundle_dir: Path, tile_dir: Path, filename: str, payload: dict[str, Any]) -> None:
    chunks = chunk_features(payload["features"])
    layer_id = filename.removesuffix(".geojson")
    if len(chunks) > 1:
        write_bundle_manifest(bundle_dir, target_dir, layer_id, payload, chunks)
        write_tile_manifest(tile_dir, target_dir, layer_id, payload)
        return
    if len(chunks) <= 1:
        write_json(target_dir / filename, payload, indent=None)
        return

def write_bundle_manifest(
    bundle_dir: Path,
    target_dir: Path,
    layer_id: str,
    payload: dict[str, Any],
    chunks: list[list[dict[str, Any]]],
) -> None:
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


def write_tile_manifest(tile_dir: Path, target_dir: Path, layer_id: str, payload: dict[str, Any]) -> None:
    features = payload["features"]
    layer_bbox = collection_bbox(features)
    if layer_bbox is None:
        return

    rows, cols = SPATIAL_TILE_GRID
    south, west, north, east = layer_bbox
    lat_step = max((north - south) / rows, 0.000001)
    lon_step = max((east - west) / cols, 0.000001)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for feature in features:
        feature_bbox = geometry_bbox(feature.get("geometry"))
        if feature_bbox is None:
            continue
        min_lat, min_lon, max_lat, max_lon = feature_bbox
        row_start = clamp_tile_index(int((min_lat - south) / lat_step), rows)
        row_end = clamp_tile_index(int((max_lat - south) / lat_step), rows)
        col_start = clamp_tile_index(int((min_lon - west) / lon_step), cols)
        col_end = clamp_tile_index(int((max_lon - west) / lon_step), cols)
        for row in range(row_start, row_end + 1):
            for col in range(col_start, col_end + 1):
                buckets.setdefault((row, col), []).append(feature)

    layer_tile_dir = tile_dir / layer_id
    ensure_directory(layer_tile_dir)
    manifest_tiles: list[dict[str, Any]] = []

    for row in range(rows):
        for col in range(cols):
            tile_features = buckets.get((row, col), [])
            tile_south = south + (lat_step * row)
            tile_west = west + (lon_step * col)
            tile_north = north if row == rows - 1 else south + (lat_step * (row + 1))
            tile_east = east if col == cols - 1 else west + (lon_step * (col + 1))
            tile_id = f"r{row + 1:02d}-c{col + 1:02d}"
            tile_filename = f"{tile_id}.geojson"
            tile_relative_url = f"data/geo/{SPATIAL_TILE_DIRECTORY_NAME}/{layer_id}/{tile_filename}"
            tile_collection = {
                "type": "FeatureCollection",
                "generated_at": payload.get("generated_at"),
                "features": tile_features,
            }
            write_json(layer_tile_dir / tile_filename, tile_collection, indent=None)
            manifest_tiles.append(
                {
                    "id": tile_id,
                    "row": row + 1,
                    "col": col + 1,
                    "bbox": [tile_south, tile_west, tile_north, tile_east],
                    "url": tile_relative_url,
                    "featureCount": len(tile_features),
                    "bytes": json_size_bytes(tile_collection),
                }
            )

    manifest = {
        "type": "geojson_tile_set",
        "generatedAt": payload.get("generated_at"),
        "layerId": layer_id,
        "featureCount": len(features),
        "tileGrid": [rows, cols],
        "bbox": [south, west, north, east],
        "tiles": manifest_tiles,
    }
    write_json(target_dir / f"{layer_id}.tiles.json", manifest)


def clear_generated_outputs(directory: Path) -> None:
    bundle_dir = directory / CHUNK_DIRECTORY_NAME
    tile_dir = directory / SPATIAL_TILE_DIRECTORY_NAME
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if tile_dir.exists():
        shutil.rmtree(tile_dir)

    for basename in GENERATED_LAYER_BASENAMES:
        for suffix in (".geojson", ".manifest.json", ".tiles.json"):
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


def clamp_tile_index(index: int, size: int) -> int:
    return max(0, min(index, size - 1))


def collection_bbox(features: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    latitudes: list[float] = []
    longitudes: list[float] = []
    for feature in features:
        bbox = geometry_bbox(feature.get("geometry"))
        if bbox is None:
            continue
        min_lat, min_lon, max_lat, max_lon = bbox
        latitudes.extend([min_lat, max_lat])
        longitudes.extend([min_lon, max_lon])
    if not latitudes or not longitudes:
        return None
    return (min(latitudes), min(longitudes), max(latitudes), max(longitudes))


def geometry_bbox(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not geometry:
        return None
    coordinates = geometry.get("coordinates")
    if coordinates is None:
        return None
    points: list[tuple[float, float]] = []
    collect_points(coordinates, points)
    if not points:
        return None
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return (min(latitudes), min(longitudes), max(latitudes), max(longitudes))


def collect_points(coordinates: Any, points: list[tuple[float, float]]) -> None:
    if isinstance(coordinates, list) and coordinates and isinstance(coordinates[0], (int, float)):
        points.append((float(coordinates[0]), float(coordinates[1])))
        return
    if isinstance(coordinates, list):
        for child in coordinates:
            collect_points(child, points)


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
