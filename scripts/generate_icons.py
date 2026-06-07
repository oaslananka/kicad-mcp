"""Generate tray and Tauri icon PNGs from a source SVG.

Usage:
    python scripts/generate_icons.py --source assets/icon.svg
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _render_svg(source: Path, output: Path, size: int) -> None:
    """Render ``source`` to ``output`` using CairoSVG."""
    try:
        import cairosvg
    except ImportError as exc:  # pragma: no cover - developer environment guard
        raise SystemExit("cairosvg is required: uv sync --extra dev") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        url=str(source),
        write_to=str(output),
        output_width=size,
        output_height=size,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Source SVG file.")
    args = parser.parse_args()

    source = args.source
    if not source.exists():
        raise SystemExit(f"Source SVG not found: {source}")

    tray_dir = Path("src/kicad_mcp/tray_assets")
    tauri_dir = Path("src-tauri/icons")
    for size in (16, 32, 64, 128, 256, 512):
        _render_svg(source, tray_dir / f"icon_{size}.png", size)

    for size, name in ((32, "32x32.png"), (128, "128x128.png"), (256, "128x128@2x.png")):
        _render_svg(source, tauri_dir / name, size)

    print(f"Generated icons from {source}")


if __name__ == "__main__":
    main()
