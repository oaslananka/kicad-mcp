# Branch Protection

Rulesets are stored as code in `.github/rulesets/main.json`.

Create in the canonical repository:

```bash
gh api -X POST /repos/oaslananka/kicad-studio-kit/rulesets --input .github/rulesets/main.json
```

If the ruleset already exists, use the ruleset id:

```bash
gh api /repos/oaslananka/kicad-studio-kit/rulesets
gh api -X PUT /repos/oaslananka/kicad-studio-kit/rulesets/<id> --input .github/rulesets/main.json
```

The current policy requires pull requests, one review, code owner review,
signed commits, non-fast-forward protection, and the current monorepo workflow
check-run contexts listed in `docs/architecture/branch-protection.md`.

When a required workflow job name changes, update the root branch-protection
document and `.github/rulesets/main.json` together before applying the ruleset.
