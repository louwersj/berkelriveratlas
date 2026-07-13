from __future__ import annotations

from common import APP_DIR, now_iso, write_json


def main() -> int:
    write_json(
        APP_DIR / "data/manifest.json",
        {
            "generated_at": now_iso(),
            "data_base_url": "data",
            "github_raw_base_url": "https://raw.githubusercontent.com/louwersj/berkelriveratlas/main/app/data",
            "prefer_local_data": True,
            "config": [
                "config/site.json",
                "config/navigation.json",
                "config/layers.json",
                "config/languages.json",
                "config/theme.json",
                "config/feature-flags.json",
            ],
            "indexes": {
                "mapObjects": "data/index/map.objects.geojson",
                "timeline": "data/index/timeline.index.json",
                "graphNodes": "data/graph/nodes.json",
                "graphEdges": "data/graph/edges.json",
                "searchEn": "data/search/search.en.json",
                "searchDe": "data/search/search.de.json",
                "searchNl": "data/search/search.nl.json",
            },
        },
    )
    print("Built data manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

