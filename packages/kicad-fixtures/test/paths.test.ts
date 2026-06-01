import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  getKicadFixture,
  KICAD_EXPECTED_FILES,
  KICAD_FIXTURE_IDS,
  findKicadFixturesPackageRoot,
  kicadExpectedPath,
  kicadFixturePath,
  kicadFixturesRoot,
  loadKicadFixtureManifest,
} from "../src/index";

test("loads the shared KiCad fixture manifest with stable semantic IDs", () => {
  const manifest = loadKicadFixtureManifest();

  assert.equal(manifest.trackingIssue, "OASLANA-53");
  assert.equal(manifest.githubIssue, 54);
  assert.deepEqual(
    manifest.fixtures.map((fixture) => fixture.id),
    [...KICAD_FIXTURE_IDS],
  );
  assert.deepEqual(manifest.expectedFiles, [...KICAD_EXPECTED_FILES]);
});

test("resolves fixture and expected golden paths from package root", () => {
  const packageRoot = findKicadFixturesPackageRoot();
  const fixture = getKicadFixture("clean-led-kicad10");

  assert.equal(
    kicadFixturesRoot(packageRoot),
    path.join(packageRoot, "fixtures"),
  );
  assert.equal(
    kicadFixturePath("clean-led-kicad10", fixture.projectFile),
    path.join(
      packageRoot,
      "fixtures",
      "clean-led-kicad10",
      fixture.projectFile,
    ),
  );
  assert.equal(
    kicadExpectedPath("clean-led-kicad10", "project-tree.snapshot.json"),
    path.join(
      packageRoot,
      "expected",
      "clean-led-kicad10",
      "project-tree.snapshot.json",
    ),
  );
  assert.ok(fs.existsSync(kicadFixturePath("clean-led-kicad10")));
  assert.ok(fs.existsSync(kicadExpectedPath("clean-led-kicad10")));
});

test("exposes KiCad 10.0.3 regression fixture coverage metadata", () => {
  const fixture = getKicadFixture("kicad-10-0-3-regressions");

  assert.equal(fixture.regressionCoverage?.kicadVersion, "10.0.3");
  assert.ok(fixture.tags.includes("kicad10.0.3"));
  assert.deepEqual(fixture.regressionCoverage?.cli, [
    "drc_elapsed_or_status_output_parsing",
    "erc_output_shape_stability",
    "pcb_export_pdf_property_popup_suppression_probe",
  ]);
  assert.deepEqual(fixture.regressionCoverage?.importers, [
    "pads_import_edge_case_fixture",
    "allegro_import_capability_probe",
  ]);
  assert.deepEqual(fixture.regressionCoverage?.pcb, [
    "custom_padstack_non_copper_layer_fixture",
  ]);
  assert.ok(
    fs.existsSync(
      kicadFixturePath(
        "kicad-10-0-3-regressions",
        "importers",
        "pads-zone-intersection.asc",
      ),
    ),
  );
});

test("throws a clear error for unknown fixture IDs", () => {
  assert.throws(
    () => getKicadFixture("missing-fixture"),
    /Unknown KiCad fixture id: missing-fixture/u,
  );
});
