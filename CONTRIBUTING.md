# Contributing to KiCad MCP Pro

Thank you for improving KiCad MCP Pro. Keep changes focused, include tests for
behavioral changes, and use Conventional Commit messages.

## Development Setup

Requirements:

- Node.js 24 and pnpm 11 through Corepack
- Python 3.13 and uv
- Rust stable for the optional Tauri desktop application

Install the development dependencies:

```bash
corepack enable
corepack pnpm install --frozen-lockfile
uv sync --all-extras --frozen
```

Copy `.env.example` to `.env` only when local overrides are needed. Never commit
credentials or local environment files.

## Quality Gates

Run the focused checks while developing:

```bash
corepack pnpm run format:check
corepack pnpm run lint
corepack pnpm run typecheck
corepack pnpm run test:unit
```

Before opening a pull request, run the full local CI equivalent:

```bash
task ci
```

See [`docs/testing.md`](docs/testing.md) for the test layers and
[`docs/repository-operations.md`](docs/repository-operations.md) for release and
maintenance policies.

## Add a tool in an afternoon

The server is deliberately structured so that adding a capability is a one-module,
one-registry-entry change. Start with [`ARCHITECTURE.md`](ARCHITECTURE.md) — the
five-layer map and the **"How to add a new tool"** section are the authoritative
walkthrough. The short loop:

1. **Implement** the tool inside the matching `src/kicad_mcp/tools/*.py` module's
   `register(mcp)` (decorated with `@mcp.tool()`). Keep KiCad-touching calls behind
   the adapter seam and pure logic in `utils/` so it is unit-testable.
2. **Register** the tool name under the right category in `TOOL_CATEGORIES`
   (`tools/router.py`) and confirm the category is in the profiles that should
   expose it. Mark experimental tools in `EXPERIMENTAL_TOOL_NAMES`.
3. **Annotate** read-only / destructive / headless / requires-KiCad metadata via
   `tools/metadata.py`.
4. **Regenerate + verify**: `pnpm run docs:tools` and `pnpm run metadata:check`.
   The registry-consistency and tool-surface-snapshot tests flag any drift.
5. **Test** the pure logic with a unit test; gate KiCad-driving paths behind the
   KiCad-enabled CI job.

Then `task verify` must be green. Honesty rule: if a capability is heuristic,
approximate, or partial, say so in the tool name, docstring, and verdict — never
claim a precision the code does not deliver.

## Pull Requests

1. Open a focused branch from `main`.
2. Add or update tests and documentation with the implementation.
3. Use a Conventional Commit title such as `fix: handle missing KiCad CLI`.
4. Confirm all required GitHub Actions checks pass.

Report vulnerabilities privately through the process in
[`SECURITY.md`](SECURITY.md).
