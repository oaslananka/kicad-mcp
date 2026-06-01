from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "docs" / "assets" / "icon.svg"
ASSET_DIR = ROOT / "docs" / "assets"
SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)


def _scaled_points(points: tuple[tuple[int, int], ...], scale: float) -> list[tuple[int, int]]:
    return [(round(x * scale), round(y * scale)) for x, y in points]


def _draw_polyline(
    draw: ImageDraw.ImageDraw,
    points: tuple[tuple[int, int], ...],
    scale: float,
    *,
    fill: str,
    width: int,
) -> None:
    draw.line(
        _scaled_points(points, scale),
        fill=fill,
        width=max(1, round(width * scale)),
        joint="curve",
    )


def _fallback_render(size: int) -> bytes:
    scale = size / 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=round(96 * scale),
        fill="#1a1a2e",
    )

    grid_width = max(1, round(scale))
    for coord in range(64, 512, 64):
        x = round(coord * scale)
        draw.line((x, 0, x, size), fill="#16213e", width=grid_width)
        draw.line((0, x, size, x), fill="#16213e", width=grid_width)

    for points in (
        ((64, 192), (192, 192), (192, 128), (320, 128), (320, 192), (448, 192)),
        ((64, 320), (160, 320), (160, 384), (352, 384), (352, 320), (448, 320)),
        ((192, 192), (192, 320)),
        ((320, 192), (320, 320)),
        ((128, 256), (384, 256)),
    ):
        _draw_polyline(draw, points, scale, fill="#00b894", width=8)

    for x, y, radius in (
        (192, 192, 16),
        (320, 192, 16),
        (192, 320, 16),
        (320, 320, 16),
        (256, 256, 20),
    ):
        cx = round(x * scale)
        cy = round(y * scale)
        r = round(radius * scale)
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill="#00cec9",
            outline="#dfe6e9",
            width=max(1, round(4 * scale)),
        )

    draw.rounded_rectangle(
        tuple(round(v * scale) for v in (208, 208, 304, 304)),
        radius=round(8 * scale),
        fill="#0984e3",
        outline="#74b9ff",
        width=max(1, round(3 * scale)),
    )

    pin_rects = (
        [(196, y, 208, y + 8) for y in (220, 236, 252, 268)]
        + [(304, y, 316, y + 8) for y in (220, 236, 252, 268)]
        + [(x, 196, x + 8, 208) for x in (220, 236, 252, 268)]
        + [(x, 304, x + 8, 316) for x in (220, 236, 252, 268)]
    )
    for rect in pin_rects:
        draw.rounded_rectangle(
            tuple(round(v * scale) for v in rect),
            radius=max(1, round(2 * scale)),
            fill="#dfe6e9",
        )

    if size >= 48:
        font_size = max(8, round(20 * scale))
        try:
            font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        draw.text(
            (round(256 * scale), round(256 * scale)),
            "MCP",
            fill="white",
            anchor="mm",
            font=font,
        )

    for x, y in ((80, 80), (432, 80), (80, 432), (432, 432)):
        cx = round(x * scale)
        cy = round(y * scale)
        r = round(12 * scale)
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            outline="#636e72",
            width=max(1, round(4 * scale)),
        )

    output = BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


def _normalize_png(png_data: bytes) -> bytes:
    with Image.open(BytesIO(png_data)) as image:
        normalized = image.convert("RGBA")
        output = BytesIO()
        normalized.save(output, format="PNG", compress_level=9)
        return output.getvalue()


def _render_png(size: int) -> bytes:
    try:
        import cairosvg
    except (ImportError, OSError):
        return _fallback_render(size)

    try:
        rendered = cairosvg.svg2png(
            url=str(SVG_PATH),
            output_width=size,
            output_height=size,
        )
        if rendered is None:
            msg = f"failed to render {SVG_PATH}"
            raise RuntimeError(msg)
        return _normalize_png(rendered)
    except OSError:
        return _fallback_render(size)


def main() -> int:
    if not SVG_PATH.is_file():
        print(f"missing SVG: {SVG_PATH}")
        return 1

    for size in SIZES:
        data = _render_png(size)
        target = ASSET_DIR / f"icon-{size}.png"
        target.write_bytes(data)
        print(f"wrote {target.relative_to(ROOT)} ({size}x{size})")

        if size == 512:
            default_target = ASSET_DIR / "icon.png"
            default_target.write_bytes(data)
            print(f"wrote {default_target.relative_to(ROOT)} ({size}x{size})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
