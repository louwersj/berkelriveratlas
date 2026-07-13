from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from common import DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json


class OverpassFetchError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def main() -> int:
    settings = json.loads(read_text(DATA_SOURCE_DIR / "osm/settings.json"))
    raw_dir = DATA_SOURCE_DIR / "osm/raw"
    rendered_dir = raw_dir / "rendered-queries"
    status_path = raw_dir / "refresh-status.json"
    ensure_directory(raw_dir)
    ensure_directory(rendered_dir)

    queries = sorted((DATA_SOURCE_DIR / "osm/queries").glob("*.overpassql"))
    query_filter = os.environ.get("ATLAS_OSM_QUERY_FILTER")
    if query_filter:
        queries = [path for path in queries if path.stem == query_filter or path.name == query_filter]
    if not queries:
        write_status_report(
            status_path,
            {
                "generated_at": now_iso(),
                "overall_status": "failed",
                "message": f"No OSM queries matched filter {query_filter!r}." if query_filter else "No OSM queries found.",
                "results": [],
            },
        )
        raise SystemExit(f"No OSM queries matched filter {query_filter!r}." if query_filter else "No OSM queries found.")
    query_context = build_query_context(settings)
    continue_on_failure = bool(settings.get("continueOnQueryFailure", False))
    results: list[dict[str, object]] = []
    had_failure = False

    for index, query_path in enumerate(queries):
        template = read_text(query_path)
        rendered_query = render_query(template, query_context)
        rendered_path = rendered_dir / query_path.name
        rendered_path.write_text(rendered_query, encoding="utf-8")
        print(f"STARTING: {query_path.name}")

        try:
            payload, fetch_meta = fetch_query_payload(settings, template, query_context, query_path.stem)
            output_path = raw_dir / f"{query_path.stem}.json"
            write_json(
                output_path,
                {
                    "generated_at": now_iso(),
                    "query_file": query_path.name,
                    "settings": settings,
                    "elements": payload.get("elements", []),
                    "osm3s": payload.get("osm3s"),
                    "remark": payload.get("remark"),
                    "fetch_meta": fetch_meta,
                },
            )
            element_count = len(payload.get("elements", []))
            print(f"FETCHED: {query_path.name} -> {output_path.relative_to(DATA_SOURCE_DIR)} ({element_count} elements)")
            results.append(
                {
                    "query": query_path.name,
                    "status": "fetched",
                    "output_file": str(output_path.relative_to(DATA_SOURCE_DIR)),
                    "element_count": element_count,
                    "fetch_meta": fetch_meta,
                }
            )
        except OverpassFetchError as error:
            had_failure = True
            status = "skipped" if continue_on_failure else "failed"
            print(f"{status.upper()}: {query_path.name} -> {error}")
            results.append(
                {
                    "query": query_path.name,
                    "status": status,
                    "error": str(error),
                    "retryable": error.retryable,
                }
            )
            write_status_report(
                status_path,
                {
                    "generated_at": now_iso(),
                    "overall_status": "partial" if continue_on_failure else "failed",
                    "results": results,
                },
            )
            if not continue_on_failure:
                raise SystemExit(
                    f"OSM refresh failed on {query_path.name}. See {status_path.relative_to(DATA_SOURCE_DIR)} for details."
                )
        except KeyboardInterrupt:
            results.append(
                {
                    "query": query_path.name,
                    "status": "interrupted",
                    "message": "Refresh interrupted by user.",
                }
            )
            write_status_report(
                status_path,
                {
                    "generated_at": now_iso(),
                    "overall_status": "interrupted",
                    "results": results,
                },
            )
            print(
                f"INTERRUPTED: {query_path.name}. Details written to {status_path.relative_to(DATA_SOURCE_DIR)}"
            )
            raise SystemExit(130)

        if index + 1 < len(queries):
            time.sleep(float(settings.get("requestDelaySeconds", 1.0)))

    overall_status = "partial" if had_failure else "success"
    write_status_report(
        status_path,
        {
            "generated_at": now_iso(),
            "overall_status": overall_status,
            "results": results,
        },
    )
    print(f"REFRESH STATUS: {overall_status}. Details written to {status_path.relative_to(DATA_SOURCE_DIR)}")
    return 0


def write_status_report(path, payload: dict[str, object]) -> None:
    write_json(path, payload)


def fetch_query_payload(
    settings: dict, template: str, query_context: dict[str, str], query_name: str
) -> tuple[dict, dict]:
    max_depth = max_tile_subdivision_depth(settings, query_name)
    initial_tile_grid = tile_grid_for_query(settings, query_name, current_depth=1)
    tile_grid_sequence = tile_grid_sequence_for_query(settings, query_name, max_depth)
    if should_tile_first(settings, query_name):
        payload, tile_count = fetch_tiled_payload(
            settings,
            template,
            query_context,
            query_name=query_name,
            max_depth=max_depth,
            current_depth=1,
            tile_grid=initial_tile_grid,
        )
        return payload, {
            "mode": "tiled",
            "tile_count": tile_count,
            "initial_tile_grid": initial_tile_grid,
            "tile_grid_sequence": tile_grid_sequence,
        }

    rendered_query = render_query(template, query_context)
    try:
        return fetch_overpass(settings, rendered_query), {"mode": "single"}
    except OverpassFetchError as error:
        if not error.retryable:
            raise

    payload, tile_count = fetch_tiled_payload(
        settings,
        template,
        query_context,
        query_name=query_name,
        max_depth=max_depth,
        current_depth=1,
        tile_grid=initial_tile_grid,
    )
    return payload, {
        "mode": "tiled",
        "tile_count": tile_count,
        "initial_tile_grid": initial_tile_grid,
        "tile_grid_sequence": tile_grid_sequence,
    }


def should_tile_first(settings: dict, query_name: str) -> bool:
    prefixes = settings.get("alwaysTileQueryPrefixes", [])
    return any(query_name.startswith(prefix) for prefix in prefixes)


def build_query_context(settings: dict) -> dict[str, str]:
    south, west, north, east = settings["berkelRegionBbox"]
    return {
        "bbox_south": f"{south:.6f}",
        "bbox_west": f"{west:.6f}",
        "bbox_north": f"{north:.6f}",
        "bbox_east": f"{east:.6f}",
        "riverbank_building_distance_m": str(int(settings["riverbankBuildingDistanceM"])),
        "overpass_timeout_seconds": str(int(settings.get("overpassTimeoutSeconds", 180))),
    }


def render_query(template: str, context: dict[str, str]) -> str:
    query = template
    for key, value in context.items():
        query = query.replace(f"{{{{{key}}}}}", value)
    return query


def split_bbox_context(context: dict[str, str], tile_grid: tuple[int, int]) -> list[dict[str, str]]:
    south = float(context["bbox_south"])
    west = float(context["bbox_west"])
    north = float(context["bbox_north"])
    east = float(context["bbox_east"])
    rows, cols = tile_grid
    lat_step = (north - south) / rows
    lon_step = (east - west) / cols
    contexts: list[dict[str, str]] = []
    for row in range(rows):
        for col in range(cols):
            bbox_south = south + (lat_step * row)
            bbox_west = west + (lon_step * col)
            bbox_north = north if row == rows - 1 else south + (lat_step * (row + 1))
            bbox_east = east if col == cols - 1 else west + (lon_step * (col + 1))
            contexts.append(
                {
                    **context,
                    "bbox_south": f"{bbox_south:.6f}",
                    "bbox_west": f"{bbox_west:.6f}",
                    "bbox_north": f"{bbox_north:.6f}",
                    "bbox_east": f"{bbox_east:.6f}",
                }
            )
    return contexts


def fetch_tiled_payload(
    settings: dict,
    template: str,
    context: dict[str, str],
    query_name: str,
    max_depth: int,
    current_depth: int,
    tile_grid: tuple[int, int],
    tile_path: tuple[int, ...] = (),
) -> tuple[dict, int]:
    merged_elements: dict[tuple[str, int], dict] = {}
    osm3s = None
    remarks: list[str] = []
    tile_count = 0

    tile_contexts = split_bbox_context(context, tile_grid)
    rows, cols = tile_grid
    for tile_index, tile_context in enumerate(tile_contexts, start=1):
        tile_query = render_query(template, tile_context)
        current_tile_path = (*tile_path, tile_index)
        tile_path_label = ".".join(str(part) for part in current_tile_path)
        print(
            "TILE: "
            f"{query_name} depth={current_depth}/{max_depth} path={tile_path_label} tile={tile_index}/{len(tile_contexts)} "
            f"grid={rows}x{cols} "
            f"bbox={tile_context['bbox_south']},{tile_context['bbox_west']},{tile_context['bbox_north']},{tile_context['bbox_east']}"
        )
        try:
            payload = fetch_overpass(settings, tile_query)
            tile_count += 1
            print(
                f"TILE FETCHED: {query_name} depth={current_depth}/{max_depth} path={tile_path_label} tile={tile_index}/{len(tile_contexts)} "
                f"grid={rows}x{cols} "
                f"({len(payload.get('elements', []))} elements)"
            )
        except OverpassFetchError as error:
            if not error.retryable or current_depth >= max_depth:
                print(
                    f"TILE FAILED: {query_name} depth={current_depth}/{max_depth} path={tile_path_label} tile={tile_index}/{len(tile_contexts)} grid={rows}x{cols} -> {error}"
                )
                raise
            print(
                f"TILE RETRYING VIA SUBDIVISION: {query_name} depth={current_depth}/{max_depth} path={tile_path_label} tile={tile_index}/{len(tile_contexts)} grid={rows}x{cols} -> {error}"
            )
            payload, nested_tile_count = fetch_tiled_payload(
                settings,
                template,
                tile_context,
                query_name=query_name,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                tile_grid=tile_grid_for_query(settings, query_name, current_depth=current_depth + 1),
                tile_path=current_tile_path,
            )
            tile_count += nested_tile_count

        osm3s = payload.get("osm3s", osm3s)
        if payload.get("remark"):
            remarks.append(payload["remark"])
        for element in payload.get("elements", []):
            merged_elements[(element["type"], element["id"])] = element
        time.sleep(float(settings.get("requestDelaySeconds", 1.0)))

    return (
        {
            "elements": list(merged_elements.values()),
            "osm3s": osm3s,
            "remark": " | ".join(remarks) if remarks else None,
        },
        tile_count,
    )


def fetch_overpass(settings: dict, query: str) -> dict:
    timeout = int(settings.get("overpassTimeoutSeconds", 180)) + 30
    max_retries = int(settings.get("maxRequestRetries", 3))
    backoff = float(settings.get("retryBackoffSeconds", 5.0))
    endpoints = settings.get("overpassUrls") or [settings["overpassUrl"]]

    for attempt in range(max_retries):
        last_error: OverpassFetchError | None = None
        for endpoint in endpoints:
            request = urllib.request.Request(
                endpoint,
                data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "User-Agent": settings.get("userAgent", "BerkelRiverAtlas/0.1"),
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                retryable = error.code in {429, 502, 503, 504}
                last_error = OverpassFetchError(
                    f"Overpass request to {endpoint} failed with HTTP {error.code}: {body[:500]}",
                    retryable=retryable,
                )
                if not retryable:
                    raise last_error from error
            except urllib.error.URLError as error:
                reason = str(error.reason)
                retryable = "timed out" in reason.lower() or "temporary failure" in reason.lower()
                last_error = OverpassFetchError(
                    f"Overpass request to {endpoint} failed: {reason}",
                    retryable=retryable,
                )
                if not retryable:
                    raise last_error from error
            except TimeoutError as error:
                last_error = OverpassFetchError(
                    f"Overpass request to {endpoint} failed: socket read timed out",
                    retryable=True,
                )

        if last_error and attempt + 1 < max_retries and last_error.retryable:
            time.sleep(backoff * (attempt + 1))
            continue
        if last_error:
            raise last_error

    raise OverpassFetchError("Overpass request failed after all retry attempts.")


def max_tile_subdivision_depth(settings: dict, query_name: str) -> int:
    override = (settings.get("queryMaxTileSubdivisionDepth") or {}).get(query_name)
    if override is not None:
        return int(override)
    return int(settings.get("maxTileSubdivisionDepth", 2))


def tile_grid_for_query(settings: dict, query_name: str, current_depth: int) -> tuple[int, int]:
    per_query = settings.get("queryTileGrids") or {}
    grid_value = per_query.get(query_name)
    if isinstance(grid_value, list) and len(grid_value) >= current_depth:
        return normalize_tile_grid(grid_value[current_depth - 1])
    if grid_value is not None and not isinstance(grid_value, list):
        return normalize_tile_grid(grid_value)

    default_grid = settings.get("tileGridByDepth") or {}
    return normalize_tile_grid(default_grid.get(str(current_depth), [2, 2]))


def tile_grid_sequence_for_query(settings: dict, query_name: str, max_depth: int) -> list[list[int]]:
    sequence: list[list[int]] = []
    for depth in range(1, max_depth + 1):
        rows, cols = tile_grid_for_query(settings, query_name, current_depth=depth)
        sequence.append([rows, cols])
    return sequence


def normalize_tile_grid(value: object) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"Invalid tile grid setting: {value!r}")
    rows = int(value[0])
    cols = int(value[1])
    if rows < 1 or cols < 1:
        raise ValueError(f"Tile grid values must be positive: {value!r}")
    return rows, cols


if __name__ == "__main__":
    raise SystemExit(main())
