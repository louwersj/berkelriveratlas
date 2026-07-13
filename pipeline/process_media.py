from __future__ import annotations

from common import APP_DIR


def main() -> int:
    expected = [
        APP_DIR / "media/images/image-borculo-mill-001.svg",
        APP_DIR / "media/maps/map-berkel-1843-001.svg",
    ]
    missing = [path for path in expected if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing media file: {path}")
        return 1
    print("Validated sample media files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

