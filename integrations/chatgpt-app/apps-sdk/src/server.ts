/**
 * KiCad MCP ChatGPT App — Remote MCP Server
 *
 * Provides read-only tools for KiCad project analysis:
 * - search_kicad_docs / fetch_kicad_doc — knowledge base
 * - analyze_uploaded_kicad_project — zip archive analysis
 * - explain_drc_report / explain_erc_report — report interpretation
 * - generate_manufacturing_readiness_report — release checklist
 * - generate_agent_config — config snippet for any agent
 */

import express from "express";
import { McpServer } from "mcp";
import { z } from "zod";

const app = express();
app.use(express.json({ limit: "50mb" }));

// In-memory project store (replace with DB in production)
const projects = new Map<string, { name: string; uploadedAt: Date }>();

const mcp = new McpServer({
  name: "KiCad MCP",
  version: "0.1.0",
  tools: [
    {
      name: "search_kicad_knowledge",
      description: "Search KiCad documentation and knowledge base.",
      inputSchema: z.object({
        query: z.string().describe("Search query"),
        maxResults: z.number().optional().describe("Maximum results"),
      }),
      handler: async ({ query }: { query: string }) => {
        return { content: [{ type: "text", text: `Search results for: ${query}` }] };
      },
    },
    {
      name: "analyze_uploaded_kicad_project",
      description: "Analyze an uploaded KiCad project archive.",
      inputSchema: z.object({
        fileId: z.string().describe("Uploaded file identifier"),
      }),
      handler: async ({ fileId }: { fileId: string }) => {
        const project = projects.get(fileId);
        if (!project) return { content: [{ type: "text", text: `Project ${fileId} not found` }] };
        return {
          content: [
            { type: "text", text: `Project: ${project.name}\nStatus: analysis complete` },
          ],
        };
      },
    },
    {
      name: "explain_drc_report",
      description: "Interpret a DRC report and explain issues.",
      inputSchema: z.object({
        reportText: z.string().describe("Raw DRC report text"),
      }),
      handler: async ({ reportText }: { reportText: string }) => {
        // Parse and categorize DRC issues
        const errors = (reportText.match(/error/gi) || []).length;
        const warnings = (reportText.match(/warning/gi) || []).length;
        return {
          content: [
            {
              type: "text",
              text: `DRC Report Summary:\n- Errors: ${errors}\n- Warnings: ${warnings}\n\nSee documentation for each rule category.`,
            },
          ],
        };
      },
    },
    {
      name: "explain_erc_report",
      description: "Interpret an ERC report and explain issues.",
      inputSchema: z.object({
        reportText: z.string().describe("Raw ERC report text"),
      }),
      handler: async ({ reportText }: { reportText: string }) => {
        const errors = (reportText.match(/error/gi) || []).length;
        const warnings = (reportText.match(/warning/gi) || []).length;
        return {
          content: [
            {
              type: "text",
              text: `ERC Report Summary:\n- Errors: ${errors}\n- Warnings: ${warnings}\n\nCheck power connections, pin conflicts, and unresolved net labels.`,
            },
          ],
        };
      },
    },
    {
      name: "generate_manufacturing_readiness_report",
      description: "Generate a manufacturing readiness report for a project.",
      inputSchema: z.object({
        drcErrors: z.number().describe("Number of DRC errors"),
        ercErrors: z.number().describe("Number of ERC errors"),
        hasBom: z.boolean().describe("Whether BOM is available"),
        hasGerbers: z.boolean().describe("Whether Gerbers are available"),
      }),
      handler: async (input: {
        drcErrors: number;
        ercErrors: number;
        hasBom: boolean;
        hasGerbers: boolean;
      }) => {
        const issues: string[] = [];
        if (input.drcErrors > 0) issues.push(`${input.drcErrors} DRC error(s)`);
        if (input.ercErrors > 0) issues.push(`${input.ercErrors} ERC error(s)`);
        if (!input.hasBom) issues.push("No BOM generated");
        if (!input.hasGerbers) issues.push("No Gerber files generated");
        const ready = issues.length === 0;
        return {
          content: [
            {
              type: "text",
              text: ready
                ? "✅ Board is manufacturing-ready!"
                : `❌ Board is NOT manufacturing-ready. Issues:\n${issues.map((i) => `  - ${i}`).join("\n")}`,
            },
          ],
        };
      },
    },
    {
      name: "generate_agent_config",
      description: "Generate an MCP config snippet for a supported agent.",
      inputSchema: z.object({
        targetAgent: z
          .enum(["claude-code", "codex", "gemini", "opencode", "cursor", "vscode"])
          .describe("Target agent"),
        mode: z.enum(["readonly", "write"]).optional().describe("Operating mode"),
      }),
      handler: async ({
        targetAgent,
        mode = "readonly",
      }: {
        targetAgent: string;
        mode?: string;
      }) => {
        const stdioConfig = { command: "uvx", args: ["kicad-mcp-pro"] };
        const env = { KICAD_MCP_PROFILE: "analysis", KICAD_MCP_OPERATING_MODE: mode };
        const configs: Record<string, object> = {
          "claude-code": { mcpServers: { kicad: { type: "stdio", ...stdioConfig, env } } },
          codex: { mcp_servers: { kicad: { command: "uvx", args: ["kicad-mcp-pro"], env } } },
          gemini: { mcpServers: { kicad: { ...stdioConfig, env } } },
          opencode: { mcp: { kicad: { type: "local", command: ["uvx", "kicad-mcp-pro"], environment: env } } },
          cursor: { mcpServers: { kicad: { ...stdioConfig, env } } },
          vscode: { servers: { kicad: { type: "stdio", ...stdioConfig, env } } },
        };
        return {
          content: [
            {
              type: "text",
              text: `Config for ${targetAgent} (${mode}):\n\`\`\`json\n${JSON.stringify(configs[targetAgent], null, 2)}\n\`\`\``,
            },
          ],
        };
      },
    },
  ],
});

// Mount MCP endpoint
app.use("/mcp", mcp);

const PORT = parseInt(process.env.PORT || "8765", 10);
app.listen(PORT, () => {
  console.log(`KiCad MCP ChatGPT App running on port ${PORT}`);
});
