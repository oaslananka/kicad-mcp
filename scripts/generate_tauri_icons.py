"""Generate placeholder icon files for the Tauri v2 scaffold.

Run from the repository root (once) to create valid PNG, ICO, and ICNS icons
so that ``cargo build`` does not fail on missing assets.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parent.parent / "src-tauri" / "icons"


def _create_rgba_png(width: int, height: int) -> bytes:
    """Create a solid-colour RGBA PNG (KiCad MCP Pro accent blue #1a73e8)."""
    header = b"\x89PNG\r\n\x1a\n"

    def chunk(typ: bytes, data: bytes) -> bytes:
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter: none
        raw.extend(b"\x1a\x73\xe8\xff" * width)  # RGBA

    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def _png_to_ico(png_data: bytes, width: int, height: int) -> bytes:
    """Wrap a single PNG into a minimal ICO container."""
    size = len(png_data)
    entry = struct.pack(
        "<BBBBHHII",
        width if width < 256 else 0,
        height if height < 256 else 0,
        0,  # colour palette
        0,  # reserved
        1,  # colour planes
        32,  # bits per pixel
        size,
        22,  # offset (6 header + 16 entry)
    )
    return struct.pack("<HHH", 0, 1, 1) + entry + png_data


def _png_to_icns(png_16: bytes, png_32: bytes, png_128: bytes) -> bytes:
    """Wrap multiple PNGs into a minimal ICNS container."""
    icon_types = [
        (b"ic07", png_128),  # 128x128
        (b"ic05", png_32),  # 32x32
        (b"ic04", png_16),  # 16x16
    ]
    entries = b""
    for ostype, data in icon_types:
        entry_size = 8 + len(data)
        entries += struct.pack(">4sI", ostype, entry_size) + data

    total = 8 + len(entries)
    return struct.pack(">4sI", b"icns", total) + entries


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    png_16 = _create_rgba_png(16, 16)
    png_32 = _create_rgba_png(32, 32)
    png_128 = _create_rgba_png(128, 128)
    png_256 = _create_rgba_png(256, 256)

    (ICONS_DIR / "32x32.png").write_bytes(png_32)
    (ICONS_DIR / "128x128.png").write_bytes(png_128)
    (ICONS_DIR / "128x128@2x.png").write_bytes(png_256)

    # ICO — uses 32x32 PNG
    (ICONS_DIR / "icon.ico").write_bytes(_png_to_ico(png_32, 32, 32))

    # ICNS — uses 16, 32, 128 PNGs
    (ICONS_DIR / "icon.icns").write_bytes(_png_to_icns(png_16, png_32, png_128))

    print(f"✅ Icons generated in {ICONS_DIR}")
    for f in sorted(ICONS_DIR.iterdir()):
        print(f"   {f.name:25s} {f.stat().st_size:>6} B")


if __name__ == "__main__":
    main()
