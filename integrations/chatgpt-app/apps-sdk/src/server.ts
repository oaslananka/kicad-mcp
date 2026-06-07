/**
 * KiCad MCP ChatGPT App — Remote MCP Server
 *
 * Provides KiCad project analysis tools for ChatGPT GPTs.
 * Runs in two modes:
 *   1. **Proxied** — Spawns `kicad-mcp-pro` as a subprocess and
 *      forwards tool calls via stdio MCP (full local toolset available).
 *   2. **Standalone** — Falls back to heuristic / static analysis when
 *      the Python backend is not installed (useful for cloud hosting).
 *
 * Also serves 3 UI widgets:
 *   - /widgets/dashboard       — Board overview, layers, component count
 *   - /widgets/project-review  — DRC/ERC issues grouped by severity
 *   - /widgets/manufacturing   — Step-by-step release checklist
 */

import express, { type Request, type Response } from "express";
import { McpServer } from "mcp";
import { z } from "zod";
import { existsSync, readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { createWriteStream } from "node:fs";
import { statSync, mkdtempSync } from "node:fs";
import { createUnzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { createReadStream } from "node:fs";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const PORT = parseInt(process.env.PORT || "8765", 10);
const HOST = process.env.HOST || "0.0.0.0";
const KICAD_MCP_CMD = process.env.KICAD_MCP_CMD || "kicad-mcp-pro";
const STATIC_DIR = resolve(import.meta.dirname, "..", "public");

// ---------------------------------------------------------------------------
// Helpers — KiCad project parsing
// ---------------------------------------------------------------------------

interface KiCadProject {
  name: string;
  path: string;
  boardPath: string | null;
  schematicPath: string | null;
  metadata: Record<string, unknown>;
}

interface KiCadBoard {
  layers: number;
  boardThickness: number | null;
  copperLayers: number;
  componentCount: number;
  trackCount: number;
  viaCount: number;
}

interface KiCadSchematic {
  componentCount: number;
  netCount: number;
  sheetCount: number;
}

function parseKiCadProj(path: string): Record<string, unknown> {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return {};
  }
}

function parseKiCadPcbLayers(pcb: Record<string, unknown>, fallback = 4): number {
  const layers = (pcb as Record<string, unknown>).layers;
  if (Array.isArray(layers)) return layers.length;
  return fallback;
}

function countBoardComponents(pcb: Record<string, unknown>): number {
  const footprint = (pcb as Record<string, unknown>).footprint;
  if (Array.isArray(footprint)) return footprint.length;
  return 0;
}

function countBoardTracks(pcb: Record<string, unknown>): number {
  const segment = (pcb as Record<string, unknown>).segment;
  if (Array.isArray(segment)) return segment.length;
  return 0;
}

function countBoardVias(pcb: Record<string, unknown>): number {
  const via = (pcb as Record<string, unknown>).via;
  if (Array.isArray(via)) return via.length;
  return 0;
}

async function extractProject(dir: string): Promise<string> {
  const entries = await readdir(dir, { withFileTypes: true });
  const kicadProj = entries.find(
    (e) => e.isFile() && e.name.endsWith(".kicad_proj"),
  );
  if (!kicadProj) {
    // Look for any project file inside a subdirectory
    for (const entry of entries) {
      if (entry.isDirectory()) {
        const sub = await readdir(join(dir, entry.name));
        const nested = sub.find((f) => f.endsWith(".kicad_proj"));
        if (nested) return join(dir, entry.name, nested);
      }
    }
    throw new Error("No .kicad_proj file found in archive");
  }
  return join(dir, kicadProj.name);
}

function analyzePcbFile(pcbPath: string): KiCadBoard {
  try {
    const raw = readFileSync(pcbPath, "utf-8");
    const pcb = JSON.parse(raw) as Record<string, unknown>;
    return {
      layers: parseKiCadPcbLayers(pcb),
      boardThickness: (pcb.setup as Record<string, unknown>?.board_thickness as number) ?? null,
      copperLayers: parseKiCadPcbLayers(pcb),
      componentCount: countBoardComponents(pcb),
      trackCount: countBoardTracks(pcb),
      viaCount: countBoardVias(pcb),
    };
  } catch {
    return { layers: 0, boardThickness: null, copperLayers: 0, componentCount: 0, trackCount: 0, viaCount: 0 };
  }
}

// ---------------------------------------------------------------------------
// In-memory project store
// ---------------------------------------------------------------------------

const projects = new Map<string, KiCadProject>();

// ---------------------------------------------------------------------------
// Helpers — DRC / ERC report interpretation
// ---------------------------------------------------------------------------

interface ReportSummary {
  errors: number;
  warnings: number;
  issues: Array<{ severity: string; rule: string; description: string }>;
}

function analyzeDrcReport(text: string): ReportSummary {
  const lines = text.split("\n");
  const issues: Array<{ severity: string; rule: string; description: string }> = [];
  let errors = 0;
  let warnings = 0;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^error|^[✗❌]|violations? found/i.test(trimmed)) errors++;
    else if (/^warn|^⚠|warning/i.test(trimmed)) warnings++;
    // Try to parse structured DRC output
    const ruleMatch = trimmed.match(/\(([\w-]+)\)\s*:\s*(.+)/);
    if (ruleMatch) {
      issues.push({ severity: "error", rule: ruleMatch[1], description: ruleMatch[2] });
    }
  }
  // Fallback: count occurrences
  errors = Math.max(errors, (text.match(/\berror\b/gi) || []).length);
  warnings = Math.max(warnings, (text.match(/\bwarning\b/gi) || []).length);
  return { errors, warnings, issues };
}

function analyzeErcReport(text: string): ReportSummary {
  const issues: Array<{ severity: string; rule: string; description: string }> = [];
  const lines = text.split("\n");
  let errors = 0;
  let warnings = 0;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^error|^[✗❌]|conflict/i.test(trimmed)) errors++;
    else if (/^warn|^⚠|unconnected|not connected/i.test(trimmed)) warnings++;
    const ruleMatch = trimmed.match(/\(([\w-]+)\)\s*:\s*(.+)/);
    if (ruleMatch) {
      issues.push({ severity: "error", rule: ruleMatch[1], description: ruleMatch[2] });
    }
  }
  errors = Math.max(errors, (text.match(/\berror\b/gi) || []).length);
  warnings = Math.max(warnings, (text.match(/\bwarning\b/gi) || []).length);
  return { errors, warnings, issues };
}

// ---------------------------------------------------------------------------
// Manufacturing readiness checklist
// ---------------------------------------------------------------------------

interface ManufacturingChecklist {
  overall: "ready" | "not_ready";
  checks: Array<{ name: string; passed: boolean; detail: string }>;
}

function generateReadinessChecklist(drcErrors: number, ercErrors: number, hasBom: boolean, hasGerbers: boolean): ManufacturingChecklist {
  const checks: Array<{ name: string; passed: boolean; detail: string }> = [
    { name: "DRC Clean", passed: drcErrors === 0, detail: drcErrors > 0 ? `${drcErrors} DRC error(s) remaining` : "No DRC errors" },
    { name: "ERC Clean", passed: ercErrors === 0, detail: ercErrors > 0 ? `${ercErrors} ERC error(s) remaining` : "No ERC errors" },
    { name: "BOM Generated", passed: hasBom, detail: hasBom ? "BOM available" : "BOM not generated" },
    { name: "Gerbers Exported", passed: hasGerbers, detail: hasGerbers ? "Gerber files available" : "Gerber files not exported" },
  ];
  const overall = checks.every((c) => c.passed) ? "ready" : "not_ready";
  return { overall, checks };
}

// ---------------------------------------------------------------------------
// Subprocess bridge to kicad-mcp-pro
// ---------------------------------------------------------------------------

function runKicadMcp(method: string, args: Record<string, unknown>): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("uvx", ["kicad-mcp-pro", method, "--json"], {
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 30_000,
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
    proc.on("close", (code) => {
      if (code === 0 && stdout) resolve(stdout);
      else reject(new Error(stderr || `Process exited with code ${code}`));
    });
    proc.on("error", (err) => reject(err));
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params: args, id: 1 }) + "\n");
    proc.stdin.end();
  });
}

// ---------------------------------------------------------------------------
// Express App + MCP Server
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: "50mb" }));

// Serve HTML widgets
app.use("/widgets", express.static(STATIC_DIR));

// Rewrite / to redirect to dashboard
app.get("/", (_req: Request, res: Response) => {
  res.redirect("/widgets/kicad-dashboard.html");
});

// Project upload endpoint
app.post("/api/analyze", async (req: Request, res: Response) => {
  try {
    const { projectDir } = req.body as { projectDir?: string };
    if (!projectDir) {
      return res.status(400).json({ error: "projectDir is required" });
    }
    const projPath = await extractProject(projectDir);
    const projectDirRoot = resolve(projectDir, "..");
    const name = projPath.replace(/\.kicad_proj$/, "").split(/[/\\]/).pop() || "unknown";
    const boardPath = projPath.replace(/\.kicad_proj$/, ".kicad_pcb");
    const schematicPath = projPath.replace(/\.kicad_proj$/, ".kicad_sch");
    const metadata = parseKiCadProj(projPath);
    const project: KiCadProject = {
      name,
      path: projPath,
      boardPath: existsSync(boardPath) ? boardPath : null,
      schematicPath: existsSync(schematicPath) ? schematicPath : null,
      metadata,
    };
    projects.set(name, project);
    return res.json(project);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return res.status(400).json({ error: message });
  }
});

// MCP Server
const mcp = new McpServer({
  name: "KiCad MCP",
  version: "0.1.0",
  tools: [
    {
      name: "search_kicad_knowledge",
      description: "Search KiCad documentation and knowledge base for PCB design topics.",
      inputSchema: z.object({
        query: z.string().describe("Search query (e.g. 'footprint editor', 'differential pair routing')"),
        maxResults: z.number().optional().describe("Maximum results to return"),
      }),
      handler: async ({ query }: { query: string }) => {
        try {
          const result = await runKicadMcp("search_kicad_docs", { query });
          return { content: [{ type: "text", text: result }] };
        } catch {
          return {
            content: [{
              type: "text",
              text: `KiCad documentation search for "${query}" — use https://docs.kicad.org for latest docs.`,
            }],
          };
        }
      },
    },
    {
      name: "analyze_uploaded_kicad_project",
      description:
        "Analyze an uploaded KiCad project archive. " +
        "Accepts a directory path containing .kicad_proj, .kicad_pcb, .kicad_sch files. " +
        "Returns project metadata, layer stackup, component count, and board statistics.",
      inputSchema: z.object({
        fileId: z.string().describe("Uploaded file identifier or project directory path"),
      }),
      handler: async ({ fileId }: { fileId: string }) => {
        // Try already-analyzed project
        const cached = projects.get(fileId);
        if (cached) {
          const board = cached.boardPath ? analyzePcbFile(cached.boardPath) : null;
          return {
            content: [
              {
                type: "text",
                text: [
                  `## Project: ${cached.name}`,
                  `- Board: ${cached.boardPath || "N/A"}`,
                  `- Schematic: ${cached.schematicPath || "N/A"}`,
                  board
                    ? [
                        `- Layers: ${board.layers} (${board.copperLayers} copper)`,
                        `- Components: ${board.componentCount}`,
                        `- Tracks: ${board.trackCount}`,
                        `- Vias: ${board.viaCount}`,
                        board.boardThickness ? `- Board Thickness: ${board.boardThickness}mm` : "",
                      ].filter(Boolean).join("\n")
                    : "",
                  "",
                  "Upload a KiCad project archive to get full analysis.",
                ].join("\n"),
              },
            ],
          };
        }
        // Try to analyze path directly
        try {
          const projPath = await extractProject(fileId);
          const name = projPath.replace(/\.kicad_proj$/, "").split(/[/\\]/).pop() || "unknown";
          const projDir = resolve(projPath, "..");
          const boardPath = resolve(projDir, `${name}.kicad_pcb`);
          const board = existsSync(boardPath) ? analyzePcbFile(boardPath) : null;
          return {
            content: [
              {
                type: "text",
                text: [
                  `## Project: ${name}`,
                  board
                    ? [
                        `- Layers: ${board.layers} (${board.copperLayers} copper)`,
                        `- Components: ${board.componentCount}`,
                        `- Tracks: ${board.trackCount}`,
                        `- Vias: ${board.viaCount}`,
                      ].join("\n")
                    : "Board file not found in archive.",
                  "",
                  "Upload a complete KiCad project (kicad_proj + kicad_pcb + kicad_sch) for full analysis.",
                ].join("\n"),
              },
            ],
          };
        } catch {
          return {
            content: [{
              type: "text",
              text: `Project "${fileId}" not found. Upload a KiCad project archive (.zip, .kicad_proj) first.`,
            }],
          };
        }
      },
    },
    {
      name: "explain_drc_report",
      description:
        "Interpret a DRC (Design Rule Check) report and explain issues. " +
        "Accepts raw report text and returns a structured summary with categorized violations.",
      inputSchema: z.object({
        reportText: z.string().describe("Raw DRC report text"),
      }),
      handler: async ({ reportText }: { reportText: string }) => {
        const { errors, warnings, issues } = analyzeDrcReport(reportText);
        const lines = [
          `## DRC Report Summary`,
          `- **Errors:** ${errors}`,
          `- **Warnings:** ${warnings}`,
          "",
        ];
        if (issues.length > 0) {
          lines.push("### Issues Found");
          for (const issue of issues.slice(0, 20)) {
            lines.push(`- [${issue.severity.toUpperCase()}] \`${issue.rule}\`: ${issue.description}`);
          }
        }
        lines.push(
          "",
          "### Tips",
          "- Check clearance, track width, and via size constraints",
          "- Verify net classes match design requirements",
          "- Ensure all unrouted nets are intentional",
          "- Run `kicad_run_drc` from the KiCad MCP toolset for a fresh check",
        );
        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    },
    {
      name: "explain_erc_report",
      description:
        "Interpret an ERC (Electrical Rule Check) report and explain issues. " +
        "Accepts raw report text and returns a structured summary.",
      inputSchema: z.object({
        reportText: z.string().describe("Raw ERC report text"),
      }),
      handler: async ({ reportText }: { reportText: string }) => {
        const { errors, warnings, issues } = analyzeErcReport(reportText);
        const lines = [
          `## ERC Report Summary`,
          `- **Errors:** ${errors}`,
          `- **Warnings:** ${warnings}`,
          "",
        ];
        if (issues.length > 0) {
          lines.push("### Issues Found");
          for (const issue of issues.slice(0, 20)) {
            lines.push(`- [${issue.severity.toUpperCase()}] \`${issue.rule}\`: ${issue.description}`);
          }
        }
        lines.push(
          "",
          "### Tips",
          "- Verify power flags on all power nets",
          "- Check pin conflicts and unconnected pins",
          "- Ensure hierarchical labels match across sheets",
          "- Run `kicad_run_erc` from the KiCad MCP toolset for a fresh check",
        );
        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    },
    {
      name: "generate_manufacturing_readiness_report",
      description:
        "Generate a manufacturing readiness report for a KiCad project. " +
        "Evaluates DRC/ERC status, BOM, and Gerber availability.",
      inputSchema: z.object({
        drcErrors: z.number().describe("Number of DRC errors"),
        ercErrors: z.number().describe("Number of ERC errors"),
        hasBom: z.boolean().describe("Whether BOM is available"),
        hasGerbers: z.boolean().describe("Whether Gerber files are available"),
        projectName: z.string().optional().describe("Project name"),
      }),
      handler: async (input: {
        drcErrors: number;
        ercErrors: number;
        hasBom: boolean;
        hasGerbers: boolean;
        projectName?: string;
      }) => {
        const { overall, checks } = generateReadinessChecklist(
          input.drcErrors,
          input.ercErrors,
          input.hasBom,
          input.hasGerbers,
        );
        const header = input.projectName
          ? `## Manufacturing Readiness: ${input.projectName}`
          : "## Manufacturing Readiness Report";
        const statusLine = overall === "ready"
          ? "✅ **Ready for manufacturing**"
          : "❌ **Not ready for manufacturing**";
        const lines = [header, "", statusLine, "", "### Checklist", ""];
        for (const check of checks) {
          const icon = check.passed ? "✅" : "❌";
          lines.push(`| ${icon} | ${check.name} | ${check.detail} |`);
        }
        if (overall !== "ready") {
          lines.push(
            "",
            "### Next Steps",
            ...checks.filter((c) => !c.passed).map((c) => `- Fix: ${c.name} — ${c.detail}`),
          );
        }
        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    },
    {
      name: "generate_agent_config",
      description: "Generate an MCP configuration snippet for a supported AI coding agent.",
      inputSchema: z.object({
        targetAgent: z
          .enum(["claude-code", "codex", "gemini", "opencode", "cursor", "vscode", "claude-desktop"])
          .describe("Target AI coding agent"),
        mode: z.enum(["readonly", "write"]).optional().describe("Operating mode"),
        transport: z.enum(["stdio", "sse", "streamable-http"]).optional().describe("Transport protocol"),
      }),
      handler: async ({
        targetAgent,
        mode = "readonly",
        transport = "stdio",
      }: {
        targetAgent: string;
        mode?: string;
        transport?: string;
      }) => {
        const env = {
          KICAD_MCP_PROFILE: "readonly",
          KICAD_MCP_OPERATING_MODE: mode,
        };
        const stdioEntry = transport === "stdio"
          ? { command: "uvx", args: ["kicad-mcp-pro"] }
          : { url: process.env.KICAD_MCP_URL || "http://localhost:8412/mcp", env };
        const configs: Record<string, object> = {
          "claude-code": { mcpServers: { kicad: { type: "stdio", ...stdioEntry, env } } },
          codex: { mcp_servers: { kicad: { command: "uvx", args: ["kicad-mcp-pro"], env } } },
          gemini: { mcpServers: { kicad: { ...stdioEntry, env } } },
          opencode: { mcp: { kicad: { type: "local", command: ["uvx", "kicad-mcp-pro"], environment: env } } },
          cursor: { mcpServers: { kicad: { ...stdioEntry, env } } },
          vscode: { servers: { kicad: { type: "stdio", ...stdioEntry, env } } },
          "claude-desktop": { mcpServers: { kicad: { ...stdioEntry, env } } },
        };
        return {
          content: [
            {
              type: "text",
              text: `## Config for ${targetAgent} (${mode}, ${transport})\n\`\`\`json\n${JSON.stringify(configs[targetAgent as keyof typeof configs] || configs["claude-code"], null, 2)}\n\`\`\``,
            },
          ],
        };
      },
    },
  ],
});

// Mount MCP endpoint
app.use("/mcp", mcp);

// Start server
app.listen(PORT, HOST, () => {
  console.log(`KiCad MCP ChatGPT App running at http://${HOST}:${PORT}`);
  console.log(`  MCP endpoint: http://${HOST}:${PORT}/mcp`);
  console.log(`  Dashboard:    http://${HOST}:${PORT}/widgets/kicad-dashboard.html`);
  console.log(`  Project Review: http://${HOST}:${PORT}/widgets/project-review.html`);
  console.log(`  Manufacturing:  http://${HOST}:${PORT}/widgets/manufacturing-report.html`);
});
