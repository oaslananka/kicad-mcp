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

## Pull Requests

1. Open a focused branch from `main`.
2. Add or update tests and documentation with the implementation.
3. Use a Conventional Commit title such as `fix: handle missing KiCad CLI`.
4. Confirm all required GitHub Actions checks pass.

Report vulnerabilities privately through the process in
[`SECURITY.md`](SECURITY.md).
