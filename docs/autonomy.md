# Repository Autonomy

This repository is configured for a single canonical GitHub repository.

## Ownership

- `oaslananka/kicad-mcp` is the canonical source-of-truth and release authority.
- Source changes, issues, releases, package publishing, and documentation
  deployment all happen from that repository.

## CI/CD Authority

Automation runs on `oaslananka/kicad-mcp`:

- CI matrix
- Security scanning
- CodeQL
- Scorecard
- release automation
- documentation deploy
- image and Docker checks
- package-manager publishing jobs

## Secrets

Doppler project `all`, config `main` is the secret source of truth for
workflows that need Doppler-backed values.

## Automation Boundaries

Automation does not publish releases without an explicit manual input, a
release tag trigger configured in the canonical repository, and the protected
`release` environment approval where required.
