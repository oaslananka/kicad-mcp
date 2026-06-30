"""Unit tests for page-bounded auto-layout (paper auto-fit, Phase 4)."""

from __future__ import annotations

from kicad_mcp.tools.schematic import (
    _apply_basic_auto_layout,
    _sheet_usable_rows,
    select_paper_for_capacity,
)
from kicad_mcp.tools.schematic_constants import (
    AUTO_LAYOUT_ORIGIN_Y_MM,
    AUTO_LAYOUT_ROW_SPACING_MM,
    PAPER_SIZES_MM,
)


def test_select_paper_never_downsizes() -> None:
    # A tiny circuit on an explicit A2 sheet keeps A2.
    assert select_paper_for_capacity(1, start_paper="A2") == "A2"


def test_select_paper_upgrades_when_rows_exceed_a4() -> None:
    a4_rows = _sheet_usable_rows("A4")
    chosen = select_paper_for_capacity(a4_rows + 5, start_paper="A4")
    assert chosen != "A4"
    assert _sheet_usable_rows(chosen) >= a4_rows + 5


def test_select_paper_caps_at_largest() -> None:
    # Absurd row count still returns a defined ladder entry, not an error.
    assert select_paper_for_capacity(100_000, start_paper="A4") == "A0"


def _max_y(entries: list[dict[str, object]]) -> float:
    return max(float(e["y_mm"]) for e in entries)  # type: ignore[arg-type]


def test_basic_layout_keeps_everything_on_sheet() -> None:
    symbols = [{"reference": f"R{i}"} for i in range(200)]
    powers = [{"name": "GND"}, {"name": "+3V3"}]
    labels = [{"name": f"NET{i}"} for i in range(10)]
    laid_sym, laid_pwr, laid_lbl, paper = _apply_basic_auto_layout(symbols, powers, labels)

    _, height = PAPER_SIZES_MM[paper]
    bottom_margin = AUTO_LAYOUT_ROW_SPACING_MM  # one row of slack
    placed = [*laid_sym, *laid_pwr, *laid_lbl]
    assert _max_y(placed) <= height - 0.0
    # And the sheet had to grow beyond the default to hold 200 parts.
    assert paper != "A4"
    # Every placed object stays at or below the top origin band.
    assert all(float(e["y_mm"]) >= AUTO_LAYOUT_ORIGIN_Y_MM - bottom_margin for e in laid_sym)


def test_small_basic_layout_stays_on_a4() -> None:
    laid_sym, _pwr, _lbl, paper = _apply_basic_auto_layout(
        [{"reference": "R1"}, {"reference": "R2"}], [{"name": "GND"}], [{"name": "OUT"}]
    )
    assert paper == "A4"
    assert all(float(s["y_mm"]) <= PAPER_SIZES_MM["A4"][1] for s in laid_sym)


def test_symbol_footprint_cells_scales_with_extent() -> None:
    from kicad_mcp.tools.schematic import _symbol_footprint_cells

    # Unknown extent -> a single cell.
    assert _symbol_footprint_cells(None, 38.1, 35.56) == (1, 1)
    # A tall multi-pin part (extent height 40 mm + margin) needs >1 row.
    cols, rows = _symbol_footprint_cells((0.0, 0.0, 6.0, 40.0), 38.1, 35.56)
    assert rows >= 2 and cols >= 1


def test_next_free_block_reserves_non_overlapping_blocks() -> None:
    from kicad_mcp.tools.schematic import _next_free_block

    occupied: set[tuple[int, int]] = set()
    first = _next_free_block(occupied, 2, 2, cell_w=20.0, cell_h=20.0, paper="A2")
    assert first == (0, 0)
    # The 2x2 block (0,0)-(1,1) is now reserved.
    assert {(0, 0), (1, 0), (0, 1), (1, 1)} <= occupied
    second = _next_free_block(occupied, 1, 1, cell_w=20.0, cell_h=20.0, paper="A2")
    assert second not in {(0, 0), (1, 0), (0, 1), (1, 1)}
