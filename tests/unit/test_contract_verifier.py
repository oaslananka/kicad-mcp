"""Unit tests for the structural symbol/footprint contract verifier (issue #156)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_mcp.models.contract_verifier import (
    extract_lib_symbol_block,
    find_symbol_instance,
    parse_footprint,
    parse_symbol_pins,
    verify_contract,
)

RESISTOR_SYMBOL = """
(symbol "Device:R"
    (pin_numbers hide)
    (pin_names (offset 0))
    (property "Reference" "R" (at 2.032 0 90))
    (property "Datasheet" "https://example.com/r.pdf" (at 0 0 0))
    (symbol "R_0_1"
        (rectangle (start -1.016 -2.54) (end 1.016 2.54))
    )
    (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
            (name "~" (effects (font (size 1.27 1.27))))
            (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
            (name "~" (effects (font (size 1.27 1.27))))
            (number "2" (effects (font (size 1.27 1.27)))))
    )
)
"""

CAPACITOR_SYMBOL = """
(symbol "Device:C"
    (pin_names (offset 0.254))
    (property "Reference" "C" (at 0.635 2.54 0))
    (symbol "C_1_1"
        (pin passive line (at 0 3.81 270) (length 2.794)
            (name "~" (effects (font (size 1.27 1.27))))
            (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 2.794)
            (name "~" (effects (font (size 1.27 1.27))))
            (number "2" (effects (font (size 1.27 1.27)))))
    )
)
"""

# A symbol that claims three pins where the footprint only has two pads.
SOT23_SYMBOL = """
(symbol "Device:Q_NPN_BCE"
    (symbol "Q_NPN_BCE_0_1"
        (pin input line (at -2.54 0 0) (length 1.27)
            (name "B" (effects (font (size 1.27 1.27))))
            (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 2.54 2.54 0) (length 1.27)
            (name "C" (effects (font (size 1.27 1.27))))
            (number "2" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 2.54 -2.54 0) (length 1.27)
            (name "E" (effects (font (size 1.27 1.27))))
            (number "3" (effects (font (size 1.27 1.27)))))
    )
)
"""

RESISTOR_FOOTPRINT = """
(footprint "R_0402_1005Metric"
    (fp_line (start -0.27 -0.27) (end 0.27 -0.27) (layer "F.SilkS"))
    (fp_poly (pts (xy -0.5 -0.27)) (layer "F.Fab"))
    (fp_line (start -0.93 -0.52) (end 0.93 -0.52) (layer "F.CrtYd"))
    (pad "1" smd roundrect (at -0.51 0) (size 0.54 0.64) (layers "F.Cu" "F.Paste" "F.Mask"))
    (pad "2" smd roundrect (at 0.51 0) (size 0.54 0.64) (layers "F.Cu" "F.Paste" "F.Mask"))
    (model "${KICAD8_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_0402_1005Metric.wrl"
        (offset (xyz 0 0 0)))
)
"""

# Two-pad footprint with a mechanical/unnumbered pad, no courtyard, no model.
TWO_PAD_BARE_FOOTPRINT = """
(footprint "Custom_2pad"
    (fp_line (start 0 0) (end 1 0) (layer "F.SilkS"))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))
    (pad "2" smd rect (at 2 0) (size 1 1) (layers "F.Cu"))
    (pad "" np_thru_hole circle (at 1 1) (size 2 2) (layers "*.Cu"))
)
"""

SCHEMATIC = (
    """
(kicad_sch (version 20240101)
  (lib_symbols
"""
    + RESISTOR_SYMBOL
    + """
  )
  (symbol (lib_id "Device:R") (at 100 50 0)
    (property "Reference" "R5" (at 102 49 0))
    (property "Value" "10k" (at 102 51 0))
    (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 100 50 0))
  )
)
"""
)


def test_parse_symbol_pins_resistor() -> None:
    pins = parse_symbol_pins(RESISTOR_SYMBOL)
    assert {pin.number for pin in pins} == {"1", "2"}
    assert all(pin.electrical_type == "passive" for pin in pins)


def test_parse_footprint_resistor_is_complete() -> None:
    shape = parse_footprint(RESISTOR_FOOTPRINT)
    assert shape.connectable_pads == ("1", "2")
    assert shape.has_courtyard
    assert shape.has_fabrication
    assert shape.has_silkscreen
    assert shape.has_3d_model
    assert shape.mechanical_pad_count == 0


def test_parse_footprint_counts_mechanical_pads() -> None:
    shape = parse_footprint(TWO_PAD_BARE_FOOTPRINT)
    assert shape.connectable_pads == ("1", "2")
    assert shape.mechanical_pad_count == 1
    assert not shape.has_courtyard
    assert not shape.has_3d_model


def test_verify_good_resistor_passes() -> None:
    report = verify_contract(
        reference="R5",
        lib_id="Device:R",
        footprint_id="Resistor_SMD:R_0402_1005Metric",
        pins=parse_symbol_pins(RESISTOR_SYMBOL),
        footprint=parse_footprint(RESISTOR_FOOTPRINT),
        datasheet="https://example.com/r.pdf",
    )
    assert report.status == "PASS"
    codes = {f.code: f.level for f in report.findings}
    assert codes["pin_pad_count"] == "PASS"
    assert codes["pin_pad_numbers"] == "PASS"


def test_verify_good_capacitor_passes() -> None:
    report = verify_contract(
        reference="C1",
        lib_id="Device:C",
        footprint_id="Capacitor_SMD:C_0402_1005Metric",
        pins=parse_symbol_pins(CAPACITOR_SYMBOL),
        footprint=parse_footprint(RESISTOR_FOOTPRINT),
    )
    assert report.status == "PASS"


def test_verify_pin_count_mismatch_fails() -> None:
    report = verify_contract(
        reference="Q1",
        lib_id="Device:Q_NPN_BCE",
        footprint_id="Custom_2pad",
        pins=parse_symbol_pins(SOT23_SYMBOL),
        footprint=parse_footprint(TWO_PAD_BARE_FOOTPRINT),
    )
    assert report.status == "FAIL"
    by_code = {f.code: f for f in report.findings}
    assert by_code["pin_pad_count"].level == "FAIL"
    # Pin "3" exists in the symbol but has no pad.
    assert by_code["pin_pad_numbers"].level == "FAIL"
    assert "3" in by_code["pin_pad_numbers"].message


def test_missing_courtyard_is_warn_not_fail() -> None:
    report = verify_contract(
        reference="R1",
        lib_id="Device:R",
        footprint_id="Custom_2pad",
        pins=parse_symbol_pins(RESISTOR_SYMBOL),
        footprint=parse_footprint(TWO_PAD_BARE_FOOTPRINT),
        datasheet="https://example.com/r.pdf",
    )
    # Pins/pads still agree, so the worst finding is a WARN (courtyard/model).
    assert report.status == "WARN"
    by_code = {f.code: f for f in report.findings}
    assert by_code["footprint_courtyard"].level == "WARN"
    assert by_code["pin_pad_count"].level == "PASS"


def test_find_symbol_instance_and_lib_block() -> None:
    resolved = find_symbol_instance(SCHEMATIC, "R5")
    assert resolved == ("Device:R", "Resistor_SMD:R_0402_1005Metric")
    block = extract_lib_symbol_block(SCHEMATIC, "Device:R")
    assert block is not None
    assert {pin.number for pin in parse_symbol_pins(block)} == {"1", "2"}


def test_find_symbol_instance_missing_returns_none() -> None:
    assert find_symbol_instance(SCHEMATIC, "R99") is None


# --- Tool-level tests for lib_verify_component_contract ---------------------

TRANSISTOR_SCHEMATIC = (
    """
(kicad_sch (version 20240101)
  (lib_symbols
"""
    + SOT23_SYMBOL
    + """
  )
  (symbol (lib_id "Device:Q_NPN_BCE") (at 100 50 0)
    (property "Reference" "Q1" (at 102 49 0))
    (property "Value" "MMBT3904" (at 102 51 0))
    (property "Footprint" "Custom:2pad" (at 100 50 0))
  )
)
"""
)


def _make_project(tmp_path: Path, sch_text: str) -> None:
    (tmp_path / "test.kicad_pro").write_text("{}", encoding="utf-8")
    (tmp_path / "test.kicad_pcb").write_text("", encoding="utf-8")
    (tmp_path / "test.kicad_sch").write_text(sch_text, encoding="utf-8")


@pytest.mark.anyio
async def test_tool_verifies_good_resistor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import kicad_mcp.tools.library as library_mod
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    _make_project(tmp_path, SCHEMATIC)
    fp_file = tmp_path / "R_0402_1005Metric.kicad_mod"
    fp_file.write_text(RESISTOR_FOOTPRINT, encoding="utf-8")
    monkeypatch.setattr(library_mod, "_footprint_file", lambda _lib, _fp: fp_file)

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(tmp_path)})
    raw = await call_tool_text(server, "lib_verify_component_contract", {"reference": "R5"})
    report = json.loads(raw)
    assert report["status"] == "PASS"
    assert report["lib_id"] == "Device:R"
    assert report["footprint"] == "Resistor_SMD:R_0402_1005Metric"


@pytest.mark.anyio
async def test_tool_flags_pin_count_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kicad_mcp.tools.library as library_mod
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    _make_project(tmp_path, TRANSISTOR_SCHEMATIC)
    fp_file = tmp_path / "2pad.kicad_mod"
    fp_file.write_text(TWO_PAD_BARE_FOOTPRINT, encoding="utf-8")
    monkeypatch.setattr(library_mod, "_footprint_file", lambda _lib, _fp: fp_file)

    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(tmp_path)})
    raw = await call_tool_text(server, "lib_verify_component_contract", {"reference": "Q1"})
    report = json.loads(raw)
    assert report["status"] == "FAIL"
    by_code = {f["code"]: f["level"] for f in report["findings"]}
    assert by_code["pin_pad_count"] == "FAIL"


@pytest.mark.anyio
async def test_tool_reports_unknown_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_mcp.server import create_server
    from tests.conftest import call_tool_text

    _make_project(tmp_path, SCHEMATIC)
    server = create_server()
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(tmp_path)})
    raw = await call_tool_text(server, "lib_verify_component_contract", {"reference": "R404"})
    report = json.loads(raw)
    assert "error" in report
