# Doppler Setup

This repository expects Doppler project `all`, config `main`.

## Manually Required GitHub Secret

Set exactly one GitHub secret manually in the canonical repository:

- `DOPPLER_TOKEN`

The token must be a read-only Doppler service token scoped to project `all`, config `main`.

Set it in `oaslananka/kicad-studio-kit`.

Workflow service secrets such as `DOPPLER_GITHUB_SERVICE_TOKEN`,
and `SAFETY_API_KEY` may be present as GitHub Actions secrets at runtime.
Prefer projecting them into GitHub by Doppler GitHub Sync. Release publishing
uses trusted publishing where available; package-index tokens remain
Doppler-managed fallback inputs and must not be printed.

`CODECOV_TOKEN` is maintained as a selected GitHub secret
for coverage upload only. Do not store or fetch a Codecov API token for CI.

## Doppler GitHub Sync

In the Doppler dashboard:

1. Open project `all`, config `main`.
2. Install the GitHub integration for `oaslananka`.
3. Create a sync to `oaslananka/kicad-studio-kit` repository secrets.
4. Use replace mode so GitHub remains a projection of Doppler, not a second source of truth.

## Required Secrets

The authoritative secret-name list lives in this document rather than a dotfile
so scanner exclusions do not need to hide a `.doppler/` directory.

Current expected Doppler-backed package/deployment names:

- `CLOUDFLARE_GLABAL_MAIL`
- `CLOUDFLARE_GLOBAL_API_KEY`
- `NPM_TOKEN`
- `OVSX_PAT`
- `PYPI_TOKEN`
- `TEST_PYPI_TOKEN`
- `VSCE_PAT`

Usage:

- `CLOUDFLARE_GLABAL_MAIL`: Cloudflare account mail. This spelling is a compatibility name and must remain exact until the Doppler secret and workflow mappings are intentionally migrated together.
- `CLOUDFLARE_GLOBAL_API_KEY`: Cloudflare API key for workflows that actually deploy docs/site/domain resources.
- `NPM_TOKEN`: npm fallback publish token when trusted publishing is unavailable.
- `OVSX_PAT`: Open VSX fallback token, only if a real VS Code extension surface exists.
- `PYPI_TOKEN`: PyPI fallback token when trusted publishing is unavailable.
- `TEST_PYPI_TOKEN`: TestPyPI fallback token when trusted publishing is unavailable.
- `VSCE_PAT`: VS Marketplace fallback token, only if a real VS Code extension surface exists.

Workflow service names that may also be projected from Doppler:

- `DOPPLER_GITHUB_SERVICE_TOKEN`: least-privilege GitHub service token for release-please PR creation when repository policy blocks `GITHUB_TOKEN` from opening pull requests.
- `SAFETY_API_KEY`: optional authenticated Safety scan. It is not required for local default gates.

GitHub-only selected secret:

- `CODECOV_TOKEN`: optional Codecov coverage upload token used only by `.github/workflows/ci.yml`. Pull requests from forks receive no token and may use Codecov's public tokenless upload behavior.

Legacy package-index token names are not required by GitHub Actions after the
trusted publishing migration.

No workflow or diagnostic output should print secret values.

## Verification

```bash
bash scripts/verify_doppler_secrets.sh
```

This command requires the Doppler CLI and a local login or `DOPPLER_TOKEN`.
