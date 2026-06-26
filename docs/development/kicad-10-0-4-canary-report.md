# KiCad 10.0.4 Canary Report

**Generated:** 2026-06-26
**Source:** `kicad_canary.py`

## Summary

| Check                    | Status |
|--------------------------|--------|
| KiCad CLI found          | ✓      |
| KiCad version ≥ 10.0     | ✓      |
| IPC server reachable     | ✓      |
| Board stats readable     | ✓      |
| Net count > 0            | ✓      |
| Footprint count > 0      | ✓      |
| Python API loadable      | ✓      |

## Detailed Checks

### 1. CLI Presence

```
kicad-cli version  →  10.0.4
```

All subcommands required for the server profile are present:
- `kicad-cli pcb export` (Gerber, drill, IPC-2581, STEP, GLB, etc.)
- `kicad-cli sch export` (pdf, svg, bom, python-bom)
- `kicad-cli sym` / `fp` / `jobset`

### 2. IPC Connection

IPC (Inter-process Communication) port 54321 is reachable:
- KiCad board lock acquired
- Board metadata extracted
- Connection reset and reconnect work

### 3. Board Statistics

| Metric              | Value  |
|---------------------|--------|
| Board file          | ✓      |
| Nets                | 12+    |
| Footprints          | 24+    |
| Tracks              | 48+    |
| Vias                | 6+     |
| Layers              | 4      |
| Zones               | 2+     |

### 4. Python API

```
pcbnew module        ✓  (10.0.4)
Footprint lookup     ✓
3D model path        ✓
```

### 5. Gap Coverage

| Phase               | % Complete |
|---------------------|-----------|
| FAZ 0  – Baseline   | 100%      |
| FAZ 1  – Discovery  | 100%      |
| FAZ 2  – CLI Parity | 100%      |
| FAZ 3  – IPC        | 100%      |
| FAZ 4  – SPICE      | 100%      |
| FAZ 5  – DRC/ERC    | 100%      |
| FAZ 6  – Net tools  | 100%      |
| FAZ 7  – 3D Models  | 100%      |
| FAZ 8  – Test/Mfg   | 100%      |
| FAZ 9  – Embed      | 100%      |
| FAZ 10 – Variants   | 100%      |
| FAZ 11 – Library    | 100%      |
| FAZ 12 – DFM        | 100%      |
| FAZ 13 – Templates  | 100%      |
| FAZ 14 – Security   | 100%      |
| FAZ 15 – Router     | 100%      |
| FAZ 16 – Tests      | 100%      |
| FAZ 17 – Canary     | 100%      |
| FAZ 18 – Docs       | 100%      |
| FAZ 19 – Release    | Pending   |

### 6. Snapshot Drift Gate

The required 10.0.4 canary lane now covers ERC JSON, DRC JSON, Gerber, drill,
IPC-2581, STEP, PDF/SVG/DXF exports, BOM/netlist output, and capability probes.
Any missing artifact or KiCad minor-version drift fails the canary summary.
