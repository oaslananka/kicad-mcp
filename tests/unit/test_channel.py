"""High-speed channel (insertion-loss / eye) physics and ngspice seam (work order P3-T3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.utils.channel import (
    ChannelSpec,
    bandwidth_3db_hz,
    build_rlgc_ladder_deck,
    closed_form_channel_metrics,
    insertion_loss_db,
    insertion_loss_from_ac,
    nyquist_frequency_hz,
    simulate_channel_insertion_loss,
)
from kicad_mcp.utils.ngspice import SimulationResult, SimulationTrace


def _spec(**overrides: float) -> ChannelSpec:
    base = dict(length_mm=300.0, z0_ohm=50.0, data_rate_gbps=10.0)
    base.update(overrides)
    return ChannelSpec(**base)  # type: ignore[arg-type]


def test_closed_form_channel_metrics_are_physical() -> None:
    metrics = closed_form_channel_metrics(_spec())
    # 10 Gbps -> 5 GHz Nyquist.
    assert metrics.nyquist_hz == pytest.approx(5.0e9)
    # A 300 mm FR4-class channel has several dB of loss at 5 GHz.
    assert 5.0 < metrics.insertion_loss_nyquist_db < 20.0
    # Eye ratio is a positive fraction <= 1 and consistent with the loss.
    assert 0.0 < metrics.eye_height_ratio < 1.0
    assert metrics.eye_height_v == pytest.approx(metrics.eye_height_ratio)  # amplitude 1 V
    assert 0.0 < metrics.bandwidth_3db_hz < metrics.nyquist_hz
    assert metrics.source == "closed-form"


def test_insertion_loss_increases_with_length_and_rate() -> None:
    short = closed_form_channel_metrics(_spec(length_mm=50.0)).insertion_loss_nyquist_db
    long = closed_form_channel_metrics(_spec(length_mm=300.0)).insertion_loss_nyquist_db
    assert long > short

    slow = closed_form_channel_metrics(_spec(data_rate_gbps=2.0)).insertion_loss_nyquist_db
    fast = closed_form_channel_metrics(_spec(data_rate_gbps=16.0)).insertion_loss_nyquist_db
    assert fast > slow


def test_loss_components_are_nonnegative_and_grow_with_frequency() -> None:
    spec = _spec()
    assert insertion_loss_db(spec, 0.0) == 0.0
    low = insertion_loss_db(spec, 1.0e9)
    high = insertion_loss_db(spec, 1.0e10)
    assert 0.0 < low < high
    assert nyquist_frequency_hz(spec) == pytest.approx(5.0e9)
    assert bandwidth_3db_hz(spec) > 0.0


def test_insertion_loss_from_ac_interpolates_and_clamps() -> None:
    freqs = [1.0e9, 5.0e9, 1.0e10]
    # Flat half-amplitude transfer is the matched-through reference: 0 dB loss.
    assert insertion_loss_from_ac(freqs, [0.5, 0.5, 0.5], 5.0e9) == pytest.approx(0.0, abs=1e-9)
    # Halving the amplitude is ~6.02 dB of loss.
    assert insertion_loss_from_ac(freqs, [0.25, 0.25, 0.25], 5.0e9) == pytest.approx(
        6.0206, abs=1e-3
    )
    # Target below/above the swept band clamps to the endpoints.
    assert insertion_loss_from_ac(freqs, [0.5, 0.4, 0.1], 1.0e6) == pytest.approx(0.0, abs=1e-9)
    with pytest.raises(ValueError):
        insertion_loss_from_ac([], [], 1.0e9)


def test_rlgc_ladder_deck_is_well_formed() -> None:
    deck = build_rlgc_ladder_deck(_spec(), segments=8)
    assert deck.startswith("* KiCad MCP Pro high-speed channel")
    assert "Vin src 0 AC 1" in deck
    assert "Rsrc src n0" in deck
    assert "Rload n8 0" in deck
    assert deck.strip().endswith(".end")
    # One R, L, G, C per segment.
    for index in range(8):
        assert f"\nR{index} " in deck
        assert f"\nL{index} " in deck
        assert f"\nG{index} " in deck
        assert f"\nC{index} " in deck


class _FakeRunner:
    """Minimal NgspiceRunner stand-in returning a canned AC sweep."""

    def __init__(self, magnitude: float) -> None:
        self.magnitude = magnitude

    def run_ac_analysis(
        self,
        netlist_path: Path,
        output_dir: Path,
        probe_nets: list[str],
        *,
        start_freq_hz: float,
        stop_freq_hz: float,
        points_per_decade: int,
    ) -> SimulationResult:
        node = probe_nets[0]
        freqs = [start_freq_hz, (start_freq_hz + stop_freq_hz) / 2.0, stop_freq_hz]
        return SimulationResult(
            backend="ngspice-cli",
            analysis="ac",
            netlist_path=netlist_path,
            x_label="frequency",
            x_values=freqs,
            traces=[SimulationTrace(name=node, values=[self.magnitude] * len(freqs))],
        )


class _BrokenRunner:
    def run_ac_analysis(self, *args: object, **kwargs: object) -> SimulationResult:
        raise RuntimeError("ngspice exploded")


def test_simulate_channel_uses_measured_insertion_loss(tmp_path: Path) -> None:
    metrics = simulate_channel_insertion_loss(_spec(), _FakeRunner(0.25), tmp_path)  # type: ignore[arg-type]
    assert metrics is not None
    assert metrics.source == "ngspice"
    assert metrics.insertion_loss_nyquist_db == pytest.approx(6.0206, abs=1e-2)
    assert (tmp_path / "channel_input.cir").exists()


def test_simulate_channel_degrades_to_none_on_failure(tmp_path: Path) -> None:
    assert simulate_channel_insertion_loss(_spec(), _BrokenRunner(), tmp_path) is None  # type: ignore[arg-type]
