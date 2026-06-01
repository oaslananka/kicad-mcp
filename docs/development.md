# Development

## One-Time Setup

Install Task from <https://taskfile.dev/installation/>.

```bash
task install
task hooks
```

## Local Setup

`pnpm run workflows:lint` and `task workflows:lint` require `actionlint` on
`PATH`. Install it from <https://github.com/rhysd/actionlint> before running the
full local workflow lint gate.

## Daily Workflow

```bash
task format
task lint
task typecheck
task test
task security
task workflows:lint
task workflows:security
task ci
```

## Before Push

The pre-push hook runs:

```bash
task pre-push
```

For full local parity with CI:

```bash
task ci
```

For local workstation security scanners:

```bash
task security:local
```

This command requires Gitleaks, actionlint, and zizmor. It reports clear install
hints when a required scanner is missing.

## Optional GitHub Actions Local Run

Install `act` from <https://github.com/nektos/act>, then run:

```bash
act -W .github/workflows/ci.yml --container-architecture linux/amd64
```

## Troubleshooting

- `task: command not found`: install Task from the official installation page.
- Hook setup fails: run `uvx pre-commit install --install-hooks`.
- CI and local results differ: run `task doppler:check` and verify the same Doppler project/config are used.
