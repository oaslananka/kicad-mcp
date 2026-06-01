from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
SCREENSHOT_DIR = ASSET_DIR / "screenshots"
ICON_PATH = ASSET_DIR / "icon-256.png"
HASH_PATH = ROOT / "scripts" / "_placeholder_hashes.json"
SIZE = (1920, 1080)
BACKGROUND = "#1a1a2e"

SLOTS = [
    (
        "01-claude-desktop-quality-gate.png",
        "Claude Desktop Quality Gate",
        "Claude Desktop running project_quality_gate",
    ),
    (
        "02-cursor-schematic-build.png",
        "Cursor Schematic Build",
        "Cursor building a schematic via sch_build_circuit",
    ),
    (
        "03-vscode-pcb-inspection.png",
        "VS Code PCB Inspection",
        "VS Code inspecting PCB state",
    ),
    (
        "04-tools-reference.png",
        "Tools Reference",
        "Tools reference catalog",
    ),
    (
        "05-export-manufacturing.png",
        "Manufacturing Export",
        "Gated manufacturing export",
    ),
]


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    draw.text(((SIZE[0] - width) // 2, y), text, fill=fill, font=font)


def _render(filename: str, title: str, caption: str, icon: Image.Image) -> Path:
    image = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)

    icon_position = ((SIZE[0] - icon.width) // 2, 216)
    image.paste(icon, icon_position, icon)

    _centered_text(draw, title, 540, _font(76, bold=True), "white")
    _centered_text(draw, caption, 650, _font(36), "#dfe6e9")

    # Subtle circuit rails keep these visibly tied to KiCad/PCB workflows.
    rail = "#00b894"
    pad = "#00cec9"
    draw.line((420, 820, 1500, 820), fill=rail, width=8)
    draw.line((620, 760, 620, 880), fill=rail, width=8)
    draw.line((1300, 760, 1300, 880), fill=rail, width=8)
    for x in (420, 620, 960, 1300, 1500):
        draw.ellipse((x - 18, 802, x + 18, 838), fill=pad, outline="white", width=3)

    target = SCREENSHOT_DIR / filename
    image.save(target, format="PNG", compress_level=9)
    return target


def main() -> int:
    if not ICON_PATH.is_file():
        print(f"missing icon asset: {ICON_PATH.relative_to(ROOT)}")
        return 1

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(ICON_PATH) as icon_source:
        icon = icon_source.convert("RGBA")

    hashes: dict[str, str] = {}
    for filename, title, caption in SLOTS:
        target = _render(filename, title, caption, icon)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        hashes[filename] = digest
        print(f"wrote {target.relative_to(ROOT)} sha256:{digest}")

    HASH_PATH.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {HASH_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
