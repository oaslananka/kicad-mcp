from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAST_PATH = ROOT / "docs" / "assets" / "demo.cast"
GIF_PATH = ROOT / "docs" / "assets" / "demo.gif"


def _frames() -> list[tuple[float, str]]:
    return [
        (0.0, "$ kicad-mcp-pro health --json\r\n"),
        (
            0.8,
            json.dumps(
                {
                    "status": "ok",
                    "version": "3.4.3",
                    "transport": "stdio",
                    "subsystems": {
                        "config": "ready",
                        "kicad_cli": "ready",
                        "project": "deferred",
                        "ipc": "deferred",
                    },
                    "workspace": "<redacted>",
                },
                indent=2,
            )
            + "\r\n",
        ),
        (7.4, "\r\n"),
        (8.0, "$ kicad-mcp-pro doctor --json\r\n"),
        (
            8.9,
            json.dumps(
                {
                    "status": "ok",
                    "checks": [
                        {"name": "python", "result": "pass"},
                        {"name": "kicad-cli", "result": "pass", "version": "10.0.2"},
                        {"name": "workspace-root", "result": "pass"},
                        {"name": "profile", "result": "pass", "value": "agent_full"},
                    ],
                    "secrets": {"auth_token": "configured: false"},
                },
                indent=2,
            )
            + "\r\n",
        ),
        (18.0, "\r\n"),
        (19.0, "$ kicad-mcp-pro serve\r\n"),
        (
            19.8,
            "KiCad MCP Pro 3.4.3\r\n"
            "MCP transport: stdio\r\n"
            "Project tools: ready\r\n"
            "Validation gates: ready\r\n"
            "Manufacturing export: gated by project_quality_gate\r\n"
            "Waiting for MCP client messages...\r\n",
        ),
        (28.0, "\u2588"),
        (28.5, "\b "),
        (29.0, "\u2588"),
        (29.5, "\b "),
        (30.0, ""),
    ]


def write_cast(path: Path = CAST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "version": 2,
        "width": 100,
        "height": 30,
        "title": "KiCad MCP Pro \u2014 Quick Start",
    }
    lines = [json.dumps(header, separators=(",", ":"))]
    lines.extend(
        json.dumps([timestamp, "o", output], separators=(",", ":"))
        for timestamp, output in _frames()
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert_if_available() -> int:
    agg = shutil.which("agg")
    if agg is None:
        write_fallback_gif()
        print("agg not found; wrote deterministic fallback docs/assets/demo.gif.")
        print(
            "Replace with a rendered terminal capture when available: "
            "agg --speed 1.2 --theme monokai --font-size 18 "
            "docs/assets/demo.cast docs/assets/demo.gif"
        )
        return 0

    command = [
        agg,
        "--speed",
        "1.2",
        "--theme",
        "monokai",
        "--font-size",
        "18",
        str(CAST_PATH),
        str(GIF_PATH),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        return result.returncode

    if GIF_PATH.stat().st_size > 2 * 1024 * 1024:
        print("demo.gif exceeded 2 MB; retrying with --font-size 14")
        retry = command.copy()
        retry[retry.index("18")] = "14"
        result = subprocess.run(retry, check=False)
        if result.returncode != 0:
            return result.returncode

    print(f"wrote {GIF_PATH.relative_to(ROOT)}")
    return 0


def write_fallback_gif(path: Path = GIF_PATH) -> None:
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    width, height = 960, 540
    background = "#1a1a2e"
    terminal = "#0f172a"
    accent = "#00b894"
    text_color = "#e5e7eb"
    muted = "#94a3b8"
    snapshots = [
        [
            "$ kicad-mcp-pro health --json",
            '{ "status": "ok", "version": "3.4.3" }',
            '{ "transport": "stdio", "kicad_cli": "ready" }',
        ],
        [
            "$ kicad-mcp-pro doctor --json",
            '{ "checks": ["python", "kicad-cli", "workspace-root"] }',
            '{ "result": "pass", "profile": "agent_full" }',
        ],
        [
            "$ kicad-mcp-pro serve",
            "KiCad MCP Pro 3.4.3",
            "MCP transport: stdio",
            "Manufacturing export: gated by project_quality_gate",
        ],
    ]
    frames: list[Image.Image] = []
    for index, lines in enumerate(snapshots, 1):
        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((64, 64, width - 64, height - 64), radius=18, fill=terminal)
        draw.rectangle((64, 64, width - 64, 118), fill="#111827")
        draw.ellipse((88, 83, 102, 97), fill="#ef4444")
        draw.ellipse((114, 83, 128, 97), fill="#f59e0b")
        draw.ellipse((140, 83, 154, 97), fill=accent)
        draw.text((184, 84), "KiCad MCP Pro - Quick Start", fill=text_color, font=font)
        draw.text((width - 176, 84), f"step {index}/3", fill=muted, font=font)
        y = 156
        for line in lines:
            color = accent if line.startswith("$") else text_color
            draw.text((104, y), line, fill=color, font=font)
            y += 42
        draw.text(
            (104, height - 118), "local stdio MCP server - no telemetry", fill=muted, font=font
        )
        frames.extend([image] * 4)

    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=420,
        loop=0,
        optimize=True,
    )
    print(f"wrote {path.relative_to(ROOT)}")


def playback() -> int:
    for _, output in _frames():
        sys.stdout.write(output)
        sys.stdout.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic demo media inputs.")
    parser.add_argument("--convert-if-available", action="store_true")
    parser.add_argument("--playback", action="store_true")
    args = parser.parse_args()

    if args.playback:
        return playback()

    write_cast()
    print(f"wrote {CAST_PATH.relative_to(ROOT)}")
    if args.convert_if_available:
        return convert_if_available()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
