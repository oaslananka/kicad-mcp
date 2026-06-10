#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { exit } from "node:process";

const files = {
  rootPackage: "package.json",
  npmPackage: "packages/mcp-npm/package.json",
  releasePlease: "release-please-config.json",
  publishPython: ".github/workflows/publish-python.yml",
  publishNpm: ".github/workflows/publish-npm.yml",
  docsRelease: "docs/release.md",
  docsPublishing: "docs/publishing.md",
};

function read(path) {
  return readFileSync(path, "utf8");
}

function readJson(path) {
  return JSON.parse(read(path));
}

function expect(condition, message, failures) {
  if (!condition) failures.push(message);
}

function expectIncludes(content, needle, label, failures) {
  expect(content.includes(needle), `${label} must include ${needle}`, failures);
}

function checkPackageNames(failures) {
  const rootPackage = readJson(files.rootPackage);
  const npmPackage = readJson(files.npmPackage);
  const releasePlease = readJson(files.releasePlease);
  expect(
    rootPackage.private === true,
    "root package must remain private",
    failures,
  );
  expect(
    npmPackage.name === "kicad-mcp-pro",
    "npm launcher package must be kicad-mcp-pro",
    failures,
  );
  expect(
    releasePlease.packages["packages/mcp-npm"]["package-name"] ===
      "kicad-mcp-pro",
    "Release Please npm package name must be kicad-mcp-pro",
    failures,
  );
}

function checkWorkflowEvidence(failures) {
  const python = read(files.publishPython);
  const npm = read(files.publishNpm);
  for (const [label, workflow] of Object.entries({ python, npm })) {
    expectIncludes(
      workflow,
      "sha256sum --check",
      `${label} workflow`,
      failures,
    );
    expectIncludes(
      workflow,
      "gh release upload",
      `${label} workflow`,
      failures,
    );
    expectIncludes(
      workflow,
      "attestations: write",
      `${label} workflow`,
      failures,
    );
    expectIncludes(workflow, "actions/attest@", `${label} workflow`, failures);
  }
  expectIncludes(
    python,
    "generate_release_evidence.py generate",
    "python workflow",
    failures,
  );
  expectIncludes(
    python,
    "generate_release_evidence.py verify-pypi",
    "python workflow",
    failures,
  );
  expectIncludes(npm, "npm pack --json", "npm workflow", failures);
  expectIncludes(
    npm,
    "npm sbom --sbom-format cyclonedx",
    "npm workflow",
    failures,
  );
  expectIncludes(npm, "verify-npm-release.mjs", "npm workflow", failures);
}

function checkDocs(failures) {
  const release = read(files.docsRelease);
  const publishing = read(files.docsPublishing);
  for (const surface of ["Python wheel", "npm launcher tarball"]) {
    expectIncludes(release, surface, "release docs", failures);
  }
  for (const registry of [
    "PyPI",
    "npm",
  ]) {
    expectIncludes(publishing, registry, "publishing docs", failures);
  }
}

const failures = [];
checkPackageNames(failures);
checkWorkflowEvidence(failures);
checkDocs(failures);

if (failures.length > 0) {
  console.error("Release provenance check failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  exit(1);
}

console.log("Release provenance check passed.");
