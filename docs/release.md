# Release

Current product versions are represented in:

- `.release-please-manifest.json`
- `apps/vscode-extension/package.json`
- `packages/mcp-server/pyproject.toml`
- `packages/mcp-server/src/kicad_mcp/__init__.py`
- `packages/mcp-server/mcp.json`
- `packages/mcp-server/server.json`
- `packages/mcp-npm/package.json`

`.release-please-manifest.json` tracks product package paths only. The private repository root is not released.

Release PRs are created by `.github/workflows/release-please.yml` with separate Release Please pull requests per product package path. The VS Code extension can release independently from `kicad-mcp-pro`; the MCP server Python package and npm launcher stay version-linked as one MCP product. Release publication workflows run from GitHub Releases and protected environments.

The publish workflows keep release evidence product-scoped:

- `publish-extension.yml` validates the VSIX, emits `SHA256SUMS.txt` and a
  CycloneDX SBOM, creates GitHub artifact attestations for the checksummed
  extension package, publishes the shared VSIX to the Visual Studio Marketplace,
  verifies the Marketplace version, and then publishes the same VSIX to Open VSX
  in a separate non-blocking job that downloads the published VSIX and compares
  its digest with the release checksum.
- `publish-python.yml` validates the wheel and source distribution, emits
  `packages/mcp-server/release-evidence/SHA256SUMS.txt`, emits a CycloneDX SBOM,
  uploads that evidence as `python-release-evidence`, and creates GitHub
  artifact attestations for the Python wheel and source distribution before PyPI
  trusted publishing. The publish jobs verify local checksums before upload and
  verify PyPI/TestPyPI SHA-256 digests after upload. The `python-dist` artifact
  intentionally contains only `*.whl` and `*.tar.gz` files.
- `publish-npm.yml` packs the `kicad-mcp-pro` npm launcher tarball, emits
  `SHA256SUMS.txt` and a CycloneDX SBOM, creates GitHub artifact attestations,
  publishes with npm provenance, and downloads the published tarball to verify
  its SHA-256 digest.
- `publish-mcp-container.yml` validates the Docker image on pull requests and
  publishes signed multi-arch GHCR images with BuildKit SBOM/provenance for
  `mcp-server-v*` GitHub Releases.

Release dry-runs also validate `compatibility.yaml` through the MCP server release preflight. Update [docs/support-matrix.md](support-matrix.md) and release notes whenever KiCad, VS Code, MCP, Node, pnpm, Python, or tool-schema support changes.

## Conventional Commit Scopes

Release Please derives product changelogs from Conventional Commits, so pull request titles and product-changing commits must use one of these scopes:

- `kicad-studio` for `apps/vscode-extension`.
- `kicad-mcp-pro` for `packages/mcp-server` and `packages/mcp-npm`.
- `repo` for repository governance, documentation, workflow, and shared release policy changes.
- `deps` for dependency-only updates.

Commits that touch both product directories must be split by product or use the multi-scope form `kicad-studio/kicad-mcp-pro`. Release Please generated PRs retain their upstream `chore(main): release ...` title format and are exempt from the human PR title scope gate.

Run product dry-runs before merging release-related changes:

```bash
corepack pnpm run release:dry-run:kicad-studio
corepack pnpm run release:dry-run:kicad-mcp-pro
corepack pnpm run release:dry-run
corepack pnpm run check:release-please
```
