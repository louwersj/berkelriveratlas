from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from common import APP_DIR, DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json


def main() -> int:
    normalized_dir = DATA_SOURCE_DIR / "osm/normalized"
    geo_dir = DATA_SOURCE_DIR / "geo"
    app_geo_dir = APP_DIR / "data/geo"
    ensure_directory(geo_dir)
    ensure_directory(app_geo_dir)

    features = load_normalized_features(normalized_dir)
    if not features:
        sync_geo_directory(geo_dir, app_geo_dir)
        print("No normalized OSM features found; preserved existing GeoJSON layers.")
        return 0

    layers = build_layers(features)

    for filename, payload in layers.items():
        write_json(geo_dir / filename, payload, indent=None)
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
