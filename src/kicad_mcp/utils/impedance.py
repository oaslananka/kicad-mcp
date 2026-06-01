"""Quasi-static impedance and propagation helpers for PCB interconnects.

Includes a built-in dielectric material library for common PCB laminates.
"""

from __future__ import annotations

import math
from typing import Literal

TraceType = Literal["microstrip", "stripline", "coplanar"]

# ---------------------------------------------------------------------------
# Dielectric material library
# Each entry: (name, nominal_er, loss_tangent, description)
# ---------------------------------------------------------------------------

DielectricEntry = tuple[str, float, float, str]

DIELECTRIC_LIBRARY: dict[str, DielectricEntry] = {
    "fr4_standard": (
        "FR4 Standard",
        4.40,
        0.020,
        "Standard FR4 glass-epoxy. Suitable for signals up to ~1 GHz.",
    ),
    "fr4_midloss": (
        "FR4 Mid-Loss",
        4.25,
        0.012,
        "Mid-loss FR4 (e.g. Isola IS400). Suitable up to ~3 GHz.",
    ),
    "fr4_lowloss": (
        "FR4 Low-Loss",
        4.00,
        0.005,
        "Low-loss FR4 (e.g. Isola IS410-HL). Suitable up to ~6 GHz.",
    ),
    "ro4350b": (
        "Rogers RO4350B",
        3.48,
        0.0037,
        "High-frequency PTFE-ceramic. Excellent for RF up to 30+ GHz.",
    ),
    "ro4003c": (
        "Rogers RO4003C",
        3.55,
        0.0027,
        "Low-loss hydrocarbon/ceramic. Popular for RF and microwave.",
    ),
    "megtron6": (
        "Panasonic Megtron 6",
        3.60,
        0.002,
        "Ultra-low-loss resin for PCIe Gen4+, 40G Ethernet, DDR5.",
    ),
    "megtron7": (
        "Panasonic Megtron 7",
        3.40,
        0.0015,
        "Next-gen ultra-low-loss for 100G+ applications.",
    ),
    "tuc862": (
        "TUC TU-862 HF",
        3.90,
        0.005,
        "Halogen-free low-loss laminate. Good balance of cost and performance.",
    ),
    "nelco4000_13ep": (
        "Nelco N4000-13EP",
        3.70,
        0.009,
        "Enhanced performance halogen-free. PCIe Gen2/3, USB3.",
    ),
    "ptfe": (
        "PTFE / Teflon",
        2.10,
        0.0002,
        "Lowest loss; very soft, difficult to process. Mm-wave applications.",
    ),
}


def list_dielectric_materials() -> list[dict[str, object]]:
    """Return all available dielectric materials with their properties."""
    return [
        {
            "key": key,
            "name": name,
            "er": er,
            "loss_tangent": loss_tan,
            "description": desc,
        }
        for key, (name, er, loss_tan, desc) in DIELECTRIC_LIBRARY.items()
    ]


def get_dielectric(key: str) -> DielectricEntry:
    """Return (name, er, loss_tangent, description) for a dielectric material key.

    Raises ValueError for unknown keys.
    """
    entry = DIELECTRIC_LIBRARY.get(key.lower())
    if entry is None:
        available = ", ".join(sorted(DIELECTRIC_LIBRARY))
        raise ValueError(f"Unknown dielectric '{key}'. Available materials: {available}")
    return entry


def recommend_dielectric_for_frequency(freq_ghz: float) -> str:
    """Return the recommended dielectric key for the given frequency."""
    if freq_ghz <= 1.0:
        return "fr4_standard"
    if freq_ghz <= 3.0:
        return "fr4_midloss"
    if freq_ghz <= 6.0:
        return "fr4_lowloss"
    if freq_ghz <= 15.0:
        return "ro4350b"
    if freq_ghz <= 40.0:
        return "ro4003c"
    return "ptfe"


_C_METERS_PER_SECOND = 299_792_458.0


def copper_thickness_mm(copper_oz: float) -> float:
    """Convert copper weight in ounces per square foot to thickness in mm."""
    return 0.034798 * copper_oz


def _clamp_ratio(value: float, *, lower: float = 1e-9, upper: float = 1.0 - 1e-9) -> float:
    return max(lower, min(upper, value))


def _elliptic_k(k: float) -> float:
    """Approximate the complete elliptic integral of the first kind."""
    k = _clamp_ratio(abs(k))
    a = 1.0
    b = math.sqrt(1.0 - (k * k))
    for _ in range(12):
        a_next = (a + b) / 2.0
        b_next = math.sqrt(a * b)
        if math.isclose(a_next, b_next, rel_tol=0.0, abs_tol=1e-12):
            a = a_next
            break
        a, b = a_next, b_next
    return math.pi / (2.0 * a)


def _microstrip_effective_width(width_mm: float, height_mm: float, copper_oz: float) -> float:
    thickness_mm = copper_thickness_mm(copper_oz)
    if thickness_mm <= 0.0:
        return width_mm

    thickness_ratio = max(thickness_mm / max(height_mm, 1e-9), 1e-9)
    correction = (thickness_mm / math.pi) * (1.0 + math.log(4.0 * math.e / thickness_ratio))
    return width_mm + max(correction, 0.0)


def _microstrip_impedance(
    width_mm: float,
    height_mm: float,
    er: float,
    copper_oz: float,
) -> tuple[float, float]:
    width_eff_mm = _microstrip_effective_width(width_mm, height_mm, copper_oz)
    ratio = width_eff_mm / height_mm
    correction = 0.04 * ((1.0 - ratio) ** 2) if ratio < 1.0 else 0.0
    effective_er = ((er + 1.0) / 2.0) + (
        ((er - 1.0) / 2.0) * ((1.0 / math.sqrt(1.0 + (12.0 / ratio))) + correction)
    )

    if ratio <= 1.0:
        impedance = (60.0 / math.sqrt(effective_er)) * math.log((8.0 / ratio) + (0.25 * ratio))
    else:
        impedance = (120.0 * math.pi) / (
            math.sqrt(effective_er) * (ratio + 1.393 + (0.667 * math.log(ratio + 1.444)))
        )
    return impedance, effective_er


def _stripline_impedance(
    width_mm: float,
    height_mm: float,
    er: float,
    copper_oz: float,
) -> tuple[float, float]:
    plane_spacing_mm = height_mm * 2.0
    thickness_mm = copper_thickness_mm(copper_oz)
    numerator = 4.0 * plane_spacing_mm
    denominator = 0.67 * math.pi * ((0.8 * width_mm) + thickness_mm)
    impedance = (60.0 / math.sqrt(er)) * math.log(numerator / denominator)
    return impedance, er


def _coplanar_impedance(
    width_mm: float,
    height_mm: float,
    er: float,
    spacing_mm: float,
) -> tuple[float, float]:
    if spacing_mm <= 0.0:
        raise ValueError("Coplanar traces require a positive spacing_mm gap.")

    k = _clamp_ratio(width_mm / (width_mm + (2.0 * spacing_mm)))
    kp = math.sqrt(1.0 - (k * k))
    k1 = _clamp_ratio(
        math.sinh((math.pi * width_mm) / (4.0 * height_mm))
        / math.sinh((math.pi * (width_mm + (2.0 * spacing_mm))) / (4.0 * height_mm))
    )
    k1p = math.sqrt(1.0 - (k1 * k1))

    kk = _elliptic_k(k)
    kkp = _elliptic_k(kp)
    k1k = _elliptic_k(k1)
    k1kp = _elliptic_k(k1p)

    q = (kkp * k1k) / (kk * k1kp)
    effective_er = 1.0 + (((er - 1.0) / 2.0) * q)
    impedance = (30.0 * math.pi / math.sqrt(effective_er)) * (kkp / kk)
    return impedance, effective_er


def trace_impedance(
    width_mm: float,
    height_mm: float,
    er: float,
    *,
    trace_type: TraceType = "microstrip",
    copper_oz: float = 1.0,
    spacing_mm: float = 0.2,
) -> tuple[float, float]:
    """Estimate the single-ended impedance and effective dielectric constant."""
    if width_mm <= 0.0 or height_mm <= 0.0:
        raise ValueError("Trace width and dielectric height must both be positive.")

    normalized = trace_type.casefold()
    if normalized == "microstrip":
        return _microstrip_impedance(width_mm, height_mm, er, copper_oz)
    if normalized == "stripline":
        return _stripline_impedance(width_mm, height_mm, er, copper_oz)
    if normalized == "coplanar":
        return _coplanar_impedance(width_mm, height_mm, er, spacing_mm)
    raise ValueError("Unsupported trace type. Use 'microstrip', 'stripline', or 'coplanar'.")


def differential_impedance(
    width_mm: float,
    height_mm: float,
    spacing_mm: float,
    er: float,
    *,
    trace_type: TraceType = "microstrip",
    copper_oz: float = 1.0,
) -> tuple[float, float]:
    """Estimate edge-coupled differential impedance and effective dielectric constant."""
    single_ended, effective_er = trace_impedance(
        width_mm,
        height_mm,
        er,
        trace_type=trace_type,
        copper_oz=copper_oz,
        spacing_mm=spacing_mm,
    )
    ratio = spacing_mm / height_mm
    normalized = trace_type.casefold()
    if normalized == "stripline":
        coupling = 0.347 * math.exp(-2.9 * ratio)
    else:
        coupling = 0.48 * math.exp(-0.96 * ratio)
    return (2.0 * single_ended) * (1.0 - coupling), effective_er


def solve_width_for_impedance(
    target_ohm: float,
    height_mm: float,
    er: float,
    *,
    trace_type: TraceType = "microstrip",
    copper_oz: float = 1.0,
    spacing_mm: float = 0.2,
) -> float:
    """Solve for a trace width that hits the target single-ended impedance."""
    low_mm = 0.01
    high_mm = max(height_mm * 40.0, 5.0)
    best_width = low_mm
    best_error = float("inf")

    for _ in range(48):
        mid_mm = (low_mm + high_mm) / 2.0
        impedance, _ = trace_impedance(
            mid_mm,
            height_mm,
            er,
            trace_type=trace_type,
            copper_oz=copper_oz,
            spacing_mm=spacing_mm,
        )
        error = abs(impedance - target_ohm)
        if error < best_error:
            best_error = error
            best_width = mid_mm
        if impedance > target_ohm:
            low_mm = mid_mm
        else:
            high_mm = mid_mm

    return best_width


def solve_spacing_for_differential_impedance(
    target_ohm: float,
    width_mm: float,
    height_mm: float,
    er: float,
    *,
    trace_type: TraceType = "microstrip",
    copper_oz: float = 1.0,
) -> float:
    """Solve for a gap that hits the target edge-coupled differential impedance."""
    low_mm = 0.01
    high_mm = max(height_mm * 20.0, width_mm * 10.0, 1.0)
    best_spacing = low_mm
    best_error = float("inf")

    for _ in range(48):
        mid_mm = (low_mm + high_mm) / 2.0
        impedance, _ = differential_impedance(
            width_mm,
            height_mm,
            mid_mm,
            er,
            trace_type=trace_type,
            copper_oz=copper_oz,
        )
        error = abs(impedance - target_ohm)
        if error < best_error:
            best_error = error
            best_spacing = mid_mm
        if impedance < target_ohm:
            low_mm = mid_mm
        else:
            high_mm = mid_mm

    return best_spacing


def propagation_delay_ps_per_mm(effective_er: float) -> float:
    """Estimate propagation delay in picoseconds per millimeter."""
    return (math.sqrt(effective_er) / _C_METERS_PER_SECOND) * 1.0e9


def via_stub_resonance_ghz(stub_length_mm: float, *, er: float = 4.0) -> float:
    """Estimate the quarter-wave via-stub resonance in GHz."""
    if stub_length_mm <= 0.0:
        raise ValueError("Via stub length must be positive.")
    stub_length_m = stub_length_mm / 1_000.0
    resonance_hz = _C_METERS_PER_SECOND / (4.0 * stub_length_m * math.sqrt(er))
    return resonance_hz / 1.0e9


def via_stub_risk_level(stub_length_mm: float, frequency_ghz: float, *, er: float = 4.0) -> str:
    """Classify via-stub risk against the operating frequency."""
    resonance = via_stub_resonance_ghz(stub_length_mm, er=er)
    margin = resonance / frequency_ghz
    if margin < 3.0:
        return "high"
    if margin < 8.0:
        return "medium"
    return "low"


def recommended_decoupling_distance_mm(target_freq_mhz: float) -> float:
    """Return a conservative placement heuristic for high-frequency decouplers."""
    return max(0.5, min(10.0, 500.0 / target_freq_mhz))
