#!/usr/bin/env node
/**
 * Codex CLI KiCad MCP installer.
 * Usage: node install.mjs [--scope project|user]
 */
const fs = require("fs");
const path = require("path");
const os = require("os");

const scope = process.argv.includes("--scope")
  ? process.argv[process.argv.indexOf("--scope") + 1]
  : "project";

const configDir = scope === "project"
  ? path.join(process.cwd(), ".codex")
  : path.join(os.homedir(), ".codex");

const configPath = path.join(configDir, "config.toml");
const examplePath = path.join(__dirname, "config.toml.example");

if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
}

let config = "";
if (fs.existsSync(configPath)) {
  config = fs.readFileSync(configPath, "utf-8");
  // Avoid duplicate entries
  if (config.includes("[mcp_servers.kicad]")) {
    console.log("✓ KiCad MCP server already configured in Codex config.");
    process.exit(0);
  }
}

const example = fs.readFileSync(examplePath, "utf-8");
fs.writeFileSync(configPath, config + "\n" + example);
console.log(`✓ KiCad MCP config appended to ${configPath}`);
