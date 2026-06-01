# Public Listings

The canonical public listing source of truth is `PUBLIC_LISTING.md` at the repository root.

Use that root file for submission status, manual action items, approval URLs, and post-approval operations. This documentation page exists so the MkDocs navigation can link to the listing status without referencing files outside the documentation directory.

Before submitting to a public directory, run:

```bash
pnpm run submission:check
```

For final production screenshots, also run:

```bash
SUBMISSION_MODE=1 pnpm run submission:check
```
