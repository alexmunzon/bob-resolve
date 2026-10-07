# Contributing

This is a synthetic-data, rules-only demonstration. Read [README.md](README.md),
[SPEC.md](SPEC.md), and [CLAUDE.md](CLAUDE.md) before changing behavior. The
[documentation index](docs/README.md) points to provenance and dated verification evidence.

## Setup and checks

Use Node 24, Python 3.12, and uv. From the repository root:

```bash
(cd engine && uv sync --locked)
(cd dashboard && npm ci)
npm run verify
```

`npm run verify` runs Ruff lint and format checks, mypy, pytest, ESLint, TypeScript, Vitest, and
the Next.js production build. Run it before committing. Focused tests help while developing but
do not replace the aggregate check. Record any skipped or expected-failure tests accurately.
Use writable temporary caches if needed; see the README. Do not update locks just to install.

## Keep changes reviewable

- Use a separate branch/worktree for a coherent change. Add tests that reproduce a behavior change
  before implementing it. Keep UI-only edits separate from engine, fixture, or benchmark changes.
- Add one dated fragment in `changelog.d/`; follow its README. Do not edit `CHANGELOG.md` directly.
- Preserve source provenance, immutable parent runs, and the append-only merge log. Document lasting
  design decisions in `docs/adr/` and keep the specification aligned with approved behavior changes.
- Keep automatic, reviewer-confirmed, and hypothetical suggestion-inclusive results separate. Label
  synthetic and seen regression evidence honestly; do not turn it into a claim about real-world accuracy.
- Review shared-identifier and display-masking assumptions. The no-shared-ids mode is a separate
  evaluation, not the masked public demo. A queued direct pair and an existing cluster are different facts.

## Data and dependency safety

- Use synthetic fixtures only. Never add real names, contacts, client records, SSNs, or credentials.
  Do not open `.env` or any `.env.*` file, including templates. No key is needed for this demo.
- Keep Jev replay behavior and paid/model tiers off. Do not enable a live or record mode as part of
  routine tests. No implemented model arm exists in this version.
- Treat untrusted data and dependency changes as separate review work. Use supported upstream fixes;
  do not force an audit upgrade or add an untested override. See [SECURITY.md](SECURITY.md) for how
  the braces tooling advisory was removed (a tested local fast-glob stand-in) and reporting instructions.
- CI uses read-only token permissions and full-SHA action pins. When updating an action, verify the
  official upstream commit, retain its version comment, and rerun verification.

A local check does not establish that CI or a deployed site contains your change. Include the tested
commit, commands, results, and any remaining release checks in a contribution. Publishing, deployment,
account settings, and access changes need the repository owner's authorization.
