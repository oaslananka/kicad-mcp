# Schematic To PCB

1. Capture the schematic.
   Use `sch_find_free_placement()` before adding new parts when you need collision-free coordinates, and pass `keepout_regions` if parts must stay out of reserved areas.
   Use `sch_get_bounding_boxes()` to inspect occupied sheet regions with pin-aware symbol extents.
2. Assign footprints.
3. Export a netlist.
   If the schematic needs cleanup first, run `sch_auto_place_functional()` to group connectors, MCU blocks, sensors, and UI parts. Set `anchor_ref` to keep already-reviewed symbols fixed, and tune inter-group spacing with `project_set_design_intent(functional_spacing_mm=...)`.
   Use `sch_get_template_info()` to inspect bundled subcircuit templates, including their declared left/right pin lists, before instantiating them.
4. Place footprints and route.
   Use `pcb_auto_place_force_directed()` for a headless spring-layout pass when you want a deterministic starting point before manual polish. The tool now supports `keepout_regions`, `grid_mm`, and a `max_seconds` budget so automated placement stays bounded and respects reserved regions.
   Review `pcb_score_placement()` after placement; it now reports critical-net Manhattan proxy length and thermal-hotspot proximity in addition to the existing intent-aware checks.
   For external autorouting, stage DSN/SES with `route_export_dsn()`, `route_autoroute_freerouting()`, and `route_import_ses()`. FreeRouting runs Docker-first when available using the pinned `ghcr.io/freerouting/freerouting:2.1.0` image, falls back to a configured JAR, and reports routed percentage, pass count, wall time, and stdout tail.
5. Validate and export.
