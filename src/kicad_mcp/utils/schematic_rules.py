"""Electrical-design-correctness rules for schematics (issue #197).

KiCad's ERC verifies *connectivity* and pin-type conflicts; it does not verify
*design intent* such as "every supply rail that feeds an IC has a decoupling
capacitor" or "an I2C bus has pull-up resistors". This module is the pure-domain
engine for those professional-practice checks. It takes a connectivity net model
(the structure produced by ``_build_connectivity_groups``) and returns structured
findings, with no KiCad dependency so it is fully unit-testable.

Each net is a mapping with at least::

    {"names": ["VCC", ...], "pins": [{"reference": "U1", "pin": "1", "value": "MCU"}, ...]}

Rules are intentionally conservative (they only fire on strong signals) to keep
false positives low; severities are advisory by default. Add new rules to
``DESIGN_RULES`` — each is a pure function ``(list[NetView]) -> list[Finding]``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# A net as produced by _build_connectivity_groups: names + connected pins.
NetView = Mapping[str, Any]

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

# Ground / return nets are supply-adjacent but never need their own decoupling.
_GROUND_NAMES = frozenset(
    {"GND", "AGND", "DGND", "PGND", "GNDA", "GNDD", "VSS", "VSSA", "EARTH", "0V"}
)

# Tokens that mark a positive supply rail.
_SUPPLY_TOKENS = (
    "VCC",
    "VDD",
    "VBAT",
    "VBUS",
    "VSYS",
    "VIN",
    "AVDD",
    "VDDA",
    "VCCIO",
    "VAUX",
    "VREF",
)

# e.g. +3V3, 3V3, +5V, 5V, +1V8, +12V, 3.3V
_VOLTAGE_RAIL_RE = re.compile(r"^\+?\d+(?:[V.]\d+)?V?$", re.IGNORECASE)
_I2C_TOKEN_RE = re.compile(r"(?:^|[^A-Z])(SDA|SCL)(?:[^A-Z]|\d|$)")


@dataclass(frozen=True)
class Finding:
    """A single design-rule observation."""

    rule_id: str
    severity: str  # "error" | "warning" | "info"
    message: str
    refs: tuple[str, ...] = field(default_factory=tuple)

    def sort_key(self) -> tuple[int, str, str]:
        return (_SEVERITY_ORDER.get(self.severity, 9), self.rule_id, self.message)


def _net_names(net: NetView) -> list[str]:
    return [str(name) for name in net.get("names", []) if str(name).strip()]


def _net_refs(net: NetView, prefix_re: re.Pattern[str]) -> list[str]:
    """Distinct component references on a net whose designator matches ``prefix_re``."""
    seen: list[str] = []
    for pin in net.get("pins", []):
        ref = str(pin.get("reference", ""))
        if prefix_re.match(ref) and ref not in seen:
            seen.append(ref)
    return seen


_RESISTOR_RE = re.compile(r"^R\d")
_CAP_RE = re.compile(r"^C\d")
_IC_RE = re.compile(r"^(?:U|IC)\d")
_CRYSTAL_RE = re.compile(r"^(?:Y|X)\d")
_RESET_TOKENS = frozenset({"RST", "NRST", "RSTN", "POR"})


def is_ground_name(name: str) -> bool:
    return name.strip().upper() in _GROUND_NAMES


def is_supply_rail_name(name: str) -> bool:
    """Return whether a net name denotes a positive supply rail (not ground)."""
    token = name.strip().upper()
    if not token or is_ground_name(token):
        return False
    if token.startswith("+"):
        return True
    if any(supply in token for supply in _SUPPLY_TOKENS):
        return True
    return bool(_VOLTAGE_RAIL_RE.match(token)) and token not in {"0V"}


def is_i2c_name(name: str) -> bool:
    return bool(_I2C_TOKEN_RE.search(name.strip().upper()))


def is_reset_name(name: str) -> bool:
    """Return whether a net name denotes a reset line (typically active-low)."""
    upper = name.strip().upper()
    if "RESET" in upper or "MCLR" in upper:
        return True
    return any(token in _RESET_TOKENS for token in re.split(r"[^A-Z0-9]+", upper))


def merge_nets_by_name(nets: Iterable[NetView]) -> list[dict[str, Any]]:
    """Union nets that share a name so cross-sheet named rails analyze as one net.

    Named nets (power symbols, global/hierarchical labels) are electrically the
    same net across sheets even when they appear as separate connectivity groups
    per page. Unnamed groups are passed through unchanged.
    """
    merged: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for net in nets:
        names = _net_names(net)
        pins = [dict(pin) for pin in net.get("pins", [])]
        if not names:
            passthrough.append({"names": [], "pins": pins})
            continue
        key = min(name.upper() for name in names)
        bucket = merged.setdefault(key, {"names": set(), "pins": []})
        bucket["names"].update(names)
        bucket["pins"].extend(pins)
    result = [{"names": sorted(b["names"]), "pins": b["pins"]} for b in merged.values()]
    result.extend(passthrough)
    return result


def _rule_i2c_pullups(nets: Sequence[NetView]) -> list[Finding]:
    findings: list[Finding] = []
    for net in nets:
        names = _net_names(net)
        i2c_names = [name for name in names if is_i2c_name(name)]
        if not i2c_names:
            continue
        if _net_refs(net, _RESISTOR_RE):
            continue
        label = i2c_names[0]
        ics = _net_refs(net, _IC_RE)
        findings.append(
            Finding(
                rule_id="i2c_pullups",
                severity="warning",
                message=(
                    f"I2C net '{label}' has no pull-up resistor on it. "
                    "I2C SDA/SCL are open-drain and require pull-ups (typically 2.2k-10k) "
                    "to the bus voltage."
                ),
                refs=tuple(ics) or (label,),
            )
        )
    return findings


def _rule_power_rail_decoupling(nets: Sequence[NetView]) -> list[Finding]:
    findings: list[Finding] = []
    for net in nets:
        names = _net_names(net)
        rail_names = [name for name in names if is_supply_rail_name(name)]
        if not rail_names:
            continue
        ics = _net_refs(net, _IC_RE)
        if not ics:
            continue
        if _net_refs(net, _CAP_RE):
            continue
        label = rail_names[0]
        findings.append(
            Finding(
                rule_id="power_rail_decoupling",
                severity="warning",
                message=(
                    f"Supply rail '{label}' feeds {', '.join(ics)} but has no decoupling "
                    "capacitor on the rail. Every IC supply pin should have a local "
                    "decoupling capacitor (typically 100nF per pin)."
                ),
                refs=tuple(ics),
            )
        )
    return findings


def _rule_reset_pullup(nets: Sequence[NetView]) -> list[Finding]:
    findings: list[Finding] = []
    for net in nets:
        names = _net_names(net)
        reset_names = [name for name in names if is_reset_name(name)]
        if not reset_names:
            continue
        # Only flag reset lines that actually reach an IC; ignore stray test points.
        ics = _net_refs(net, _IC_RE)
        if not ics:
            continue
        if _net_refs(net, _RESISTOR_RE):
            continue
        label = reset_names[0]
        findings.append(
            Finding(
                rule_id="reset_pullup",
                severity="warning",
                message=(
                    f"Reset net '{label}' on {', '.join(ics)} has no pull resistor. "
                    "A reset line needs a defined idle level (active-low resets typically "
                    "use a pull-up, often with an RC for noise immunity)."
                ),
                refs=tuple(ics),
            )
        )
    return findings


def _rule_crystal_load_caps(nets: Sequence[NetView]) -> list[Finding]:
    # Collect, per crystal reference, whether any net it touches carries a capacitor.
    crystal_nets: dict[str, bool] = {}
    for net in nets:
        crystals = _net_refs(net, _CRYSTAL_RE)
        if not crystals:
            continue
        has_cap = bool(_net_refs(net, _CAP_RE))
        for crystal in crystals:
            crystal_nets[crystal] = crystal_nets.get(crystal, False) or has_cap
    findings: list[Finding] = []
    for crystal, has_cap in sorted(crystal_nets.items()):
        if has_cap:
            continue
        findings.append(
            Finding(
                rule_id="crystal_load_caps",
                severity="warning",
                message=(
                    f"Crystal/resonator '{crystal}' has no load capacitors on its pins. "
                    "A quartz crystal needs matched load capacitors (value per the crystal's "
                    "specified load capacitance) to oscillate reliably."
                ),
                refs=(crystal,),
            )
        )
    return findings


def _rule_decoupling_count(nets: Sequence[NetView]) -> list[Finding]:
    """Flag ICs with fewer decoupling caps than power pins (partial decoupling).

    Uses pin electrical type: counts ``power_in`` pins that sit on a positive
    supply rail per IC, and the distinct capacitors on those rails. The fully
    undecoupled case (zero caps) is left to ``power_rail_decoupling`` so the two
    rules never double-report; this one catches the 0 < caps < power-pins gap.
    """
    power_pins: dict[str, int] = {}
    rail_caps: dict[str, set[str]] = {}
    for net in nets:
        if not any(is_supply_rail_name(name) for name in _net_names(net)):
            continue
        caps_on_net = set(_net_refs(net, _CAP_RE))
        ics_on_net: set[str] = set()
        for pin in net.get("pins", []):
            ref = str(pin.get("reference", ""))
            if _IC_RE.match(ref) and str(pin.get("etype", "")) == "power_in":
                power_pins[ref] = power_pins.get(ref, 0) + 1
                ics_on_net.add(ref)
        for ic in ics_on_net:
            rail_caps.setdefault(ic, set()).update(caps_on_net)

    findings: list[Finding] = []
    for ic in sorted(power_pins):
        pins = power_pins[ic]
        caps = len(rail_caps.get(ic, set()))
        if 0 < caps < pins:
            findings.append(
                Finding(
                    rule_id="decoupling_count",
                    severity="warning",
                    message=(
                        f"{ic} has {pins} supply pin(s) but only {caps} decoupling "
                        "capacitor(s) on its rails. Aim for roughly one ~100nF "
                        "capacitor per power pin, placed close to the pin."
                    ),
                    refs=(ic,),
                )
            )
    return findings


# Registry of active rules. Append new pure ``(nets) -> [Finding]`` callables here.
DESIGN_RULES: tuple[Callable[[Sequence[NetView]], list[Finding]], ...] = (
    _rule_i2c_pullups,
    _rule_power_rail_decoupling,
    _rule_reset_pullup,
    _rule_crystal_load_caps,
    _rule_decoupling_count,
)


def run_schematic_design_rules(nets: Iterable[NetView]) -> list[Finding]:
    """Run every design rule over the (name-merged) net model and return findings."""
    merged = merge_nets_by_name(nets)
    findings: list[Finding] = []
    for rule in DESIGN_RULES:
        findings.extend(rule(merged))
    findings.sort(key=Finding.sort_key)
    return findings
