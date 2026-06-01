"""Cross-platform export tools backed by kicad-cli."""

from __future__ import annotations

import csv
import re
import subprocess as _subprocess
import time as _time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from ..config import get_config
from ..discovery import get_cli_capabilities
from ..models.export import (
    ExportBOMInput,
    ExportGerberInput,
    ExportNetlistInput,
    ExportPdfInput,
    ExportRenderInput,
)
from .export_support import (
    _ensure_output_dir,
    _get_pcb_file,
    _get_sch_file,
    _run_cli,
    _run_cli_variants,
)
from .metadata import headless_compatible
from .variants import variant_apply_to_kicad_cli_args

# Public compatibility for tests and downstream monkeypatches.  These aliases
# point at Python's process/time modules, so monkeypatching
# kicad_mcp.tools.export.subprocess.run or .time.sleep still affects _run_cli's
# shared module objects.
subprocess = _subprocess
time = _time

DEFAULT_PCB_PDF_LAYERS = ["F.Cu", "Edge.Cuts"]
_WINDOWS_ANCHORED_PATH = re.compile(r"^(?:[a-zA-Z]:|//|\\\\)")
__all__ = [
    "_ensure_output_dir",
    "_get_pcb_file",
    "_get_sch_file",
    "_run_cli",
    "_run_cli_variants",
    "subprocess",
    "time",
]


def _safe_output_filename(raw_name: str, *, default_name: str) -> str:
    name = raw_name.strip() if raw_name else default_name
    if not name:
        raise ValueError("Output file names cannot be empty or whitespace only.")
    if "/" in name or "\\" in name:
        raise ValueError("Output file names cannot contain directory separators or traversal.")
    if _WINDOWS_ANCHORED_PATH.match(name):
        raise ValueError("Output file names must be relative to the export output directory.")
    candidate = Path(name).expanduser()
    if candidate.is_absolute() or candidate.anchor:
        raise ValueError("Output file names must be relative to the export output directory.")
    if len(candidate.parts) != 1 or candidate.name in {"", ".", ".."}:
        raise ValueError("Output file names cannot contain directory separators or traversal.")
    return candidate.name


def _resolve_output_file(subdir: str, raw_name: str, *, default_name: str) -> Path:
    return _ensure_output_dir(subdir) / _safe_output_filename(raw_name, default_name=default_name)


def _format_file_list(files: list[Path], heading: str) -> str:
    if not files:
        return f"{heading}\nNo files were produced."
    lines = [heading]
    lines.extend(f"- {file.name}" for file in files[:25])
    if len(files) > 25:
        lines.append(f"... and {len(files) - 25} more files")
    return "\n".join(lines)


def _read_preview(path: Path) -> str:
    cfg = get_config()
    content = path.read_text(encoding="utf-8", errors="ignore")
    if len(content) > cfg.max_text_response_chars:
        return f"{content[: cfg.max_text_response_chars]}\n... [truncated]"
    return content


LOW_LEVEL_EXPORT_NOTICE = (
    "Debug export only: this low-level export does not enforce project_quality_gate(). "
    "Use export_manufacturing_package() for a gated release handoff."
)


def _with_low_level_export_notice(message: str) -> str:
    return f"{LOW_LEVEL_EXPORT_NOTICE}\n\n{message}"


def _active_variant_args(variant_name: str | None = None) -> list[str]:
    try:
        args = variant_apply_to_kicad_cli_args(variant_name)
    except ValueError:
        if variant_name:
            raise
        return []
    if not args:
        return args
    # ``--variant`` was added to ``kicad-cli`` in KiCad 10.  Earlier CLIs (9.x
    # and below) reject it as ``Unknown argument`` and abort the export.  The
    # ``default`` variant is a synthetic no-op baseline that adds no overrides,
    # so suppress it unconditionally; for explicit non-default variants, gate
    # on the local CLI's advertised capability.
    if args == ["--variant", "default"]:
        return []
    try:
        caps = get_cli_capabilities(get_config().kicad_cli)
    except Exception:
        return args
    if not caps.supports_cli_variant:
        raise ValueError(
            f"The detected kicad-cli does not support --variant. "
            f"Cannot apply variant '{args[1]}'. Upgrade to KiCad 10+ "
            f"or run variant_set_active('default') to clear the override."
        )
    return args


async def _report_progress(
    ctx: Context[Any, Any, Any] | None,
    progress: float,
    total: float,
    message: str,
) -> None:
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress, total, message)
    except ValueError:
        return


def register(mcp: FastMCP, *, include_low_level_exports: bool = True) -> None:
    """Register export tools."""

    def _export_gerber(
        output_subdir: str = "gerber",
        layers: list[str] | None = None,
        variant_name: str | None = None,
    ) -> str:
        payload = ExportGerberInput(output_subdir=output_subdir, layers=layers or [])
        pcb_file = _get_pcb_file()
        try:
            out_dir = _ensure_output_dir(payload.output_subdir)
        except ValueError as exc:
            return f"Invalid output path: {exc}"
        caps = get_cli_capabilities(get_config().kicad_cli)

        layer_args = []
        if payload.layers:
            layer_args = ["--layers", ",".join(payload.layers)]
        variant_args = _active_variant_args(variant_name)

        gerber_commands = ["gerbers", "gerber"]
        if caps.gerber_command not in gerber_commands:
            gerber_commands.append(caps.gerber_command)
        variants: list[list[str]] = []
        for gerber_command in gerber_commands:
            variants.extend(
                [
                    [
                        "pcb",
                        "export",
                        gerber_command,
                        *variant_args,
                        "--output",
                        str(out_dir),
                        *layer_args,
                        str(pcb_file),
                    ],
                    [
                        "pcb",
                        "export",
                        gerber_command,
                        *variant_args,
                        "--input",
                        str(pcb_file),
                        "--output",
                        str(out_dir),
                        *layer_args,
                    ],
                ]
            )
        code, _, stderr = _run_cli_variants(variants)
        if code != 0:
            return f"Gerber export failed: {stderr or 'unknown error'}"

        files = sorted(out_dir.glob("*.gbr")) + sorted(out_dir.glob("*.g*"))
        return _format_file_list(files, f"Gerber export completed in {out_dir}:")

    @headless_compatible
    async def export_gerber(
        output_subdir: str = "gerber",
        layers: list[str] | None = None,
        ctx: Context[Any, Any, Any] | None = None,
    ) -> str:
        """Export Gerber manufacturing files."""
        await _report_progress(ctx, 5, 100, "Starting Gerber export...")
        result = _with_low_level_export_notice(_export_gerber(output_subdir, layers))
        await _report_progress(ctx, 100, 100, "Gerber export complete.")
        return result

    def _export_drill(output_subdir: str = "gerber", variant_name: str | None = None) -> str:
        pcb_file = _get_pcb_file()
        try:
            out_dir = _ensure_output_dir(output_subdir)
        except ValueError as exc:
            return f"Invalid output path: {exc}"
        caps = get_cli_capabilities(get_config().kicad_cli)
        variant_args = _active_variant_args(variant_name)
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    caps.drill_command,
                    *variant_args,
                    "--output",
                    str(out_dir),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    caps.drill_command,
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--output",
                    str(out_dir),
                ],
            ]
        )
        if code != 0:
            return f"Drill export failed: {stderr or 'unknown error'}"
        files = sorted(out_dir.glob("*.drl")) + sorted(out_dir.glob("*.xnc"))
        return _format_file_list(files, f"Drill export completed in {out_dir}:")

    @headless_compatible
    def export_drill(output_subdir: str = "gerber") -> str:
        """Export drill files."""
        return _with_low_level_export_notice(_export_drill(output_subdir))

    def _export_bom(format: str = "csv", variant_name: str | None = None) -> str:
        payload = ExportBOMInput(format=format)
        sch_file = _get_sch_file()
        out_dir = _ensure_output_dir()
        suffix = "csv" if payload.format == "csv" else "xml"
        out_file = out_dir / f"bom.{suffix}"
        if payload.format == "csv":
            try:
                from .library import _schematic_component_rows
                from .schematic import project_schematic_files

                schematic_files = project_schematic_files()
                if len(schematic_files) > 1:
                    rows = _schematic_component_rows()
                    with out_file.open("w", newline="", encoding="utf-8") as handle:
                        writer = csv.DictWriter(
                            handle,
                            fieldnames=["reference", "value", "footprint", "lib_id", "lcsc"],
                        )
                        writer.writeheader()
                        writer.writerows(rows)
                    return (
                        f"BOM exported to {out_file}\n"
                        f"Consolidated {len(rows)} reference(s) from "
                        f"{len(schematic_files)} schematic files.\n\n"
                        f"{_read_preview(out_file)}"
                    )
            except (OSError, ValueError, RuntimeError) as exc:
                return f"BOM export failed: {exc}"
        variant_args = _active_variant_args(variant_name)
        code, _, stderr = _run_cli_variants(
            [
                [
                    "sch",
                    "export",
                    "bom",
                    *variant_args,
                    "--output",
                    str(out_file),
                    "--format-preset",
                    "CSV",
                    str(sch_file),
                ],
                [
                    "sch",
                    "export",
                    "bom",
                    *variant_args,
                    "--input",
                    str(sch_file),
                    "--output",
                    str(out_file),
                    "--format-preset",
                    "CSV",
                ],
                ["sch", "export", "python-bom", "--output", str(out_file), str(sch_file)],
            ]
        )
        if code != 0 and not out_file.exists():
            return f"BOM export failed: {stderr or 'unknown error'}"
        return f"BOM exported to {out_file}\n\n{_read_preview(out_file)}"

    @headless_compatible
    def export_bom(format: str = "csv") -> str:
        """Export a bill of materials."""
        return _with_low_level_export_notice(_export_bom(format))

    def _export_netlist(format: str = "kicad") -> str:
        payload = ExportNetlistInput(format=format)
        sch_file = _get_sch_file()
        out_dir = _ensure_output_dir()
        extension_map = {"kicad": "net", "spice": "cir", "cadstar": "frp", "orcadpcb2": "net"}
        cli_format_map = {
            "kicad": "kicadsexpr",
            "spice": "spice",
            "cadstar": "cadstar",
            "orcadpcb2": "orcadpcb2",
        }
        out_file = out_dir / f"netlist.{extension_map[payload.format]}"
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "sch",
                    "export",
                    "netlist",
                    *variant_args,
                    "--format",
                    cli_format_map[payload.format],
                    "--output",
                    str(out_file),
                    str(sch_file),
                ],
            ]
        )
        if code != 0:
            return f"Netlist export failed: {stderr or 'unknown error'}"
        return f"Netlist exported to {out_file}"

    @headless_compatible
    def export_netlist(format: str = "kicad") -> str:
        """Export a KiCad schematic netlist."""
        return _with_low_level_export_notice(_export_netlist(format))

    @headless_compatible
    def export_spice_netlist() -> str:
        """Export a SPICE netlist."""
        return _with_low_level_export_notice(_export_netlist("spice"))

    def _export_pcb_pdf(layers: list[str] | None = None) -> str:
        payload = ExportPdfInput(layers=layers or [])
        pcb_file = _get_pcb_file()
        out_dir = _ensure_output_dir()
        out_file = out_dir / "board.pdf"
        layers_arg = ",".join(payload.layers or DEFAULT_PCB_PDF_LAYERS)
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "pdf",
                    *variant_args,
                    "--output",
                    str(out_file),
                    "--layers",
                    layers_arg,
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    "pdf",
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--output",
                    str(out_file),
                    "--layers",
                    layers_arg,
                ],
            ]
        )
        if code != 0:
            return f"PCB PDF export failed: {stderr or 'unknown error'}"
        return f"PCB PDF exported to {out_file}"

    @headless_compatible
    def export_pcb_pdf(layers: list[str] | None = None) -> str:
        """Export the PCB to PDF."""
        return _with_low_level_export_notice(_export_pcb_pdf(layers))

    def _export_sch_pdf() -> str:
        sch_file = _get_sch_file()
        out_dir = _ensure_output_dir()
        out_file = out_dir / "schematic.pdf"
        variant_args = _active_variant_args()
        code, stdout, stderr = _run_cli_variants(
            [
                ["sch", "export", "pdf", *variant_args, "--output", str(out_file), str(sch_file)],
                [
                    "sch",
                    "export",
                    "pdf",
                    *variant_args,
                    "--input",
                    str(sch_file),
                    "--output",
                    str(out_file),
                ],
            ]
        )
        if code != 0:
            return f"Schematic PDF export failed: {stderr or stdout or 'unknown error'}"
        return f"Schematic PDF exported to {out_file}"

    @headless_compatible
    def export_sch_pdf() -> str:
        """Export the schematic to PDF."""
        return _with_low_level_export_notice(_export_sch_pdf())

    def _export_3d_model(
        cli_command: str,
        output_path: str,
        *,
        supported: bool,
        default_name: str,
        label: str,
    ) -> str:
        pcb_file = _get_pcb_file()
        if not supported:
            return f"{label} export is not supported by the detected KiCad CLI."

        try:
            out_file = _resolve_output_file("3d", output_path, default_name=default_name)
        except ValueError as exc:
            return f"Invalid output path: {exc}"
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    cli_command,
                    *variant_args,
                    "--output",
                    str(out_file),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    cli_command,
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--output",
                    str(out_file),
                ],
            ]
        )
        if code != 0:
            return f"{label} export failed: {stderr or 'unknown error'}"
        return f"{label} model exported to {out_file}"

    def _export_step(output_path: str = "") -> str:
        caps = get_cli_capabilities(get_config().kicad_cli)
        return _export_3d_model(
            "step",
            output_path,
            supported=caps.supports_step,
            default_name="board.step",
            label="STEP",
        )

    def _export_stepz(output_path: str = "") -> str:
        caps = get_cli_capabilities(get_config().kicad_cli)
        return _export_3d_model(
            "stpz",
            output_path,
            supported=caps.supports_stepz,
            default_name="board.stepz",
            label="STEPZ",
        )

    def _export_xao(output_path: str = "") -> str:
        caps = get_cli_capabilities(get_config().kicad_cli)
        return _export_3d_model(
            "xao",
            output_path,
            supported=caps.supports_xao,
            default_name="board.xao",
            label="XAO",
        )

    @headless_compatible
    def export_3d_step() -> str:
        """Export a STEP model for the active board."""
        return _with_low_level_export_notice(_export_step(""))

    @headless_compatible
    def export_step(output_path: str = "") -> str:
        """Alias for STEP export with an optional explicit output path."""
        return _with_low_level_export_notice(_export_step(output_path))

    @headless_compatible
    def export_stepz(output_path: str = "") -> str:
        """Export a gzip-compressed STEPZ model using KiCad's stpz CLI command."""
        return _with_low_level_export_notice(_export_stepz(output_path))

    @headless_compatible
    def export_xao(output_path: str = "") -> str:
        """Export an XAO model for the active board using KiCad CLI."""
        return _with_low_level_export_notice(_export_xao(output_path))

    def _export_3d_pdf(output_path: str = "", board_only: bool = False) -> str:
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_3d_pdf:
            return (
                "3D PDF export requires CliCapabilities.supports_3d_pdf from a "
                "KiCad 10-compatible kicad-cli."
            )

        try:
            out_file = _resolve_output_file("3d", output_path, default_name="board-3d.pdf")
        except ValueError as exc:
            return f"Invalid output path: {exc}"

        extra_args = ["--board-only"] if board_only else []
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "3dpdf",
                    *variant_args,
                    "--output",
                    str(out_file),
                    *extra_args,
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    "3dpdf",
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--output",
                    str(out_file),
                    *extra_args,
                ],
            ]
        )
        if code != 0:
            return f"3D PDF export failed: {stderr or 'unknown error'}"
        return f"3D PDF exported to {out_file}"

    @headless_compatible
    def pcb_export_3d_pdf(output_path: str = "", board_only: bool = False) -> str:
        """Export the active PCB as a KiCad 10 3D PDF."""
        return _with_low_level_export_notice(_export_3d_pdf(output_path, board_only))

    def _export_3d_render(
        output_file: str = "render.png",
        side: str = "top",
        zoom: float = 1.0,
    ) -> str:
        payload = ExportRenderInput(output_file=output_file, side=side, zoom=zoom)
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_render:
            return "3D rendering is not supported by the detected KiCad CLI."

        try:
            out_file = _resolve_output_file("3d", payload.output_file, default_name="render.png")
        except ValueError as exc:
            return f"Invalid output path: {exc}"
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "render",
                    "--side",
                    payload.side,
                    "--zoom",
                    str(payload.zoom),
                    "--output",
                    str(out_file),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "render",
                    "--input",
                    str(pcb_file),
                    "--side",
                    payload.side,
                    "--zoom",
                    str(payload.zoom),
                    "--output",
                    str(out_file),
                ],
            ]
        )
        if code != 0:
            return f"3D render failed: {stderr or 'unknown error'}"
        return f"Rendered board image exported to {out_file}"

    @headless_compatible
    def export_3d_render(
        output_file: str = "render.png",
        side: str = "top",
        zoom: float = 1.0,
    ) -> str:
        """Render the board to a PNG image."""
        return _with_low_level_export_notice(_export_3d_render(output_file, side, zoom))

    def _export_pick_and_place(format: str = "csv", variant_name: str | None = None) -> str:
        pcb_file = _get_pcb_file()
        out_dir = _ensure_output_dir("assembly")
        out_file = out_dir / f"pick_and_place.{format}"
        caps = get_cli_capabilities(get_config().kicad_cli)
        variant_args = _active_variant_args(variant_name)
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    caps.position_command,
                    *variant_args,
                    "--format",
                    format,
                    "--output",
                    str(out_file),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    caps.position_command,
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--format",
                    format,
                    "--output",
                    str(out_file),
                ],
                ["pcb", "export", "pos", *variant_args, "--output", str(out_file), str(pcb_file)],
            ]
        )
        if code != 0:
            return f"Pick and place export failed: {stderr or 'unknown error'}"
        return f"Pick and place data exported to {out_file}"

    @headless_compatible
    def export_pick_and_place(format: str = "csv") -> str:
        """Export assembly position data."""
        return _with_low_level_export_notice(_export_pick_and_place(format))

    def _export_ipc2581(variant_name: str | None = None) -> str:
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_ipc2581:
            return "IPC-2581 export is not supported by the detected KiCad CLI."

        out_file = _ensure_output_dir("manufacturing") / "board.xml"
        variant_args = _active_variant_args(variant_name)
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "ipc2581",
                    *variant_args,
                    "--output",
                    str(out_file),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    "ipc2581",
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--output",
                    str(out_file),
                ],
            ]
        )
        if code != 0:
            return f"IPC-2581 export failed: {stderr or 'unknown error'}"
        return f"IPC-2581 exported to {out_file}"

    @headless_compatible
    def export_ipc2581() -> str:
        """Export IPC-2581 manufacturing data."""
        return _with_low_level_export_notice(_export_ipc2581())

    def _export_odb(variant_name: str | None = None) -> str:
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_odb_export:
            return "ODB++ export is not supported by the detected KiCad CLI."

        out_file = _ensure_output_dir("manufacturing") / "board.odb.zip"
        variant_args = _active_variant_args(variant_name)
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "odb",
                    *variant_args,
                    "--compression",
                    "zip",
                    "--output",
                    str(out_file),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    "odb",
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--compression",
                    "zip",
                    "--output",
                    str(out_file),
                ],
            ]
        )
        if code != 0:
            return f"ODB++ export failed: {stderr or 'unknown error'}"
        return f"ODB++ exported to {out_file}"

    @headless_compatible
    def export_odb() -> str:
        """Export an ODB++ manufacturing package when supported by KiCad 10+."""
        return _with_low_level_export_notice(_export_odb())

    def _export_svg(layer: str = "F.Cu") -> str:
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_svg:
            return "SVG export is not supported by the detected KiCad CLI."

        out_dir = _ensure_output_dir("svg")
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "svg",
                    *variant_args,
                    "--mode-multi",
                    "--layers",
                    layer,
                    "--output",
                    str(out_dir),
                    str(pcb_file),
                ],
            ]
        )
        if code != 0:
            return f"SVG export failed: {stderr or 'unknown error'}"
        files = sorted(out_dir.glob("*.svg"))
        return _format_file_list(files, f"SVG export completed in {out_dir}:")

    @headless_compatible
    def export_svg(layer: str = "F.Cu") -> str:
        """Export a board layer to SVG when supported."""
        return _with_low_level_export_notice(_export_svg(layer))

    def _export_dxf(layer: str = "Edge.Cuts") -> str:
        pcb_file = _get_pcb_file()
        caps = get_cli_capabilities(get_config().kicad_cli)
        if not caps.supports_dxf:
            return "DXF export is not supported by the detected KiCad CLI."

        out_dir = _ensure_output_dir("dxf")
        variant_args = _active_variant_args()
        code, _, stderr = _run_cli_variants(
            [
                [
                    "pcb",
                    "export",
                    "dxf",
                    *variant_args,
                    "--layers",
                    layer,
                    "--output",
                    str(out_dir),
                    str(pcb_file),
                ],
                [
                    "pcb",
                    "export",
                    "dxf",
                    *variant_args,
                    "--input",
                    str(pcb_file),
                    "--layers",
                    layer,
                    "--output",
                    str(out_dir),
                ],
            ]
        )
        if code != 0:
            return f"DXF export failed: {stderr or 'unknown error'}"
        files = sorted(out_dir.glob("*.dxf"))
        return _format_file_list(files, f"DXF export completed in {out_dir}:")

    @headless_compatible
    def export_dxf(layer: str = "Edge.Cuts") -> str:
        """Export a board layer to DXF when supported."""
        return _with_low_level_export_notice(_export_dxf(layer))

    @headless_compatible
    def get_board_stats() -> str:
        """Export board statistics and return a readable preview."""
        pcb_file = _get_pcb_file()
        out_file = _ensure_output_dir() / "board_stats.txt"
        code, stdout, stderr = _run_cli_variants(
            [
                ["pcb", "export", "stats", "--output", str(out_file), str(pcb_file)],
                ["pcb", "export", "stats", "--input", str(pcb_file), "--output", str(out_file)],
            ]
        )
        if out_file.exists():
            return _read_preview(out_file)
        if code != 0:
            return f"Board stats export failed: {stderr or 'unknown error'}"
        return stdout or "Board statistics were generated without a text report."

    @headless_compatible
    async def export_manufacturing_package(
        variant: str = "",
        ctx: Context[Any, Any, Any] | None = None,
    ) -> str:
        """Generate the standard set of manufacturing exports."""
        from .validation import _evaluate_project_gate, _render_project_gate_report

        variant_name = variant.strip() or None
        await _report_progress(ctx, 5, 100, "Running full project quality gate...")
        outcomes = _evaluate_project_gate()
        blocking = [outcome for outcome in outcomes if outcome.status != "PASS"]
        if blocking:
            return _render_project_gate_report(
                blocking,
                summary=(
                    "- Manufacturing package export is hard-blocked until the full "
                    "project quality gate passes."
                ),
            )

        await _report_progress(ctx, 25, 100, "Exporting Gerbers...")
        results = [
            _export_gerber(variant_name=variant_name),
        ]
        await _report_progress(ctx, 45, 100, "Exporting drill files...")
        results.extend([_export_drill(variant_name=variant_name)])
        await _report_progress(ctx, 65, 100, "Exporting BOM...")
        results.extend(
            [
                _export_bom(variant_name=variant_name),
            ]
        )
        await _report_progress(ctx, 85, 100, "Exporting pick-and-place data...")
        results.extend(
            [
                _export_pick_and_place(variant_name=variant_name),
            ]
        )
        ipc_result = _export_ipc2581(variant_name=variant_name)
        if not ipc_result.startswith("IPC-2581 export is not supported"):
            results.append(ipc_result)
        odb_result = _export_odb(variant_name=variant_name)
        if not odb_result.startswith("ODB++ export is not supported"):
            results.append(odb_result)
        await _report_progress(ctx, 100, 100, "Manufacturing package complete.")
        return "\n\n".join(results)

    if include_low_level_exports:
        mcp.tool()(export_gerber)
        mcp.tool()(export_drill)
        mcp.tool()(export_bom)
        mcp.tool()(export_netlist)
        mcp.tool()(export_spice_netlist)
        mcp.tool()(export_pcb_pdf)
        mcp.tool()(export_sch_pdf)
        mcp.tool()(export_3d_step)
        mcp.tool()(export_step)
        mcp.tool()(export_stepz)
        mcp.tool()(export_xao)
        mcp.tool()(pcb_export_3d_pdf)
        mcp.tool()(export_3d_render)
        mcp.tool()(export_pick_and_place)
        mcp.tool()(export_ipc2581)
        mcp.tool()(export_odb)
        mcp.tool()(export_svg)
        mcp.tool()(export_dxf)

    mcp.tool()(get_board_stats)
    mcp.tool()(export_manufacturing_package)
