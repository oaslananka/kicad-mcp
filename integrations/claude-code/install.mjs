#!/usr/bin/env node
/**
 * Claude Code KiCad MCP installer.
 * Usage: node install.mjs [--scope project|user]
 */
const { execSync } = require("child_process");
const scope = process.argv.includes("--scope")
  ? process.argv[process.argv.indexOf("--scope") + 1]
  : "project";

try {
  execSync(`claude mcp add --transport stdio --scope ${scope} kicad -- uvx kicad-mcp-pro`, {
    stdio: "inherit",
  });
  console.log(`✓ KiCad MCP server added to Claude Code (${scope} scope)`);
} catch (err) {
  console.error("✗ Failed to add KiCad MCP server.");
  console.error("  Make sure Claude Code CLI is installed and authenticated.");
  process.exit(1);
}
