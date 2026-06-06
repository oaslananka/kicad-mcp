# Manufacturing Release Checklist

## Pre-Release
- [ ] Run `project_quality_gate` — all checks pass
- [ ] Run `run_erc` — zero errors
- [ ] Run `run_drc` — zero errors
- [ ] Run `check_design_for_manufacture` — all DFM rules pass

## Export Artifacts
- [ ] Gerber (RS-274X) — all layers
- [ ] NC Drill files — all drill sizes
- [ ] BOM — CSV with MPNs, references, values
- [ ] Pick and Place — centroid file
- [ ] STEP/3D model
- [ ] Schematic PDF
- [ ] PCB PDF (fabrication drawing)
- [ ] IPC-2581 or ODB++ (if required)

## Post-Export
- [ ] Verify Gerber preview
- [ ] Check drill file alignment
- [ ] Validate BOM against schematic
- [ ] Compress export package
- [ ] Generate release manifest

## Waiver Tracking
| Issue | Waiver Reason | Approved By |
|-------|--------------|-------------|
| | | |
