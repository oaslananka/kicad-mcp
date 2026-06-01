# Manufacturing Export

1. Run `project_quality_gate()`.
2. If the gate is not `PASS`, stop and fix the reported blocking issues.
3. Run `pcb_transfer_quality_gate()` to confirm named schematic pad nets survived sync.
4. Run DRC and ERC for detailed reports.
5. Confirm the board stats and DFM summary.
6. If you need low-level debug or interchange artifacts, switch to a broader profile
   such as `full` or `minimal`; direct `export_*()` tools do not enforce the full
   project gate.
7. Treat `export_manufacturing_package()` as the final gated release step only after the
   project gate is clean.
