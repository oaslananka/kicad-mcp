"""Power-integrity and thermal heuristics for practical PCB review."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Protocol, cast

from kipy.board_types import Net, Zone
from kipy.geometry import PolyLineNode, Vector2
from kipy.proto.board.board_types_pb2 import BoardLayer
from mcp.server.fastmcp import FastMCP

from ..config import get_config
from ..connection import board_transaction, get_board
from ..models.common import _FootprintLike
from ..models.power_integrity import (
    CopperWeightCheckInput,
    DecouplingRecommendationInput,
    PowerPlaneInput,
    ThermalPourInput,
    ThermalViaInput,
    VoltageDropInput,
)
from ..utils.impedance import copper_thickness_mm, recommended_decoupling_distance_mm
from ..utils.layers import resolve_layer
from ..utils.pdn_mesh import PdnDecouplingCap, PdnLoad, PdnMesh
from ..utils.units import _coord_nm, mm_to_mil, mm_to_nm, nm_to_mm

_COPPER_RESISTIVITY_OHM_M = 1.724e-8
_TEMPERATURE_COEFFICIENT = 0.0039
_DEFAULT_BOARD_THICKNESS_MM = 1.6


class _TrackLike(Protocol):
    start: object
    end: object
    width: int
    layer: BoardLayer.ValueType
    net: object


class _ZoneLike(Protocol):
    name: str
    net: object
    layers: Iterable[BoardLayer.ValueType]


def _net(name: str) -> Net:
    net = Net()
    net.name = name
    return net


def _track_length_mm(track: _TrackLike) -> float:
    dx = _coord_nm(track.end, "x") - _coord_nm(track.start, "x")
    dy = _coord_nm(track.end, "y") - _coord_nm(track.start, "y")
    return math.hypot(dx, dy) / 1_000_000.0


def _matching_tracks(net_name: str) -> list[_TrackLike]:
    matches: list[_TrackLike] = []
    for track in cast(list[_TrackLike], list(get_board().get_tracks())):
        track_net = str(getattr(getattr(track, "net", None), "name", "") or "")
        if track_net == net_name:
            matches.append(track)
    return matches


def _board_thickness_mm() -> float:
    stackup = get_board().get_stackup()
    total_nm = sum(int(getattr(layer, "thickness", 0)) for layer in getattr(stackup, "layers", []))
    if total_nm <= 0:
        return _DEFAULT_BOARD_THICKNESS_MM
    return nm_to_mm(total_nm)


def _layer_copper_thickness_mm(layer_value: BoardLayer.ValueType) -> float:
    stackup = get_board().get_stackup()
    for layer in getattr(stackup, "layers", []):
        if getattr(layer, "layer", None) == layer_value:
            thickness_nm = int(getattr(layer, "thickness", 0))
            if thickness_nm > 0:
                return nm_to_mm(thickness_nm)
    return copper_thickness_mm(1.0)


def _board_footprints() -> list[_FootprintLike]:
    return cast(list[_FootprintLike], list(get_board().get_footprints()))


def _footprint_reference(footprint: _FootprintLike) -> str:
    return str(footprint.reference_field.text.value)


def _footprint_value(footprint: _FootprintLike) -> str:
    return str(footprint.value_field.text.value)


def _footprint_position_mm(footprint: _FootprintLike) -> tuple[float, float]:
    return (
        nm_to_mm(_coord_nm(footprint.position, "x")),
        nm_to_mm(_coord_nm(footprint.position, "y")),
    )


def _nearest_capacitors(reference: str) -> list[tuple[str, float, str]]:
    footprints = _board_footprints()
    anchor = next(
        (footprint for footprint in footprints if _footprint_reference(footprint) == reference),
        None,
    )
    if anchor is None:
        return []

    source_x_mm, source_y_mm = _footprint_position_mm(anchor)
    matches: list[tuple[str, float, str]] = []
    for footprint in footprints:
        candidate_ref = _footprint_reference(footprint)
        if candidate_ref == reference or not candidate_ref.upper().startswith("C"):
            continue
        x_mm, y_mm = _footprint_position_mm(footprint)
        matches.append(
            (
                candidate_ref,
                math.hypot(source_x_mm - x_mm, source_y_mm - y_mm),
                _footprint_value(footprint),
            )
        )
    return sorted(matches, key=lambda item: item[1])


def _track_resistance_ohm(
    trace_width_mm: float,
    trace_length_mm: float,
    copper_oz: float,
    ambient_temp_c: float = 25.0,
) -> float:
    thickness_m = copper_thickness_mm(copper_oz) / 1_000.0
    width_m = trace_width_mm / 1_000.0
    length_m = trace_length_mm / 1_000.0
    area_m2 = width_m * thickness_m
    base_resistance = _COPPER_RESISTIVITY_OHM_M * length_m / area_m2
    return base_resistance * (1.0 + (_TEMPERATURE_COEFFICIENT * max(ambient_temp_c - 20.0, 0.0)))


def _ipc_current_capacity_a(
    width_mm: float,
    copper_thickness_mm_value: float,
    *,
    external: bool,
    max_temp_rise_c: float,
) -> float:
    area_mil_sq = mm_to_mil(width_mm) * mm_to_mil(copper_thickness_mm_value)
    k = 0.048 if external else 0.024
    return float(k * (max_temp_rise_c**0.44) * (area_mil_sq**0.725))


def _required_width_mm(
    expected_current_a: float,
    copper_thickness_mm_value: float,
    *,
    external: bool,
    max_temp_rise_c: float,
) -> float:
    k = 0.048 if external else 0.024
    area_mil_sq = (expected_current_a / (k * (max_temp_rise_c**0.44))) ** (1.0 / 0.725)
    return float(area_mil_sq / mm_to_mil(copper_thickness_mm_value) * 0.0254)


def _edge_cuts_bounds() -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for shape in get_board().get_shapes():
        if getattr(shape, "layer", None) != BoardLayer.BL_Edge_Cuts:
            continue
        for attr in ("start", "end", "top_left", "bottom_right", "center", "radius_point"):
            point = getattr(shape, attr, None)
            if point is None:
                continue
            xs.append(nm_to_mm(_coord_nm(point, "x")))
            ys.append(nm_to_mm(_coord_nm(point, "y")))
    if xs and ys:
        return min(xs), min(ys), max(xs), max(ys)
    return None


def _footprint_bounds() -> tuple[float, float, float, float] | None:
    footprints = _board_footprints()
    if not footprints:
        return None
    xs = [_footprint_position_mm(footprint)[0] for footprint in footprints]
    ys = [_footprint_position_mm(footprint)[1] for footprint in footprints]
    margin_mm = 5.0
    return min(xs) - margin_mm, min(ys) - margin_mm, max(xs) + margin_mm, max(ys) + margin_mm


def _plane_bounds() -> tuple[float, float, float, float] | None:
    return _edge_cuts_bounds() or _footprint_bounds()


def _zone_already_exists(net_name: str, layer: BoardLayer.ValueType) -> bool:
    for zone in cast(list[_ZoneLike], list(get_board().get_zones())):
        zone_net = str(getattr(getattr(zone, "net", None), "name", "") or "")
        zone_layers = list(getattr(zone, "layers", []))
        if zone_net == net_name and layer in zone_layers:
            return True
    return False


def register(mcp: FastMCP) -> None:
    """Register power-integrity and thermal tools."""

    @mcp.tool()
    def pdn_calculate_voltage_drop(
        current_a: float,
        trace_width_mm: float,
        trace_length_mm: float,
        copper_oz: float = 1.0,
    ) -> str:
        """Estimate DC voltage drop and trace resistance."""
        payload = VoltageDropInput(
            current_a=current_a,
            trace_width_mm=trace_width_mm,
            trace_length_mm=trace_length_mm,
            copper_oz=copper_oz,
        )
        resistance_ohm = _track_resistance_ohm(
            payload.trace_width_mm,
            payload.trace_length_mm,
            payload.copper_oz,
        )
        drop_v = payload.current_a * resistance_ohm
        current_density_a_per_mm2 = payload.current_a / (
            payload.trace_width_mm * copper_thickness_mm(payload.copper_oz)
        )
        return "\n".join(
            [
                "PDN voltage-drop estimate:",
                f"- Current: {payload.current_a:.3f} A",
                f"- Trace width: {payload.trace_width_mm:.3f} mm",
                f"- Trace length: {payload.trace_length_mm:.3f} mm",
                f"- Copper: {payload.copper_oz:.2f} oz",
                f"- Estimated resistance: {resistance_ohm:.5f} ohm",
                f"- Estimated voltage drop: {drop_v * 1_000.0:.2f} mV",
                f"- Estimated current density: {current_density_a_per_mm2:.2f} A/mm^2",
            ]
        )

    @mcp.tool()
    def check_power_integrity(
        net_name: str,
        source_ref: str,
        load_refs: list[str],
        trace_width_mm: float,
        load_current_a: float = 0.1,
        trace_length_mm: float = 100.0,
        copper_weight_oz: float = 1.0,
        nominal_voltage_v: float = 3.3,
        frequency_points_hz: list[float] | None = None,
        decoupling_caps_uf: list[float] | None = None,
        target_impedance_ohm: float | None = None,
        decoupling_esr_mohm: float = 20.0,
        decoupling_esl_nh: float = 1.0,
    ) -> str:
        """Run a lightweight PDN mesh voltage-drop check for a power net."""
        loads = [
            PdnLoad(
                ref=reference,
                current_a=load_current_a,
                distance_mm=trace_length_mm * ((index + 1) / max(1, len(load_refs))),
            )
            for index, reference in enumerate(load_refs)
        ]
        result = PdnMesh().solve(
            net_name=net_name,
            source_ref=source_ref,
            loads=loads,
            trace_width_mm=trace_width_mm,
            copper_weight_oz=copper_weight_oz,
            nominal_voltage_v=nominal_voltage_v,
            frequency_points_hz=frequency_points_hz,
            decoupling_caps=[
                PdnDecouplingCap(
                    ref=f"C{index}",
                    capacitance_f=value_uf * 1e-6,
                    esr_ohm=decoupling_esr_mohm / 1000.0,
                    esl_h=decoupling_esl_nh * 1e-9,
                )
                for index, value_uf in enumerate(decoupling_caps_uf or [], start=1)
            ],
            target_impedance_ohm=target_impedance_ohm,
        )
        lines = [
            "PDN mesh check:",
            f"- Net: {net_name}",
            f"- Source: {source_ref}",
            f"- Max drop: {result.max_drop_mv:.2f} mV",
            f"- Violations: {len(result.violations)}",
        ]
        lines.extend(f"- {ref}: {drop:.2f} mV" for ref, drop in result.drops_mv.items())
        lines.extend(f"- FAIL: {item}" for item in result.violations)
        if result.impedance_ohm:
            lines.append(f"- Max AC impedance: {result.max_impedance_ohm:.4f} ohm")
            for frequency_hz, impedance in result.impedance_ohm.items():
                lines.append(f"- Z({frequency_hz:.0f} Hz): {impedance:.4f} ohm")
        lines.extend(f"- IMPEDANCE FAIL: {item}" for item in result.impedance_violations)
        lines.extend(f"- Recommendation: {item}" for item in result.recommendations)
        return "\n".join(lines)

    @mcp.tool()
    def pdn_recommend_decoupling_caps(
        ic_refs: list[str],
        vcc_net: str,
        supply_voltage_v: float,
        target_ripple_mv: float = 20.0,
    ) -> str:
        """Recommend local and bulk decoupling from a simple PDN heuristic."""
        payload = DecouplingRecommendationInput(
            ic_refs=ic_refs,
            vcc_net=vcc_net,
            supply_voltage_v=supply_voltage_v,
            target_ripple_mv=target_ripple_mv,
        )
        scale = max(0.5, min(5.0, 20.0 / payload.target_ripple_mv))
        bulk_uf = max(4.7, round(4.7 * len(payload.ic_refs) * scale, 1))

        lines = [
            f"Decoupling recommendation for {payload.vcc_net}:",
            f"- Supply voltage: {payload.supply_voltage_v:.3f} V",
            f"- Target ripple: {payload.target_ripple_mv:.2f} mV",
            "- Baseline local decoupler per IC: 100 nF X7R placed at the power pin",
            f"- Shared bulk recommendation near rail entry: {bulk_uf:.1f} uF low-ESR",
        ]
        for reference in payload.ic_refs[: get_config().max_items_per_response]:
            nearby = _nearest_capacitors(reference)
            recommendation_mm = recommended_decoupling_distance_mm(200.0)
            if nearby:
                best_ref, best_distance_mm, best_value = nearby[0]
                verdict = "OK" if best_distance_mm <= recommendation_mm else "MOVE CLOSER"
                lines.append(
                    f"- {reference}: nearest capacitor is {best_ref} ({best_value or 'unknown'}) "
                    f"at {best_distance_mm:.3f} mm [{verdict}]"
                )
            else:
                lines.append(
                    f"- {reference}: add one 100 nF local cap within {recommendation_mm:.2f} mm"
                )
        return "\n".join(lines)

    @mcp.tool()
    def pdn_check_copper_weight(
        net_name: str,
        expected_current_a: float,
        ambient_temp_c: float = 25.0,
        max_temp_rise_c: float = 10.0,
    ) -> str:
        """Check whether the routed copper for a net looks sufficient for the load current."""
        payload = CopperWeightCheckInput(
            net_name=net_name,
            expected_current_a=expected_current_a,
            ambient_temp_c=ambient_temp_c,
            max_temp_rise_c=max_temp_rise_c,
        )
        tracks = _matching_tracks(payload.net_name)
        if not tracks:
            return f"No routed tracks were found for net '{payload.net_name}'."

        min_width_mm = min(nm_to_mm(int(track.width)) for track in tracks)
        avg_width_mm = sum(nm_to_mm(int(track.width)) for track in tracks) / len(tracks)
        longest_track = max(tracks, key=_track_length_mm)
        copper_thickness = _layer_copper_thickness_mm(longest_track.layer)
        external = longest_track.layer in {BoardLayer.BL_F_Cu, BoardLayer.BL_B_Cu}
        capacity_a = _ipc_current_capacity_a(
            min_width_mm,
            copper_thickness,
            external=external,
            max_temp_rise_c=payload.max_temp_rise_c,
        )
        required_width_mm = _required_width_mm(
            payload.expected_current_a,
            copper_thickness,
            external=external,
            max_temp_rise_c=payload.max_temp_rise_c,
        )
        verdict = "PASS" if capacity_a >= payload.expected_current_a else "WARN"

        return "\n".join(
            [
                f"Copper weight check for {payload.net_name} ({verdict}):",
                f"- Routed track count: {len(tracks)}",
                f"- Minimum width: {min_width_mm:.3f} mm",
                f"- Average width: {avg_width_mm:.3f} mm",
                f"- Copper thickness: {copper_thickness:.4f} mm",
                f"- Assumed temperature rise limit: {payload.max_temp_rise_c:.1f} C",
                f"- Estimated conservative current capacity: {capacity_a:.3f} A",
                f"- Expected current: {payload.expected_current_a:.3f} A",
                f"- Recommended minimum width: {required_width_mm:.3f} mm",
                "- Uses a conservative IPC-style current-carrying estimate for quick review.",
            ]
        )

    @mcp.tool()
    def pdn_generate_power_plane(net_name: str, layer: str, clearance_mm: float = 0.5) -> str:
        """Generate a rectangular copper plane on the requested copper layer."""
        payload = PowerPlaneInput(net_name=net_name, layer=layer, clearance_mm=clearance_mm)
        layer_value = resolve_layer(payload.layer)
        if layer_value not in {BoardLayer.BL_F_Cu, BoardLayer.BL_B_Cu}:
            return "Power plane generation currently supports only F_Cu and B_Cu."
        if _zone_already_exists(payload.net_name, layer_value):
            return f"A copper zone for '{payload.net_name}' already exists on {payload.layer}."

        bounds = _plane_bounds()
        if bounds is None:
            return (
                "Could not determine board bounds. Add an Edge.Cuts outline or at least one "
                "footprint before generating a power plane."
            )
        x1_mm, y1_mm, x2_mm, y2_mm = bounds
        zone = Zone()
        zone.name = f"{payload.net_name}_PLANE"
        zone.net = _net(payload.net_name)
        zone.proto.layers.append(layer_value)
        zone.clearance = mm_to_nm(payload.clearance_mm)
        zone.min_thickness = mm_to_nm(0.25)
        zone.proto.outline.polygons.add()
        outline = zone.outline.outline
        outline.closed = True
        points = [
            (x1_mm + payload.clearance_mm, y1_mm + payload.clearance_mm),
            (x2_mm - payload.clearance_mm, y1_mm + payload.clearance_mm),
            (x2_mm - payload.clearance_mm, y2_mm - payload.clearance_mm),
            (x1_mm + payload.clearance_mm, y2_mm - payload.clearance_mm),
        ]
        for x_mm, y_mm in points:
            outline.append(PolyLineNode.from_point(Vector2.from_xy_mm(x_mm, y_mm)))

        with board_transaction() as board:
            board.create_items([zone])
            board.refill_zones(block=True, max_poll_seconds=60.0)

        return (
            f"Generated a copper plane for '{payload.net_name}' on {payload.layer} "
            f"with {payload.clearance_mm:.3f} mm clearance."
        )

    @mcp.tool()
    def thermal_calculate_via_count(
        power_w: float | None = None,
        package_power_w: float | None = None,
        ambient_c: float = 25.0,
        max_junction_c: float = 125.0,
        theta_ja_deg_c_w: float = 40.0,
        via_diameter_mm: float = 0.3,
        thermal_resistance_target: float = 5.0,
    ) -> str:
        """Estimate thermal via count from package heat and board thermal resistance."""
        payload = ThermalViaInput(
            power_w=power_w,
            package_power_w=package_power_w,
            ambient_c=ambient_c,
            max_junction_c=max_junction_c,
            theta_ja_deg_c_w=theta_ja_deg_c_w,
            via_diameter_mm=via_diameter_mm,
            thermal_resistance_target=thermal_resistance_target,
        )
        effective_power_w = payload.package_power_w or payload.power_w
        if effective_power_w is None:
            raise ValueError(
                "Thermal via power is missing. Provide either 'package_power_w' for the "
                "package thermal-envelope workflow or legacy 'power_w'."
            )
        if payload.max_junction_c <= payload.ambient_c:
            raise ValueError("max_junction_c must be greater than ambient_c.")

        allowed_total_theta = (payload.max_junction_c - payload.ambient_c) / effective_power_w
        if payload.package_power_w is not None and payload.theta_ja_deg_c_w > allowed_total_theta:
            # Parallel thermal paths: 1/R_allowed = 1/R_package + 1/R_vias.
            required_via_network_theta = 1.0 / (
                (1.0 / allowed_total_theta) - (1.0 / payload.theta_ja_deg_c_w)
            )
        else:
            required_via_network_theta = min(
                payload.thermal_resistance_target,
                allowed_total_theta,
            )

        # Rule of thumb used by many thermal-via calculators: one 0.3 mm plated via in
        # 1 oz copper contributes roughly 100 C/W. Scale conservatively by via diameter
        # and board thickness so larger/shorter barrels lower resistance.
        single_via_theta = (
            100.0
            * (0.3 / payload.via_diameter_mm)
            * (_board_thickness_mm() / _DEFAULT_BOARD_THICKNESS_MM)
        )
        via_count = max(1, math.ceil(single_via_theta / required_via_network_theta))
        delta_temp_c = effective_power_w * required_via_network_theta

        return "\n".join(
            [
                "Thermal via estimate:",
                f"- Power to spread: {effective_power_w:.3f} W",
                (
                    f"- Ambient / max junction: {payload.ambient_c:.1f} C / "
                    f"{payload.max_junction_c:.1f} C"
                ),
                f"- Package theta JA: {payload.theta_ja_deg_c_w:.2f} C/W",
                f"- Via diameter: {payload.via_diameter_mm:.3f} mm",
                f"- Board thickness used: {_board_thickness_mm():.3f} mm",
                "- Single-via rule of thumb: 0.3 mm, 1 oz copper is approximately 100 C/W",
                f"- Single-via thermal resistance estimate: {single_via_theta:.2f} C/W",
                f"- Required via-network resistance: {required_via_network_theta:.2f} C/W",
                f"- Required via count: {via_count}",
                f"- Target temperature rise at the interface: {delta_temp_c:.2f} C",
            ]
        )

    @mcp.tool()
    def thermal_check_copper_pour(
        net_name: str,
        expected_power_w: float,
        preferred_layer: str = "auto",
    ) -> str:
        """Check whether the board already has copper pour support for the net."""
        payload = ThermalPourInput(
            net_name=net_name,
            expected_power_w=expected_power_w,
            preferred_layer=preferred_layer,
        )
        zones = [
            zone
            for zone in cast(list[_ZoneLike], list(get_board().get_zones()))
            if str(getattr(getattr(zone, "net", None), "name", "") or "") == payload.net_name
        ]
        if not zones:
            return (
                f"No copper pours were found for net '{payload.net_name}'. "
                "Add a pour or plane for thermal spreading before release."
            )

        verdict = "PASS" if len(zones) >= max(1, math.ceil(payload.expected_power_w)) else "WARN"
        lines = [
            f"Thermal copper-pour review for {payload.net_name} ({verdict}):",
            f"- Expected dissipation: {payload.expected_power_w:.3f} W",
            f"- Matching pours / planes: {len(zones)}",
        ]
        for zone in zones[: get_config().max_items_per_response]:
            zone_layers = ",".join(BoardLayer.Name(layer) for layer in getattr(zone, "layers", []))
            lines.append(f"- {zone.name or '(unnamed)'} on {zone_layers or '(unknown layers)'}")
        if verdict == "WARN":
            lines.append("- Consider a wider pour, more copper area, and stitched thermal vias.")
        return "\n".join(lines)
