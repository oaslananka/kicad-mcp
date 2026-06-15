"""Integration tests for simulation SPICE library management tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.server import build_server
from tests.conftest import call_tool_text


@pytest.mark.anyio
async def test_sim_assign_spice_model_updates_symbol_properties(
    sample_project: Path, mock_kicad
) -> None:
    """sim_assign_spice_model should set Sim.* properties on a symbol."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server,
        "sim_assign_spice_model",
        {
            "reference": "R1",
            "model_name": "R",
            "library": "Device",
            "model_type": "R",
            "pins": "1 2",
            "params": "R=10k",
        },
    )
    assert "Updated R1.Sim.Name" in result or "Sim.Name" in result


@pytest.mark.anyio
async def test_sim_assign_spice_model_skips_empty_fields(sample_project: Path, mock_kicad) -> None:
    """sim_assign_spice_model should skip empty string fields."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    await call_tool_text(
        server,
        "sch_build_circuit",
        {
            "symbols": [
                {
                    "library": "Device",
                    "symbol_name": "R",
                    "x_mm": 10.0,
                    "y_mm": 10.0,
                    "reference": "R1",
                    "value": "10k",
                    "footprint": "Resistor_SMD:R_0805",
                }
            ]
        },
    )

    result = await call_tool_text(
        server,
        "sim_assign_spice_model",
        {"reference": "R1", "model_name": "R"},
    )
    assert "Updated R1.Sim.Name" in result or "Sim.Name" in result


@pytest.mark.anyio
async def test_sim_assign_spice_model_no_fields_provided(sample_project: Path) -> None:
    """sim_assign_spice_model should report when no fields are provided."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sim_assign_spice_model", {"reference": "R1"}
    )
    assert "No fields were provided" in result


@pytest.mark.anyio
async def test_sim_list_spice_libraries_empty(sample_project: Path) -> None:
    """sim_list_spice_libraries should report when no libraries are configured."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sim_list_spice_libraries", {})
    assert "No SPICE libraries are configured" in result


@pytest.mark.anyio
async def test_sim_add_spice_library(sample_project: Path) -> None:
    """sim_add_spice_library should register a library in the project file."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/mylib.lib"},
    )
    assert "Added SPICE library 'MyModels'" in result

    listing = await call_tool_text(server, "sim_list_spice_libraries", {})
    assert "MyModels" in listing
    assert "models/mylib.lib" in listing


@pytest.mark.anyio
async def test_sim_add_spice_library_duplicate(sample_project: Path) -> None:
    """sim_add_spice_library should reject duplicate names."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/mylib.lib"},
    )
    result = await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/other.lib"},
    )
    assert "already exists" in result


@pytest.mark.anyio
async def test_sim_remove_spice_library(sample_project: Path) -> None:
    """sim_remove_spice_library should unregister a library."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/mylib.lib"},
    )
    result = await call_tool_text(
        server, "sim_remove_spice_library", {"name": "MyModels"}
    )
    assert "Removed SPICE library 'MyModels'" in result

    listing = await call_tool_text(server, "sim_list_spice_libraries", {})
    assert "No SPICE libraries are configured" in listing


@pytest.mark.anyio
async def test_sim_remove_spice_library_missing(sample_project: Path) -> None:
    """sim_remove_spice_library should report when library is not found."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sim_remove_spice_library", {"name": "MissingLib"}
    )
    assert "No SPICE library named 'MissingLib' was found" in result


@pytest.mark.anyio
async def test_sim_validate_spice_setup_empty(sample_project: Path) -> None:
    """sim_validate_spice_setup should report when no libraries are configured."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sim_validate_spice_setup", {})
    assert "No SPICE libraries are configured" in result


@pytest.mark.anyio
async def test_sim_validate_spice_setup_resolves_paths(sample_project: Path) -> None:
    """sim_validate_spice_setup should check library file existence."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    lib_file = sample_project / "models" / "mylib.lib"
    lib_file.parent.mkdir(parents=True, exist_ok=True)
    lib_file.write_text("* SPICE model library\n", encoding="utf-8")

    await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/mylib.lib"},
    )
    result = await call_tool_text(server, "sim_validate_spice_setup", {})
    assert "OK" in result
    assert "Resolved: 1, Missing: 0" in result


@pytest.mark.anyio
async def test_sim_validate_spice_setup_reports_missing(sample_project: Path) -> None:
    """sim_validate_spice_setup should report missing library files."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    await call_tool_text(
        server,
        "sim_add_spice_library",
        {"name": "MyModels", "uri": "models/missing.lib"},
    )
    result = await call_tool_text(server, "sim_validate_spice_setup", {})
    assert "NOT FOUND" in result
    assert "Resolved: 0, Missing: 1" in result


@pytest.mark.anyio
async def test_sim_add_spice_directive_validation(sample_project: Path) -> None:
    """sim_add_spice_directive should validate allowed directive prefixes."""
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    valid_directives = [
        ".param temp=25",
        ".include models.lib",
        ".options reltol=0.001",
        ".model D D(IS=1e-14)",
        ".ic v(out)=0",
        ".nodeset v(in)=5",
        ".ac dec 10 1 1e6",
        ".tran 1u 10m",
        ".dc v1 0 5 0.1",
        "* comment line",
    ]

    for directive in valid_directives:
        result = await call_tool_text(
            server, "sim_add_spice_directive", {"directive": directive}
        )
        assert "Stored simulation directive" in result, f"Failed for {directive}"

    invalid = await call_tool_text(
        server, "sim_add_spice_directive", {"directive": "R1 out 0 1k"}
    )
    assert "Unsupported SPICE directive prefix" in invalid


@pytest.mark.anyio
async def test_sim_run_operating_point_with_empty_netlist_path(
    sample_project: Path, monkeypatch
) -> None:
    """sim_run_operating_point should export netlist when path is empty."""
    exported: list[Path] = []

    def fake_run_cli_variants(variants: list[list[str]]) -> tuple[int, str, str]:
        out_file = Path(variants[0][variants[0].index("--output") + 1])
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("* exported\n.end\n", encoding="utf-8")
        exported.append(out_file)
        return (0, "", "")

    class FakeRunner:
        def run_operating_point(self, netlist_path, output_dir, probe_nets):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="ngspice-cli",
                analysis="operating-point",
                netlist_path=netlist_path,
                traces=[SimulationTrace(name="out", values=[1.8])],
            )

    monkeypatch.setattr(
        "kicad_mcp.tools.simulation._run_cli_variants", fake_run_cli_variants
    )
    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(server, "sim_run_operating_point", {})
    assert "Operating point analysis" in result
    assert exported


@pytest.mark.anyio
async def test_sim_check_stability_no_crossover(sample_project: Path, monkeypatch) -> None:
    """sim_check_stability should handle case with no unity-gain crossover."""
    netlist = sample_project / "loop.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_ac_analysis(
            self,
            netlist_path,
            output_dir,
            probe_nets,
            *,
            start_freq_hz,
            stop_freq_hz,
            points_per_decade,
        ):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="inspice",
                analysis="ac",
                netlist_path=netlist_path,
                x_label="frequency",
                x_values=[10.0, 100.0, 1000.0],
                traces=[
                    SimulationTrace(
                        name="out",
                        values=[0.1, 0.05, 0.01],
                        phase_values=[-90.0, -135.0, -170.0],
                    ),
                    SimulationTrace(
                        name="fb",
                        values=[1.0, 1.0, 1.0],
                        phase_values=[0.0, 0.0, 0.0],
                    ),
                ],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_check_stability",
        {"netlist_path": "loop.cir", "output_net": "out", "feedback_net": "fb"},
    )
    assert "Stability check" in result
    assert "No unity-gain crossover was found" in result


@pytest.mark.anyio
async def test_sim_check_stability_missing_traces(sample_project: Path, monkeypatch) -> None:
    """sim_check_stability should handle missing traces gracefully."""
    netlist = sample_project / "loop.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_ac_analysis(
            self,
            netlist_path,
            output_dir,
            probe_nets,
            *,
            start_freq_hz,
            stop_freq_hz,
            points_per_decade,
        ):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="inspice",
                analysis="ac",
                netlist_path=netlist_path,
                x_label="frequency",
                x_values=[10.0, 100.0],
                traces=[
                    SimulationTrace(
                        name="out",
                        values=[1.0, 0.1],
                        phase_values=[-90.0, -135.0],
                    ),
                ],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_check_stability",
        {"netlist_path": "loop.cir", "output_net": "out", "feedback_net": "fb"},
    )
    assert "Stability check" in result
    assert "Could not find both AC traces" in result


@pytest.mark.anyio
async def test_sim_run_transient_reports_progress(sample_project: Path, monkeypatch) -> None:
    """sim_run_transient should report progress via context."""
    netlist = sample_project / "tran.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_transient_analysis(
            self,
            netlist_path,
            output_dir,
            probe_nets,
            *,
            stop_time_s,
            step_time_s,
        ):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="inspice",
                analysis="transient",
                netlist_path=netlist_path,
                x_label="time",
                x_values=[0.0, 1e-3],
                traces=[SimulationTrace(name="out", values=[0.0, 4.8])],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_run_transient",
        {"netlist_path": "tran.cir", "stop_time_s": 1e-3, "step_time_s": 1e-6},
    )
    assert "Transient analysis" in result
    assert "4.8" in result


@pytest.mark.anyio
async def test_sim_run_dc_sweep(sample_project: Path, monkeypatch) -> None:
    """sim_run_dc_sweep should return formatted DC sweep results."""
    netlist = sample_project / "dc.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_dc_sweep(
            self,
            netlist_path,
            output_dir,
            probe_nets,
            *,
            source_ref,
            start_v,
            stop_v,
            step_v,
        ):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="inspice",
                analysis="dc",
                netlist_path=netlist_path,
                x_label="sweep",
                x_values=[0.0, 2.5, 5.0],
                traces=[SimulationTrace(name="out", values=[0.0, 2.45, 4.95])],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_run_dc_sweep",
        {
            "netlist_path": "dc.cir",
            "source_ref": "V1",
            "start_v": 0.0,
            "stop_v": 5.0,
            "step_v": 0.5,
        },
    )
    assert "DC sweep analysis" in result
    assert "4.95" in result


@pytest.mark.anyio
async def test_sim_run_ac_analysis_with_phase(sample_project: Path, monkeypatch) -> None:
    """sim_run_ac_analysis should include phase information when available."""
    netlist = sample_project / "ac.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_ac_analysis(
            self,
            netlist_path,
            output_dir,
            probe_nets,
            *,
            start_freq_hz,
            stop_freq_hz,
            points_per_decade,
        ):
            from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace

            return SimulationResult(
                backend="inspice",
                analysis="ac",
                netlist_path=netlist_path,
                x_label="frequency",
                x_values=[10.0, 1000.0],
                traces=[
                    SimulationTrace(
                        name="out",
                        values=[2.0, 1.0],
                        phase_values=[-90.0, -135.0],
                    ),
                ],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server,
        "sim_run_ac_analysis",
        {
            "netlist_path": "ac.cir",
            "start_freq_hz": 10.0,
            "stop_freq_hz": 1000.0,
            "points_per_decade": 20,
        },
    )
    assert "AC analysis" in result
    assert "phase" in result


@pytest.mark.anyio
async def test_sim_run_operating_point_no_traces(sample_project: Path, monkeypatch) -> None:
    """sim_run_operating_point should handle empty trace results."""
    netlist = sample_project / "op.cir"
    netlist.write_text("* deck\n.end\n", encoding="utf-8")

    class FakeRunner:
        def run_operating_point(self, netlist_path, output_dir, probe_nets):
            from kicad_mcp.utils.ngspice import SimulationResult

            return SimulationResult(
                backend="inspice",
                analysis="operating-point",
                netlist_path=netlist_path,
                traces=[],
            )

    monkeypatch.setattr("kicad_mcp.tools.simulation._runner", lambda: FakeRunner())
    server = build_server("full")
    await call_tool_text(server, "kicad_set_project", {"project_dir": str(sample_project)})

    result = await call_tool_text(
        server, "sim_run_operating_point", {"netlist_path": "op.cir"}
    )
    assert "Operating point analysis" in result
    assert "No node or branch data was returned" in result
