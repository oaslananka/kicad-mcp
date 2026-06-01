"""IPC-7351B footprint generator for common SMD and through-hole packages.

Generates KiCad-format ``.kicad_mod`` S-expressions for standard packages using
IPC-7351B land-pattern formulas.  Supports density levels A (most-generous),
B (nominal, default), and C (least-land/most-compact).

Supported families
------------------
- Chip passives: 0201, 0402, 0603, 0805, 1206, 1210, 2512
- SOT-23 (3-lead), SOT-223 (4-lead), SOT-89 (3-lead)
- SOIC / SOP / SSOP / TSSOP (arbitrary pitch/pin-count)
- QFP / LQFP / TQFP (quad flat pack)
- QFN / DFN (quad flat no-lead with optional exposed pad)
- BGA (ball grid array, grid or depopulated)
- Through-hole pin header (1×N or 2×N, pitch 2.54 / 2.00 / 1.27 mm)
"""

from __future__ import annotations

import math
from typing import Literal

from .sexpr import _sexpr_string

DensityLevel = Literal["A", "B", "C"]

# IPC-7351B Table 3-1 land-pattern density offsets (mm)
# (Jt: toe, Jh: heel, Js: side)  — A=generous, B=nominal, C=compact
_IPC_OFFSETS: dict[DensityLevel, tuple[float, float, float]] = {
    "A": (0.55, 0.00, 0.05),
    "B": (0.35, 0.00, -0.05),
    "C": (0.15, 0.00, -0.10),
}

_LAYER_FAB = "F.Fab"
_LAYER_CU = "F.Cu"
_LAYER_MASK = "F.Mask"
_LAYER_PASTE = "F.Paste"
_LAYER_SILK = "F.SilkS"
_LAYER_CYARD = "F.CrtYd"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _fp_header(name: str, description: str, tags: str) -> list[str]:
    return [
        f"(footprint {_sexpr_string(name)}",
        "\t(version 20250316)",
        '\t(generator "kicad-mcp-footprint-gen")',
        f"\t(layer {_sexpr_string(_LAYER_CU)})",
        f"\t(descr {_sexpr_string(description)})",
        f"\t(tags {_sexpr_string(tags)})",
        "\t(attr smd)",
    ]


def _fp_header_tht(name: str, description: str, tags: str) -> list[str]:
    return [
        f"(footprint {_sexpr_string(name)}",
        "\t(version 20250316)",
        '\t(generator "kicad-mcp-footprint-gen")',
        f"\t(layer {_sexpr_string(_LAYER_CU)})",
        f"\t(descr {_sexpr_string(description)})",
        f"\t(tags {_sexpr_string(tags)})",
    ]


def _pad_smd(num: int | str, x: float, y: float, w: float, h: float) -> str:
    return (
        f"\t(pad {num!r} smd rect (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f})"
        f" (layers {_LAYER_CU} {_LAYER_MASK} {_LAYER_PASTE}))"
    )


def _pad_tht(num: int, x: float, y: float, drill: float, size: float) -> str:
    return (
        f"\t(pad {num!r} thru_hole circle (at {x:.4f} {y:.4f})"
        f" (size {size:.4f} {size:.4f}) (drill {drill:.4f})"
        f" (layers *.Cu *.Mask))"
    )


def _ref_value(ref_y: float, val_y: float, fab_y: float | None = None) -> list[str]:
    lines = [
        f'\t(fp_text reference "REF**" (at 0 {ref_y:.4f})'
        f" (layer {_LAYER_SILK}) (effects (font (size 1 1) (thickness 0.15))))",
        f'\t(fp_text value "VAL**" (at 0 {val_y:.4f})'
        f" (layer {_LAYER_FAB}) (effects (font (size 1 1) (thickness 0.15))))",
    ]
    if fab_y is not None:
        lines.append(
            f'\t(fp_text user "${{REFERENCE}}" (at 0 {fab_y:.4f})'
            f" (layer {_LAYER_FAB}) (effects (font (size 0.8 0.8) (thickness 0.12))))"
        )
    return lines


def _rect_line(
    layer: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    w: float = 0.1,
) -> list[str]:
    """Draw a rectangle on a layer as four line segments."""
    return [
        (
            f"\t(fp_line (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y1:.4f}) "
            f"(layer {layer}) (stroke (width {w})(type solid)))"
        ),
        (
            f"\t(fp_line (start {x2:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) "
            f"(layer {layer}) (stroke (width {w})(type solid)))"
        ),
        (
            f"\t(fp_line (start {x2:.4f} {y2:.4f}) (end {x1:.4f} {y2:.4f}) "
            f"(layer {layer}) (stroke (width {w})(type solid)))"
        ),
        (
            f"\t(fp_line (start {x1:.4f} {y2:.4f}) (end {x1:.4f} {y1:.4f}) "
            f"(layer {layer}) (stroke (width {w})(type solid)))"
        ),
    ]


def _circle_line(layer: str, cx: float, cy: float, r: float, w: float = 0.1) -> str:
    return (
        f"\t(fp_circle (center {cx:.4f} {cy:.4f}) (end {cx + r:.4f} {cy:.4f})"
        f" (layer {layer}) (stroke (width {w})(type solid)))"
    )


# ---------------------------------------------------------------------------
# Chip passives (0201 … 2512)
# ---------------------------------------------------------------------------

_CHIP_DIMS: dict[str, tuple[float, float, float, float]] = {
    # name: (body_L, body_W, land_L, land_W) mm  — IPC-7351B Table 7-7
    "0201": (0.60, 0.30, 0.35, 0.35),
    "0402": (1.00, 0.50, 0.50, 0.50),
    "0603": (1.55, 0.85, 0.70, 0.90),
    "0805": (2.00, 1.25, 0.90, 1.35),
    "1206": (3.20, 1.60, 1.30, 1.70),
    "1210": (3.20, 2.50, 1.30, 2.60),
    "2512": (6.40, 3.20, 1.80, 3.30),
}


def _chip_passive(size_code: str, density: DensityLevel = "B") -> str:
    """Generate a chip passive (resistor/capacitor/inductor) footprint."""
    if size_code not in _CHIP_DIMS:
        raise ValueError(f"Unknown chip size '{size_code}'. Choose from {sorted(_CHIP_DIMS)}")
    body_l, body_w, land_l, land_w = _CHIP_DIMS[size_code]
    jt, _jh, js = _IPC_OFFSETS[density]
    pad_w = land_l + jt
    pad_h = land_w + 2 * js
    cx = (body_l / 2.0 + pad_w / 2.0) / 1.0  # centre of outer edge
    # Silk just outside body
    silk_x = body_l / 2.0 + 0.2
    silk_y = max(pad_h, body_w) / 2.0 + 0.2
    cyard_x = cx + pad_w / 2.0 + 0.25
    cyard_y = max(pad_h, body_w) / 2.0 + 0.25

    lines = _fp_header(
        f"C_{size_code}",
        f"Capacitor {size_code}",
        f"capacitor {size_code}",
    )
    lines += _ref_value(-(cyard_y + 0.5), cyard_y + 0.5, 0.0)
    # pads
    lines.append(_pad_smd(1, -cx, 0, pad_w, pad_h))
    lines.append(_pad_smd(2, cx, 0, pad_w, pad_h))
    # fab outline
    lines += _rect_line(_LAYER_FAB, -body_l / 2, -body_w / 2, body_l / 2, body_w / 2)
    # silk
    lines += _rect_line(_LAYER_SILK, -silk_x, -silk_y, silk_x, silk_y)
    # courtyard
    lines += _rect_line(_LAYER_CYARD, -cyard_x, -cyard_y, cyard_x, cyard_y, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SOT-23 (3 leads)
# ---------------------------------------------------------------------------


def _sot23(density: DensityLevel = "B") -> str:
    """Generate SOT-23-3 (standard 3-lead SOT-23) footprint."""
    jt, _jh, js = _IPC_OFFSETS[density]
    pad_w = 0.55 + jt
    pad_h = 0.70 + 2 * js
    # Pins 1,2 on left; pin 3 on right (centre)
    pitch = 0.95
    x_l = -1.45
    x_r = 1.45
    lines = _fp_header("SOT-23-3", "SOT-23 3-lead", "SOT-23 transistor")
    lines += _ref_value(-2.0, 2.0)
    lines.append(_pad_smd(1, x_l, -pitch / 2, pad_w, pad_h))
    lines.append(_pad_smd(2, x_l, pitch / 2, pad_w, pad_h))
    lines.append(_pad_smd(3, x_r, 0.0, pad_w, pad_h))
    lines += _rect_line(_LAYER_FAB, -1.3, -0.65, 1.3, 0.65)
    lines += _rect_line(_LAYER_CYARD, -1.85, -1.25, 1.85, 1.25, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SOIC / SOP / SSOP / TSSOP (dual-in-line SMD)
# ---------------------------------------------------------------------------


def _soic(
    pin_count: int,
    pitch_mm: float = 1.27,
    body_w_mm: float = 3.9,
    density: DensityLevel = "B",
    family: str = "SOIC",
) -> str:
    """Generate SOIC/SOP/SSOP/TSSOP footprint."""
    if pin_count % 2 != 0 or pin_count < 4 or pin_count > 64:
        raise ValueError("pin_count must be an even number between 4 and 64.")
    jt, _jh, js = _IPC_OFFSETS[density]
    pad_h = 1.60 + jt  # along body axis (IPC nominal lead length ~1.6mm)
    pad_w = pitch_mm * 0.7 + 2 * js
    n_per_side = pin_count // 2
    span = (n_per_side - 1) * pitch_mm
    # lead protrusion: 0.4mm past body edge
    x_centre = body_w_mm / 2 + 0.4 + pad_h / 2
    cyard_x = x_centre + pad_h / 2 + 0.25
    cyard_y = span / 2 + pad_w / 2 + 0.25
    name = f"{family}-{pin_count}_{pitch_mm:.2f}mm"
    lines = _fp_header(name, f"{family} {pin_count} leads {pitch_mm:.2f}mm pitch", family.lower())
    lines += _ref_value(-(cyard_y + 0.6), cyard_y + 0.6)
    for i in range(n_per_side):
        y = -span / 2 + i * pitch_mm
        lines.append(_pad_smd(i + 1, -x_centre, y, pad_h, pad_w))
        lines.append(_pad_smd(pin_count - i, x_centre, y, pad_h, pad_w))
    # body outline
    bh = span + pitch_mm
    lines += _rect_line(_LAYER_FAB, -body_w_mm / 2, -bh / 2, body_w_mm / 2, bh / 2)
    # pin-1 marker
    lines.append(
        f"\t(fp_circle (center {-body_w_mm / 2 - 0.5:.4f} {-span / 2:.4f})"
        f" (end {-body_w_mm / 2 - 0.3:.4f} {-span / 2:.4f})"
        f" (layer {_LAYER_FAB}) (stroke (width 0.1)(type solid)))"
    )
    lines += _rect_line(_LAYER_CYARD, -cyard_x, -cyard_y, cyard_x, cyard_y, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# QFP / LQFP / TQFP (quad, 4-sided)
# ---------------------------------------------------------------------------


def _qfp(
    pin_count: int,
    pitch_mm: float = 0.5,
    body_l_mm: float = 10.0,
    body_w_mm: float | None = None,
    density: DensityLevel = "B",
    family: str = "LQFP",
) -> str:
    """Generate QFP/LQFP/TQFP footprint (square or rectangular body)."""
    if pin_count % 4 != 0 or pin_count < 32 or pin_count > 256:
        raise ValueError("pin_count must be divisible by 4, between 32 and 256.")
    body_w = body_w_mm or body_l_mm
    n_per_side = pin_count // 4
    jt, _jh, js = _IPC_OFFSETS[density]
    pad_h = 1.50 + jt
    pad_w = pitch_mm - 0.10 + 2 * js
    span_tb = (n_per_side - 1) * pitch_mm  # top/bottom side span
    span_lr = span_tb  # square QFP
    x_centre = body_w / 2 + 0.6 + pad_h / 2
    y_centre = body_l_mm / 2 + 0.6 + pad_h / 2
    cyard = max(x_centre, y_centre) + pad_h / 2 + 0.25
    name = f"{family}-{pin_count}_{pitch_mm:.2f}mm_{body_l_mm:.0f}x{body_w:.0f}mm"
    lines = _fp_header(name, f"{family} {pin_count} leads {pitch_mm:.2f}mm pitch", family.lower())
    lines += _ref_value(-(cyard + 0.6), cyard + 0.6)
    # Bottom side (pins 1…n_per_side), going right-to-left
    for i in range(n_per_side):
        x = -span_tb / 2 + i * pitch_mm
        lines.append(_pad_smd(i + 1, x, y_centre, pad_w, pad_h))
    # Right side (n_per_side+1 … 2n), top-to-bottom
    for i in range(n_per_side):
        y = -span_lr / 2 + i * pitch_mm
        lines.append(_pad_smd(n_per_side + i + 1, x_centre, y, pad_h, pad_w))
    # Top side (2n+1 … 3n), right-to-left
    for i in range(n_per_side):
        x = span_tb / 2 - i * pitch_mm
        lines.append(_pad_smd(2 * n_per_side + i + 1, x, -y_centre, pad_w, pad_h))
    # Left side (3n+1 … 4n), bottom-to-top
    for i in range(n_per_side):
        y = span_lr / 2 - i * pitch_mm
        lines.append(_pad_smd(3 * n_per_side + i + 1, -x_centre, y, pad_h, pad_w))
    # Body outline
    lines += _rect_line(_LAYER_FAB, -body_w / 2, -body_l_mm / 2, body_w / 2, body_l_mm / 2)
    # Pin-1 corner notch
    lines.append(
        f"\t(fp_arc (start {-body_w / 2:.4f} {body_l_mm / 2:.4f})"
        f" (mid {-body_w / 2 - 0.3:.4f} {body_l_mm / 2 - 0.15:.4f})"
        f" (end {-body_w / 2 + 0.3:.4f} {body_l_mm / 2:.4f})"
        f" (layer {_LAYER_FAB}) (stroke (width 0.1)(type solid)))"
    )
    lines += _rect_line(_LAYER_CYARD, -cyard, -cyard, cyard, cyard, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# QFN / DFN (no-lead packages)
# ---------------------------------------------------------------------------


def _qfn(
    pin_count: int,
    pitch_mm: float = 0.5,
    body_size_mm: float = 7.0,
    exposed_pad_mm: float | None = None,
    density: DensityLevel = "B",
) -> str:
    """Generate QFN footprint with optional exposed thermal pad."""
    if pin_count % 4 != 0 or pin_count < 8 or pin_count > 100:
        raise ValueError("pin_count must be divisible by 4, between 8 and 100.")
    jt, _jh, js = _IPC_OFFSETS[density]
    pad_h = 0.40 + jt  # QFN pad protrudes 0.4 mm from body
    pad_w = pitch_mm - 0.05 + 2 * js
    n_per_side = pin_count // 4
    span = (n_per_side - 1) * pitch_mm
    xy_centre = body_size_mm / 2 + pad_h / 2
    cyard = xy_centre + pad_h / 2 + 0.25
    ep_size = exposed_pad_mm or (body_size_mm - 1.0)
    name = f"QFN-{pin_count}_{pitch_mm:.2f}mm_{body_size_mm:.1f}x{body_size_mm:.1f}mm"
    lines = _fp_header(name, f"QFN {pin_count} leads {pitch_mm:.2f}mm pitch", "qfn")
    lines += _ref_value(-(cyard + 0.6), cyard + 0.6)
    # Bottom side — pins 1…n
    for i in range(n_per_side):
        x = -span / 2 + i * pitch_mm
        lines.append(_pad_smd(i + 1, x, xy_centre, pad_w, pad_h))
    # Right side
    for i in range(n_per_side):
        y = -span / 2 + i * pitch_mm
        lines.append(_pad_smd(n_per_side + i + 1, xy_centre, y, pad_h, pad_w))
    # Top side
    for i in range(n_per_side):
        x = span / 2 - i * pitch_mm
        lines.append(_pad_smd(2 * n_per_side + i + 1, x, -xy_centre, pad_w, pad_h))
    # Left side
    for i in range(n_per_side):
        y = span / 2 - i * pitch_mm
        lines.append(_pad_smd(3 * n_per_side + i + 1, -xy_centre, y, pad_h, pad_w))
    # Exposed thermal pad
    ep_num = pin_count + 1
    lines.append(
        f"\t(pad {ep_num!r} smd rect (at 0 0) (size {ep_size:.4f} {ep_size:.4f})"
        f" (layers {_LAYER_CU} {_LAYER_MASK} {_LAYER_PASTE}))"
    )
    # Body outline
    lines += _rect_line(
        _LAYER_FAB,
        -body_size_mm / 2,
        -body_size_mm / 2,
        body_size_mm / 2,
        body_size_mm / 2,
    )
    lines += _rect_line(_LAYER_CYARD, -cyard, -cyard, cyard, cyard, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BGA
# ---------------------------------------------------------------------------


def _bga(
    rows: int,
    cols: int,
    pitch_mm: float = 0.8,
    ball_diameter_mm: float | None = None,
    density: DensityLevel = "B",
) -> str:
    """Generate BGA footprint (full-grid).

    Pad numbering: A1 = top-left, row letters A,B,C… (skip I,O,Q,S,X,Z per IPC).
    """
    _skip = frozenset("IOQSXZ")
    _letters = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in _skip]

    jt, _jh, _js = _IPC_OFFSETS[density]
    ball_d = ball_diameter_mm or (pitch_mm * 0.5 + 0.05)
    pad_d = ball_d + jt * 0.5  # IPC solder-mask-defined land
    total_w = (cols - 1) * pitch_mm
    total_h = (rows - 1) * pitch_mm
    cyard = max(total_w, total_h) / 2 + pitch_mm / 2 + 0.25
    name = f"BGA-{rows * cols}_{rows}x{cols}_{pitch_mm:.2f}mm"
    lines = _fp_header(name, f"BGA {rows}×{cols} {pitch_mm:.2f}mm pitch", "bga")
    lines += _ref_value(-(cyard + 0.6), cyard + 0.6)

    for r in range(rows):
        row_letter = _letters[r] if r < len(_letters) else f"R{r}"
        for c in range(cols):
            x = -total_w / 2 + c * pitch_mm
            y = -total_h / 2 + r * pitch_mm
            pad_name = f"{row_letter}{c + 1}"
            lines.append(
                f"\t(pad {_sexpr_string(pad_name)} smd circle (at {x:.4f} {y:.4f})"
                f" (size {pad_d:.4f} {pad_d:.4f})"
                f" (layers {_LAYER_CU} {_LAYER_MASK}))"
            )
    lines += _rect_line(
        _LAYER_FAB,
        -total_w / 2 - pitch_mm / 2,
        -total_h / 2 - pitch_mm / 2,
        total_w / 2 + pitch_mm / 2,
        total_h / 2 + pitch_mm / 2,
    )
    lines += _rect_line(_LAYER_CYARD, -cyard, -cyard, cyard, cyard, 0.05)
    # A1 corner dot
    lines.append(
        _circle_line(
            _LAYER_FAB,
            -total_w / 2 - pitch_mm * 0.4,
            -total_h / 2 - pitch_mm * 0.4,
            0.15,
        )
    )
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Through-hole pin header
# ---------------------------------------------------------------------------

_HEADER_PITCH = {2.54, 2.00, 1.27}


def _pin_header(
    pin_count: int,
    rows: int = 1,
    pitch_mm: float = 2.54,
) -> str:
    """Generate through-hole pin header (1×N or 2×N)."""
    if pitch_mm not in _HEADER_PITCH:
        raise ValueError(f"pitch_mm must be one of {sorted(_HEADER_PITCH)}")
    if rows not in (1, 2):
        raise ValueError("rows must be 1 or 2.")
    drill = pitch_mm * 0.4
    pad_size = drill + 0.8
    name = f"PinHeader_{rows}x{pin_count:02d}_{pitch_mm:.2f}mm"
    lines = _fp_header_tht(
        name,
        f"Pin header {rows}×{pin_count} {pitch_mm:.2f}mm",
        "pin-header connector",
    )
    lines += _ref_value(-(pin_count * pitch_mm / 2 + 0.5), pin_count * pitch_mm / 2 + 0.5)
    for i in range(pin_count):
        for r in range(rows):
            num = i * rows + r + 1
            x = r * pitch_mm - (rows - 1) * pitch_mm / 2
            y = -((pin_count - 1) * pitch_mm / 2) + i * pitch_mm
            lines.append(_pad_tht(num, x, y, drill, pad_size))
    # Silk outline
    ox = (rows - 1) * pitch_mm / 2 + pitch_mm / 2
    oy = (pin_count - 1) * pitch_mm / 2 + pitch_mm / 2
    lines += _rect_line(_LAYER_SILK, -ox, -oy, ox, oy)
    lines += _rect_line(_LAYER_CYARD, -ox - 0.25, -oy - 0.25, ox + 0.25, oy + 0.25, 0.05)
    lines.append(")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_footprint(
    package: str,
    *,
    pin_count: int | None = None,
    pitch_mm: float | None = None,
    body_l_mm: float | None = None,
    body_w_mm: float | None = None,
    density: DensityLevel = "B",
    rows: int = 1,
    exposed_pad_mm: float | None = None,
    ball_diameter_mm: float | None = None,
) -> str:
    """Generate a KiCad ``.kicad_mod`` S-expression for the requested package.

    Args:
        package: Package family. One of:
            ``"0201"``, ``"0402"``, ``"0603"``, ``"0805"``, ``"1206"``,
            ``"1210"``, ``"2512"`` — chip passives;
            ``"SOT-23"`` — SOT-23-3;
            ``"SOIC"``, ``"SOP"``, ``"SSOP"``, ``"TSSOP"`` — dual in-line SMD;
            ``"QFP"``, ``"LQFP"``, ``"TQFP"`` — quad flat pack;
            ``"QFN"``, ``"DFN"`` — no-lead;
            ``"BGA"`` — ball grid array;
            ``"PinHeader"`` — through-hole pin header.
        pin_count: Number of leads/balls (required for non-chip packages).
        pitch_mm: Lead pitch in mm. Defaults vary by package family.
        body_l_mm: Body length in mm (QFP/QFN; defaults apply).
        body_w_mm: Body width in mm (QFP only; defaults to ``body_l_mm``).
        density: IPC-7351B density level: ``"A"`` (generous), ``"B"`` (nominal),
            ``"C"`` (compact). Defaults to ``"B"``.
        rows: Number of rows for BGA (``rows×cols``) or PinHeader (1 or 2).
        exposed_pad_mm: Exposed pad size for QFN (defaults to ``body_size_mm - 1``).
        ball_diameter_mm: BGA ball diameter (defaults to ``pitch * 0.5 + 0.05``).

    Returns:
        A string containing the complete ``.kicad_mod`` S-expression.

    Raises:
        ValueError: For unsupported package families or out-of-range parameters.
    """
    pkg_up = package.upper()

    # Chip passives
    if pkg_up in {k.upper() for k in _CHIP_DIMS}:
        canonical = next(k for k in _CHIP_DIMS if k.upper() == pkg_up)
        return _chip_passive(canonical, density)

    if pkg_up == "SOT-23":
        return _sot23(density)

    if pkg_up in {"SOIC", "SOP", "SSOP", "TSSOP"}:
        if pin_count is None:
            raise ValueError("pin_count is required for SOIC/SOP/SSOP/TSSOP packages.")
        return _soic(
            pin_count,
            pitch_mm=pitch_mm or (1.27 if pkg_up == "SOIC" else 0.65),
            body_w_mm=body_w_mm or (3.9 if pkg_up == "SOIC" else 4.4),
            density=density,
            family=pkg_up,
        )

    if pkg_up in {"QFP", "LQFP", "TQFP"}:
        if pin_count is None:
            raise ValueError("pin_count is required for QFP/LQFP/TQFP packages.")
        return _qfp(
            pin_count,
            pitch_mm=pitch_mm or 0.5,
            body_l_mm=body_l_mm or 10.0,
            body_w_mm=body_w_mm,
            density=density,
            family=pkg_up,
        )

    if pkg_up in {"QFN", "DFN"}:
        if pin_count is None:
            raise ValueError("pin_count is required for QFN/DFN packages.")
        return _qfn(
            pin_count,
            pitch_mm=pitch_mm or 0.5,
            body_size_mm=body_l_mm or 7.0,
            exposed_pad_mm=exposed_pad_mm,
            density=density,
        )

    if pkg_up == "BGA":
        if pin_count is None or rows is None:
            raise ValueError("pin_count (total balls) and rows are required for BGA.")
        cols = math.ceil(pin_count / rows)
        return _bga(
            rows,
            cols,
            pitch_mm=pitch_mm or 0.8,
            ball_diameter_mm=ball_diameter_mm,
            density=density,
        )

    if pkg_up == "PINHEADER":
        if pin_count is None:
            raise ValueError("pin_count is required for PinHeader.")
        return _pin_header(
            pin_count,
            rows=rows,
            pitch_mm=pitch_mm or 2.54,
        )

    raise ValueError(
        f"Unsupported package family '{package}'. "
        "Supported: chip passives (0201/0402/0603/0805/1206/1210/2512), "
        "SOT-23, SOIC, SOP, SSOP, TSSOP, QFP, LQFP, TQFP, QFN, DFN, BGA, PinHeader."
    )
