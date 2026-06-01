#!/usr/bin/env node
"use strict";

const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const wrapperPath = path.join(packageRoot, "bin", "kicad-mcp-pro.js");

const result = spawnSync(process.execPath, [wrapperPath, "--help"], {
  cwd: packageRoot,
  encoding: "utf8",
  windowsHide: true,
});

function writeChildOutput() {
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }

  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
}

if (result.error) {
  console.error(
    `Failed to execute npm launcher smoke: ${result.error.message}`,
  );
  process.exit(1);
}

if (result.signal) {
  console.error(
    `npm launcher smoke was interrupted by signal ${result.signal}.`,
  );
  process.exit(1);
}

if (result.status === 0) {
  writeChildOutput();
  process.exit(0);
}

const uvxMissing = result.stderr.includes("uvx was not found on PATH.");
const pythonPackageUnavailable = result.stderr.includes(
  "Publish the matching Python package before publishing this npm wrapper",
);
const knownPrepublishFailure = uvxMissing || pythonPackageUnavailable;

if (!knownPrepublishFailure) {
  writeChildOutput();
  console.error(
    `npm launcher smoke failed with unexpected exit code ${result.status ?? 1}.`,
  );
  process.exit(result.status ?? 1);
}

const reason = uvxMissing
  ? "uvx is not available on PATH"
  : "the matching Python package is not available yet";

console.error(
  [
    `npm launcher smoke skipped: ${reason}.`,
    "This is tolerated during repository builds because the matching Python package",
    "may not be published yet. The wrapper itself still exits non-zero for users.",
  ].join("\n"),
);
process.exit(0);
