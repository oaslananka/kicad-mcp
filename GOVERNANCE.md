# Governance

KiCad MCP Pro is maintained by `@oaslananka`. The project uses maintainer-led decisions with lazy consensus for routine changes.

## Decision Process

- Small fixes, docs updates, tests, and CI maintenance can be merged after normal review.
- User-facing behavior, public tool contracts, profile changes, transport behavior, and release policy changes need an issue or discussion before implementation.
- Major public API or workflow changes require an RFC under `docs/rfcs/`.

## RFC Process

1. Create `docs/rfcs/000N-title.md` with motivation, design, compatibility, migration, and alternatives.
2. Open a GitHub Discussion and keep it open for at least 14 days.
3. Maintainers accept, reject, or request revision.
4. Accepted RFCs become the source of truth for implementation PRs.

## Release Authority

Automated CI/CD is owned by the canonical `oaslananka/kicad-mcp`
GitHub repository. Publishing uses GitHub Actions environments and trusted
publishing where supported. Releases are driven by release-please and the CI
pipeline rather than by privileged local steps, so a release can be cut by any
maintainer with merge rights — no single person's workstation is in the path.

## Succession and continuity

This project currently has a single maintainer (bus factor = 1). That risk is
mitigated by design rather than hidden:

- **Everything needed to continue is in the repository.** Architecture
  ([`ARCHITECTURE.md`](ARCHITECTURE.md)), the build/release pipeline
  (`.github/workflows/`), the quality gates (`task verify` / `task ci`), and the
  contributor on-ramp ([`CONTRIBUTING.md`](CONTRIBUTING.md)) are documented and
  enforced in CI. A competent contributor can fork and continue without tribal
  knowledge.
- **Adding a co-maintainer.** A sustained contributor (several merged,
  well-tested PRs across more than one subsystem, and demonstrated understanding
  of the adapter-seam/honesty rules) may be invited as a co-maintainer. Onboarding
  grants are listed in [`MAINTAINERS.md`](MAINTAINERS.md).
- **If the sole maintainer becomes unavailable.** The canonical repository and
  package names are recorded in [`MAINTAINERS.md`](MAINTAINERS.md). Because
  publishing uses GitHub-side trusted publishing and CI environments, a new
  maintainer added to the repository can resume releases without recovering any
  individual's local secrets. If the repository itself becomes unreachable, the
  MIT license permits a community fork to continue under a new name.

## Security response

Vulnerabilities are reported privately per [`SECURITY.md`](SECURITY.md). The
primary security contact is the maintainer listed in
[`MAINTAINERS.md`](MAINTAINERS.md). To avoid a single point of failure, security
reports may also be filed as a GitHub private vulnerability report on the
canonical repository, which any current maintainer can triage. Co-maintainers
inherit security-triage responsibility when added.
