#!/usr/bin/env bash
set -euo pipefail

: "${DOPPLER_PROJECT:=all}"
: "${DOPPLER_CONFIG:=main}"

# This readiness check is scoped to package, registry, and deployment publishing.
# Workflow service tokens are projected and validated separately in GitHub settings.
required_secrets=(
  # Reserved for Cloudflare-backed site/domain deployment paths.
  CLOUDFLARE_GLABAL_MAIL
  CLOUDFLARE_GLOBAL_API_KEY

  # Package registry and marketplace fallback tokens.
  NPM_TOKEN
  OVSX_PAT
  PYPI_TOKEN
  TEST_PYPI_TOKEN
  VSCE_PAT
)

if ! command -v doppler >/dev/null 2>&1; then
  echo "doppler CLI is required but was not found in PATH." >&2
  exit 1
fi

missing=()
for secret_name in "${required_secrets[@]}"; do
  if ! doppler secrets get "$secret_name" --plain \
        --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" \
        >/dev/null 2>&1; then
    missing+=("$secret_name")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  printf 'Missing Doppler secrets in %s/%s:\n' "$DOPPLER_PROJECT" "$DOPPLER_CONFIG" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

echo "All required Doppler publishing secrets are present in ${DOPPLER_PROJECT}/${DOPPLER_CONFIG}."
