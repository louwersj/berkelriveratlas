from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json


AREA_KEYS = {"building", "landuse", "natural", "amenity", "leisure", "water", "waterway", "historic"}
AREA_VALUES = {"yes", "residential", "industrial", "commercial", "retail", "forest", "grass", "park", "water"}


@dataclass
class ElementIndex:
    nodes: dict[int, dict[str, Any]]
    ways: dict[int, dict[str, Any]]
    relations: dict[int, dict[str, Any]]


def main() -> int:
    raw_dir = DATA_SOURCE_DIR / "osm/raw"
    normalized_dir = DATA_SOURCE_DIR / "osm/normalized"
    ensure_directory(normalized_dir)

    converted_count = 0
    for raw_path in sorted(raw_dir.glob("*.json")):
        if raw_path.parent.name == "rendered-queries":
            continue
        payload = json.loads(read_text(raw_path))
        index = build_index(payload.get("elements", []))
        features = convert_elements(index, raw_path.stem, payload.get("settings", {}))
        output_path = normalized_dir / f"{raw_path.stem}.geojson"
        write_json(
            output_path,
            {
                "type": "FeatureCollection",
                "generated_at": now_iso(),
                "source_file": raw_path.name,
                "features": features,
            },
            indent=None,
        )
        converted_count += 1
        print(f"Converted {raw_path.name} -> {output_path.relative_to(DATA_SOURCE_DIR)}")

    print(f"Converted {converted_count} raw OSM files.")
    return 0


def build_index(elements: list[dict[str, Any]]) -> ElementIndex:
    nodes: dict[int, dict[str, Any]] = {}
    ways: dict[int, dict[str, Any]] = {}
    relations: dict[int, dict[str, Any]] = {}
    for element in elements:
        if element["type"] == "node":
            nodes[element["id"]] = element
        elif element["type"] == "way":
            ways[element["id"]] = element
        elif element["type"] == "relation":
            relations[element["id"]] = element
    return ElementIndex(nodes=nodes, ways=ways, relations=relations)


def convert_elements(index: ElementIndex, query_name: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []

    for node in index.nodes.values():
        tags = node.get("tags")
        if not tags:
            continue
        features.append(
            feature_from_element(
                node,
                {
                    "type": "Point",
                    "coordinates": [node["lon"], node["lat"]],
                },
                query_name,
                settings,
            )
        )

    for way in index.ways.values():
        tags = way.get("tags")
        if not tags:
            continue
        coordinates = coordinates_for_way(way, index)
        if len(coordinates) < 2:
            continue
        geometry: dict[str, Any]
        if is_area_way(way, coordinates):
            geometry = {"type": "Polygon", "coordinates": [close_ring(coordinates)]}
        else:
            geometry = {"type": "LineString", "coordinates": coordinates}
        features.append(feature_from_element(way, geometry, query_name, settings))

    for relation in index.relations.values():
        tags = relation.get("tags")
        if not tags:
            continue
        geometry = geometry_for_relation(relation, index)
        if geometry is None:
            continue
        features.append(feature_from_element(relation, geometry, query_name, settings))

    return features


def feature_from_element(
    element: dict[str, Any], geometry: dict[str, Any], query_name: str, settings: dict[str, Any]
) -> dict[str, Any]:
    tags = element.get("tags", {})
    extra_props: dict[str, Any] = {}
    if query_name == "05-buildings-near-riverbanks":
        extra_props["riverbank_distance_m"] = settings.get("riverbankBuildingDistanceM")
    return {
        "type": "Feature",
        "id": f"{element['type']}/{element['id']}",
        "geometry": geometry,
        "properties": {
            "source": "osm",
            "query_name": query_name,
            "osm_type": element["type"],
            "osm_id": element["id"],
            "name": tags.get("name"),
            "tags": tags,
            "source_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
            **extra_props,
        },
    }


def coordinates_for_way(way: dict[str, Any], index: ElementIndex) -> list[list[float]]:
    coords: list[list[float]] = []
    for node_id in way.get("nodes", []):
        node = index.nodes.get(node_id)
        if node is not None:
            coords.append([node["lon"], node["lat"]])
    return coords


def geometry_for_relation(relation: dict[str, Any], index: ElementIndex) -> dict[str, Any] | None:
    relation_type = relation.get("tags", {}).get("type")
    if relation_type not in {"multipolygon", "boundary"}:
        return None

    outer_rings: list[list[list[float]]] = []
    inner_rings: list[list[list[float]]] = []

    for member in relation.get("members", []):
        if member.get("type") != "way":
            continue
        way = index.ways.get(member.get("ref"))
        if not way:
            continue
        coords = coordinates_for_way(way, index)
        if len(coords) < 3:
            continue
        ring = close_ring(coords)
        if member.get("role") == "inner":
            inner_rings.append(ring)
        else:
            outer_rings.append(ring)

    if not outer_rings:
        return None
    if len(outer_rings) == 1:
        polygon = [outer_rings[0], *inner_rings]
        return {"type": "Polygon", "coordinates": polygon}
    polygons = [[ring] for ring in outer_rings]
    return {"type": "MultiPolygon", "coordinates": polygons}


def is_area_way(way: dict[str, Any], coordinates: list[list[float]]) -> bool:
    if len(coordinates) < 4:
        return False
    if coordinates[0] != coordinates[-1]:
        return False
    tags = way.get("tags", {})
    if tags.get("area") == "yes":
        return True
    return any(key in AREA_KEYS or tags.get(key) in AREA_VALUES for key in tags)


def close_ring(coordinates: list[list[float]]) -> list[list[float]]:
    if coordinates and coordinates[0] != coordinates[-1]:
        return [*coordinates, coordinates[0]]
    return coordinates


if __name__ == "__main__":
    raise SystemExit(main())
