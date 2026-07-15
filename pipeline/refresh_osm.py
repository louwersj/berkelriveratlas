from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

from common import DATA_SOURCE_DIR, ensure_directory, now_iso, read_text, write_json


class OverpassFetchError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class QueryProgress:
    query_name: str
    total_area: float = 0.0
    planned_requests: int = 0
    completed_requests: int = 0
    covered_area: float = 0.0
    _planned_paths: set[str] = field(default_factory=set)
    _completed_paths: set[str] = field(default_factory=set)
    _covered_paths: set[str] = field(default_factory=set)

    def register_tile(self, tile_path_label: str) -> None:
        if tile_path_label in self._planned_paths:
            return
        self._planned_paths.add(tile_path_label)
        self.planned_requests += 1

    def subdivide_tile(self, tile_path_label: str, child_paths: list[str]) -> None:
        if tile_path_label in self._planned_paths:
            self._planned_paths.remove(tile_path_label)
            self.planned_requests = max(0, self.planned_requests - 1)
        for child_path in child_paths:
            self.register_tile(child_path)

    def mark_request_completed(self, tile_path_label: str) -> None:
        if tile_path_label in self._completed_paths:
            return
        self._completed_paths.add(tile_path_label)
        self.completed_requests += 1

    def mark_covered(self, tile_path_label: str, tile_area: float) -> None:
        if tile_path_label in self._covered_paths:
            return
        self._covered_paths.add(tile_path_label)
        self.covered_area += tile_area

    def requests_summary(self) -> str:
        return f"{self.completed_requests}/{self.planned_requests}"

    def coverage_percent(self) -> float:
        if self.total_area <= 0:
            return 0.0
        return min(100.0, (self.covered_area / self.total_area) * 100.0)

    def progress_fields(self) -> dict[str, str]:
        return {
            "coverage": f"{self.coverage_percent():.1f}%",
            "requests": self.requests_summary(),
        }


@dataclass(frozen=True)
class TileMask:
    query_name: str
    reason: str
    expanded_bboxes: list[tuple[float, float, float, float]]

    def intersects_context(self, context: dict[str, str]) -> bool:
        tile_bbox = context_bbox(context)
        return any(bboxes_intersect(tile_bbox, expanded_bbox) for expanded_bbox in self.expanded_bboxes)


def main() -> int:
    args = parse_args()
    settings = json.loads(read_text(DATA_SOURCE_DIR / "osm/settings.json"))
    raw_dir = DATA_SOURCE_DIR / "osm/raw"
    rendered_dir = raw_dir / "rendered-queries"
    tile_cache_dir = raw_dir / "tile-cache"
    status_path = raw_dir / "refresh-status.json"
    ensure_directory(raw_dir)
    ensure_directory(rendered_dir)
    ensure_directory(tile_cache_dir)

    queries = sorted((DATA_SOURCE_DIR / "osm/queries").glob("*.overpassql"))
    query_filter = os.environ.get("ATLAS_OSM_QUERY_FILTER")
    if query_filter:
        queries = [path for path in queries if path.stem == query_filter or path.name == query_filter]
    resume_from = args.resume_from
    if resume_from:
        queries, prior_results = apply_resume_from(queries, raw_dir, status_path, resume_from)
    else:
        prior_results = []
    if not queries:
        write_status_report(
            status_path,
            {
                "generated_at": now_iso(),
                "overall_status": "failed",
                "message": f"No OSM queries matched filter {query_filter!r}." if query_filter else "No OSM queries found.",
                "results": prior_results,
            },
        )
        raise SystemExit(f"No OSM queries matched filter {query_filter!r}." if query_filter else "No OSM queries found.")
    query_context = build_query_context(settings)
    continue_on_failure = bool(settings.get("continueOnQueryFailure", False))
    results: list[dict[str, object]] = [*prior_results]
    had_failure = False

    for index, query_path in enumerate(queries):
        template = read_text(query_path)
        rendered_query = render_query(template, query_context)
        rendered_path = rendered_dir / query_path.name
        rendered_path.write_text(rendered_query, encoding="utf-8")
        progress, tile_mask = initialize_query_progress(settings, query_path.stem, query_context)
        log_event(
            "STARTING",
            query=query_path.name,
            planned_tiles=str(progress.planned_requests),
            **progress.progress_fields(),
        )

        try:
            payload, fetch_meta = fetch_query_payload(
                settings, template, query_context, query_path.stem, progress, tile_mask, tile_cache_dir
            )
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
            log_event(
                "FETCHED",
                query=query_path.name,
                output=str(output_path.relative_to(DATA_SOURCE_DIR)),
                elements=str(element_count),
                **progress.progress_fields(),
            )
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
            log_event(status.upper(), query=query_path.name, error=str(error), **progress.progress_fields())
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
            log_event(
                "INTERRUPTED",
                query=query_path.name,
                details=str(status_path.relative_to(DATA_SOURCE_DIR)),
                **progress.progress_fields(),
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
    log_event("REFRESH_STATUS", status=overall_status, details=str(status_path.relative_to(DATA_SOURCE_DIR)))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh OSM raw data from stored Overpass queries.")
    parser.add_argument(
        "--resume-from",
        dest="resume_from",
        help="Resume from the named query file or stem, reusing earlier successful raw outputs already on disk.",
    )
    return parser.parse_args()


def write_status_report(path, payload: dict[str, object]) -> None:
    write_json(path, payload)


def apply_resume_from(
    queries: list, raw_dir, status_path, resume_from: str
) -> tuple[list, list[dict[str, object]]]:
    raw_dir = raw_dir.resolve()
    status_path = status_path.resolve()
    normalized_resume_from = normalize_query_identifier(resume_from)
    resume_index = next(
        (index for index, path in enumerate(queries) if normalize_query_identifier(path.name) == normalized_resume_from),
        None,
    )
    if resume_index is None:
        raise SystemExit(f"Cannot resume: no query matched {resume_from!r}.")

    prior_queries = queries[:resume_index]
    remaining_queries = queries[resume_index:]
    prior_results = load_prior_results(status_path)
    prior_results_by_query = {entry.get("query"): entry for entry in prior_results if entry.get("query")}
    resumed_results: list[dict[str, object]] = []

    for query_path in prior_queries:
        output_path = raw_dir / f"{query_path.stem}.json"
        if not output_path.exists():
            raise SystemExit(
                f"Cannot resume from {resume_from!r}: missing earlier raw output {output_path.relative_to(DATA_SOURCE_DIR)}."
            )
        preserved_result = preserve_prior_result(query_path.name, output_path, prior_results_by_query.get(query_path.name))
        resumed_results.append(preserved_result)
        log_event("RESUME_PRESERVED", query=query_path.name, output=str(output_path.relative_to(DATA_SOURCE_DIR)))

    log_event("RESUME_START", query=remaining_queries[0].name)
    return remaining_queries, resumed_results


def load_prior_results(status_path) -> list[dict[str, object]]:
    if not status_path.exists():
        return []
    payload = json.loads(read_text(status_path))
    results = payload.get("results", [])
    return results if isinstance(results, list) else []


def preserve_prior_result(query_name: str, output_path, previous_result: dict[str, object] | None) -> dict[str, object]:
    output_path = output_path.resolve()
    payload = json.loads(read_text(output_path))
    element_count = len(payload.get("elements", []))
    result: dict[str, object] = {
        "query": query_name,
        "status": "preserved",
        "output_file": str(output_path.relative_to(DATA_SOURCE_DIR)),
        "element_count": element_count,
    }
    fetch_meta = payload.get("fetch_meta")
    if fetch_meta:
        result["fetch_meta"] = fetch_meta
    if previous_result and previous_result.get("status"):
        result["previous_status"] = previous_result.get("status")
    return result


def normalize_query_identifier(value: str) -> str:
    normalized = value.strip()
    if normalized.endswith(".overpassql"):
        normalized = normalized.removesuffix(".overpassql")
    return normalized


def fetch_query_payload(
    settings: dict,
    template: str,
    query_context: dict[str, str],
    query_name: str,
    progress: QueryProgress,
    tile_mask: TileMask | None,
    tile_cache_dir,
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
            progress=progress,
            tile_mask=tile_mask,
            tile_cache_dir=tile_cache_dir,
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
    progress.register_tile("single")
    try:
        payload = fetch_overpass(settings, rendered_query, request_label=query_name, progress=progress)
        progress.mark_request_completed("single")
        progress.mark_covered("single", progress.total_area)
        return payload, {"mode": "single"}
    except OverpassFetchError as error:
        progress.mark_request_completed("single")
        if not error.retryable:
            raise

    payload, tile_count = fetch_tiled_payload(
        settings,
        template,
        query_context,
        query_name=query_name,
        progress=progress,
        tile_mask=tile_mask,
        tile_cache_dir=tile_cache_dir,
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
        "river_corridor_name_pattern": str(settings.get("riverCorridorNamePattern", "berkel")),
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
    progress: QueryProgress,
    tile_mask: TileMask | None,
    tile_cache_dir,
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
        if tile_mask and not tile_mask.intersects_context(tile_context):
            log_event(
                "TILE_SKIPPED",
                query=query_name,
                depth=f"{current_depth}/{max_depth}",
                path=tile_path_label,
                tile=f"{tile_index}/{len(tile_contexts)}",
                grid=f"{rows}x{cols}",
                reason=tile_mask.reason,
                **progress.progress_fields(),
            )
            continue
        tile_area = tile_area_ratio(context, tile_grid)
        cache_path = tile_cache_file_path(tile_cache_dir, query_name, current_tile_path)
        query_signature = query_signature_for_text(tile_query)
        log_event(
            "TILE",
            query=query_name,
            depth=f"{current_depth}/{max_depth}",
            path=tile_path_label,
            tile=f"{tile_index}/{len(tile_contexts)}",
            grid=f"{rows}x{cols}",
            bbox=(
                f"{tile_context['bbox_south']},{tile_context['bbox_west']},"
                f"{tile_context['bbox_north']},{tile_context['bbox_east']}"
            ),
            **progress.progress_fields(),
        )
        cached_payload = load_cached_tile_payload(
            cache_path,
            query_name=query_name,
            query_signature=query_signature,
            tile_path_label=tile_path_label,
        )
        if cached_payload is not None:
            tile_count += 1
            progress.mark_request_completed(tile_path_label)
            progress.mark_covered(tile_path_label, tile_area)
            payload = cached_payload
            log_event(
                "TILE_CACHED",
                query=query_name,
                depth=f"{current_depth}/{max_depth}",
                path=tile_path_label,
                tile=f"{tile_index}/{len(tile_contexts)}",
                grid=f"{rows}x{cols}",
                elements=str(len(payload.get("elements", []))),
                **progress.progress_fields(),
            )
        else:
            try:
                payload = fetch_overpass(
                    settings,
                    tile_query,
                    request_label=f"{query_name} depth={current_depth}/{max_depth} path={tile_path_label}",
                    progress=progress,
                )
                write_cached_tile_payload(
                    cache_path,
                    query_name=query_name,
                    query_signature=query_signature,
                    tile_path_label=tile_path_label,
                    payload=payload,
                )
                tile_count += 1
                progress.mark_request_completed(tile_path_label)
                progress.mark_covered(tile_path_label, tile_area)
                log_event(
                    "TILE_FETCHED",
                    query=query_name,
                    depth=f"{current_depth}/{max_depth}",
                    path=tile_path_label,
                    tile=f"{tile_index}/{len(tile_contexts)}",
                    grid=f"{rows}x{cols}",
                    elements=str(len(payload.get("elements", []))),
                    **progress.progress_fields(),
                )
            except OverpassFetchError as error:
                if not error.retryable or current_depth >= max_depth:
                    progress.mark_request_completed(tile_path_label)
                    log_event(
                        "TILE_FAILED",
                        query=query_name,
                        depth=f"{current_depth}/{max_depth}",
                        path=tile_path_label,
                        tile=f"{tile_index}/{len(tile_contexts)}",
                        grid=f"{rows}x{cols}",
                        error=str(error),
                        **progress.progress_fields(),
                    )
                    raise
                next_tile_grid = tile_grid_for_query(settings, query_name, current_depth=current_depth + 1)
                eligible_child_paths = child_tile_paths_for_context(
                    tile_context,
                    current_tile_path,
                    next_tile_grid,
                    tile_mask,
                )
                if not eligible_child_paths:
                    progress.mark_request_completed(tile_path_label)
                    log_event(
                        "TILE_FAILED",
                        query=query_name,
                        depth=f"{current_depth}/{max_depth}",
                        path=tile_path_label,
                        tile=f"{tile_index}/{len(tile_contexts)}",
                        grid=f"{rows}x{cols}",
                        error=f"{error} | subdivision produced no eligible child tiles",
                        **progress.progress_fields(),
                    )
                    raise
                progress.subdivide_tile(tile_path_label, eligible_child_paths)
                log_event(
                    "TILE_SUBDIVIDING",
                    query=query_name,
                    depth=f"{current_depth}/{max_depth}",
                    path=tile_path_label,
                    tile=f"{tile_index}/{len(tile_contexts)}",
                    grid=f"{rows}x{cols}",
                    next_grid=f"{next_tile_grid[0]}x{next_tile_grid[1]}",
                    error=str(error),
                    **progress.progress_fields(),
                )
                payload, nested_tile_count = fetch_tiled_payload(
                    settings,
                    template,
                    tile_context,
                    query_name=query_name,
                    progress=progress,
                    tile_mask=tile_mask,
                    tile_cache_dir=tile_cache_dir,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                    tile_grid=next_tile_grid,
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


def fetch_overpass(settings: dict, query: str, request_label: str = "query", progress: QueryProgress | None = None) -> dict:
    timeout = int(settings.get("overpassTimeoutSeconds", 180)) + 30
    retry_rounds_before_subdivision = int(
        settings.get("requestRetriesBeforeSubdivision", max(0, int(settings.get("maxRequestRetries", 3)) - 1))
    )
    total_attempts = retry_rounds_before_subdivision + 1
    backoff = float(settings.get("retryBackoffSeconds", 5.0))
    endpoints = settings.get("overpassUrls") or [settings["overpassUrl"]]

    for attempt in range(total_attempts):
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
                _ = error.read()
                retryable = error.code in {429, 502, 503, 504}
                last_error = OverpassFetchError(
                    summarize_http_error(endpoint, error.code),
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

        if last_error and attempt + 1 < total_attempts and last_error.retryable:
            log_event(
                "RETRY",
                request=request_label,
                attempt=f"{attempt + 2}/{total_attempts}",
                error=str(last_error),
                **(progress.progress_fields() if progress else {}),
            )
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


def initialize_query_progress(
    settings: dict,
    query_name: str,
    query_context: dict[str, str],
) -> tuple[QueryProgress, TileMask | None]:
    progress = QueryProgress(query_name=query_name)
    if not should_tile_first(settings, query_name):
        progress.register_tile("single")
        progress.total_area = 1.0
        return progress, None

    tile_mask = build_query_tile_mask(settings, query_name)
    initial_tile_grid = tile_grid_for_query(settings, query_name, current_depth=1)
    tile_contexts = split_bbox_context(query_context, initial_tile_grid)
    root_tile_area = tile_area_ratio(query_context, initial_tile_grid)
    for tile_index, tile_context in enumerate(tile_contexts, start=1):
        tile_path_label = str(tile_index)
        if tile_mask and not tile_mask.intersects_context(tile_context):
            continue
        progress.register_tile(tile_path_label)
        progress.total_area += root_tile_area
    if progress.total_area <= 0:
        progress.total_area = 1.0
    return progress, tile_mask


def tile_area_ratio(context: dict[str, str], tile_grid: tuple[int, int]) -> float:
    south = float(context["bbox_south"])
    west = float(context["bbox_west"])
    north = float(context["bbox_north"])
    east = float(context["bbox_east"])
    total_area = max((north - south) * (east - west), 0.0)
    rows, cols = tile_grid
    if rows <= 0 or cols <= 0:
        return 0.0
    return total_area / (rows * cols)


def child_tile_paths(tile_path: tuple[int, ...], tile_grid: tuple[int, int]) -> list[str]:
    rows, cols = tile_grid
    return [".".join(str(part) for part in (*tile_path, child_index)) for child_index in range(1, (rows * cols) + 1)]


def child_tile_paths_for_context(
    context: dict[str, str],
    tile_path: tuple[int, ...],
    tile_grid: tuple[int, int],
    tile_mask: TileMask | None,
) -> list[str]:
    child_contexts = split_bbox_context(context, tile_grid)
    eligible_paths: list[str] = []
    for child_index, child_context in enumerate(child_contexts, start=1):
        if tile_mask and not tile_mask.intersects_context(child_context):
            continue
        eligible_paths.append(".".join(str(part) for part in (*tile_path, child_index)))
    return eligible_paths


def build_query_tile_mask(settings: dict, query_name: str) -> TileMask | None:
    if query_name != "05-buildings-near-riverbanks":
        return None

    waterways_raw_path = DATA_SOURCE_DIR / "osm/raw/01-waterways.json"
    if not waterways_raw_path.exists():
        log_event(
            "MASK_UNAVAILABLE",
            query=query_name,
            reason="missing osm/raw/01-waterways.json; using full tile grid",
        )
        return None

    payload = json.loads(read_text(waterways_raw_path))
    expanded_bboxes = waterway_expanded_bboxes(
        payload.get("elements", []),
        float(settings["riverbankBuildingDistanceM"]),
        str(settings.get("riverCorridorNamePattern", "berkel")),
    )
    if not expanded_bboxes:
        log_event(
            "MASK_UNAVAILABLE",
            query=query_name,
            reason="could not derive waterway corridor from osm/raw/01-waterways.json; using full tile grid",
        )
        return None

    log_event(
        "MASK_READY",
        query=query_name,
        source="osm/raw/01-waterways.json",
        corridor_segments=str(len(expanded_bboxes)),
    )
    return TileMask(
        query_name=query_name,
        reason="outside_river_corridor",
        expanded_bboxes=expanded_bboxes,
    )


def waterway_expanded_bboxes(
    elements: list[dict],
    distance_m: float,
    river_name_pattern: str,
) -> list[tuple[float, float, float, float]]:
    river_name_regex = re.compile(river_name_pattern, re.IGNORECASE)
    node_coords = {
        int(element["id"]): (float(element["lat"]), float(element["lon"]))
        for element in elements
        if element.get("type") == "node" and "lat" in element and "lon" in element
    }
    bboxes: list[tuple[float, float, float, float]] = []
    for element in elements:
        if element.get("type") != "way":
            continue
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "")
        if not river_name_regex.search(name):
            continue
        node_ids = element.get("nodes", [])
        coordinates = [node_coords.get(int(node_id)) for node_id in node_ids]
        coordinates = [coordinate for coordinate in coordinates if coordinate is not None]
        if not coordinates:
            continue
        lats = [coordinate[0] for coordinate in coordinates]
        lons = [coordinate[1] for coordinate in coordinates]
        min_lat = min(lats)
        max_lat = max(lats)
        min_lon = min(lons)
        max_lon = max(lons)
        mid_lat = (min_lat + max_lat) / 2
        lat_margin = meters_to_lat_degrees(distance_m)
        lon_margin = meters_to_lon_degrees(distance_m, mid_lat)
        bboxes.append(
            (
                min_lat - lat_margin,
                min_lon - lon_margin,
                max_lat + lat_margin,
                max_lon + lon_margin,
            )
        )
    return bboxes


def meters_to_lat_degrees(distance_m: float) -> float:
    return distance_m / 111_320.0


def meters_to_lon_degrees(distance_m: float, latitude: float) -> float:
    cosine = math.cos(math.radians(latitude))
    if abs(cosine) < 1e-9:
        return 0.0
    return distance_m / (111_320.0 * cosine)


def context_bbox(context: dict[str, str]) -> tuple[float, float, float, float]:
    return (
        float(context["bbox_south"]),
        float(context["bbox_west"]),
        float(context["bbox_north"]),
        float(context["bbox_east"]),
    )


def bboxes_intersect(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    left_south, left_west, left_north, left_east = left
    right_south, right_west, right_north, right_east = right
    return not (
        left_east < right_west
        or right_east < left_west
        or left_north < right_south
        or right_north < left_south
    )


def log_event(event: str, **fields: str) -> None:
    timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    serialized_fields = " ".join(f"{key}={format_log_value(value)}" for key, value in fields.items())
    if serialized_fields:
        print(f"[{timestamp}] {event} {serialized_fields}")
    else:
        print(f"[{timestamp}] {event}")


def format_log_value(value: object) -> str:
    text = str(value)
    if any(character.isspace() for character in text):
        return json.dumps(text)
    return text


def summarize_http_error(endpoint: str, status_code: int) -> str:
    host = urllib.parse.urlparse(endpoint).netloc or endpoint
    explanations = {
        429: "rate limited",
        502: "bad gateway",
        503: "service unavailable",
        504: "gateway timeout",
    }
    explanation = explanations.get(status_code, "http error")
    return f"HTTP {status_code} {explanation} from {host}"


def tile_cache_file_path(tile_cache_dir, query_name: str, tile_path: tuple[int, ...]):
    query_cache_dir = tile_cache_dir / query_name
    ensure_directory(query_cache_dir)
    filename = f"{'.'.join(str(part) for part in tile_path)}.json"
    return query_cache_dir / filename


def query_signature_for_text(query: str) -> str:
    return hashlib.sha1(query.encode("utf-8")).hexdigest()


def load_cached_tile_payload(cache_path, query_name: str, query_signature: str, tile_path_label: str) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(read_text(cache_path))
    except (json.JSONDecodeError, OSError):
        return None
    if payload.get("query_name") != query_name:
        return None
    if payload.get("query_signature") != query_signature:
        return None
    if payload.get("tile_path") != tile_path_label:
        return None
    cached_payload = payload.get("payload")
    return cached_payload if isinstance(cached_payload, dict) else None


def write_cached_tile_payload(cache_path, query_name: str, query_signature: str, tile_path_label: str, payload: dict) -> None:
    write_json(
        cache_path,
        {
            "query_name": query_name,
            "query_signature": query_signature,
            "tile_path": tile_path_label,
            "payload": payload,
        },
        indent=None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
