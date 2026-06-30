"""Synthetic KiCad schematic generators for the regression zoo (issue #159).

These produce valid (or deliberately malformed) ``.kicad_sch`` text on the fly so
the benchmark/regression suite can cover large and messy boards without committing
multi-megabyte fixtures. Everything here is plain text generation — no KiCad
dependency — so it runs anywhere.
"""

from __future__ import annotations

import math

_RESISTOR_LIB_SYMBOL = """    (symbol "Device:R"
      (pin_numbers hide) (pin_names (offset 0))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~") (number "1"))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~") (number "2"))
      )
    )"""


def generate_resistor_grid(
    n_components: int,
    *,
    paper: str | None = None,
    spacing_mm: float = 12.7,
    net_prefix: str = "NET",
) -> str:
    """Return a schematic of ``n_components`` resistors laid out in a grid.

    The grid pitch exceeds a resistor's drawn body (~10 mm tall) and per-net
    labels sit clear of the value text, so a clean grid never trips the visual-QA
    overlap or off-sheet heuristics; this isolates the benchmark to
    parsing/throughput rather than defect detection. The sheet is auto-sized to a
    ``User`` paper that holds the whole grid unless ``paper`` is given explicitly.
    """

    origin = 20.0
    margin = 20.0
    columns = max(1, math.isqrt(n_components))
    rows = max(1, math.ceil(n_components / columns))
    if paper is None:
        width = origin + columns * spacing_mm + margin
        height = origin + rows * spacing_mm + margin
        paper_decl = f'(paper "User" {width:.1f} {height:.1f})'
    else:
        paper_decl = f'(paper "{paper}")'

    lines = [
        f"(kicad_sch (version 20240101) {paper_decl}",
        '  (title_block (title "Synthetic Regression Board") (rev "1")'
        ' (date "2026-01-01") (company "Regression Zoo"))',
        "  (lib_symbols",
        _RESISTOR_LIB_SYMBOL,
        "  )",
    ]
    for index in range(n_components):
        x = origin + (index % columns) * spacing_mm
        y = origin + (index // columns) * spacing_mm
        lines.append(f'  (symbol (lib_id "Device:R") (at {x} {y} 0)')
        lines.append(f'    (property "Reference" "R{index + 1}" (at {x + 4} {y - 1} 0))')
        lines.append(f'    (property "Value" "10k" (at {x + 4} {y + 1} 0))')
        lines.append(f'    (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at {x} {y} 0))')
        lines.append("  )")
        lines.append(f'  (label "{net_prefix}{index}" (at {x} {y + 4} 0))')
    lines.append(")")
    return "\n".join(lines)


def generate_unicode_schematic() -> str:
    """Return a small schematic with non-ASCII net names (issue #159 unicode case)."""

    return """
(kicad_sch (version 20240101) (paper "A4")
  (title_block (title "Ölçüm Kartı") (rev "A") (date "2026-01-01") (company "Şirket"))
  (label "GÜÇ_3V3" (at 50 40 0))
  (label "TOPRAK" (at 150 100 0))
  (symbol (lib_id "Device:R") (at 100 50 0)
    (property "Reference" "R1" (at 102 49 0))
    (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 100 50 0))
  )
)
"""


def malformed_schematics() -> dict[str, str]:
    """Return a set of deliberately broken inputs parsers must survive."""

    return {
        "truncated": '(kicad_sch (paper "A4") (symbol (lib_id "Device:R") (at 10 10',
        "unbalanced_parens": '(kicad_sch (label "NET" (at 5 5 0)',
        "garbage": "not an s-expression at all }{][ )))(((",
        "empty": "",
        "only_paper": '(kicad_sch (paper "A4"))',
    }
