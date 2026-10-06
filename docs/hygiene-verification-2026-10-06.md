# Repository hygiene verification, 2026-10-06

Base: visual commit `7d20551`. Scope: README and documentation, contributor/security guidance,
one changelog fragment, and the existing verification workflow. No matching code, UI, dependency
manifest/lock, fixture, version, committed run, or benchmark figure changed.

Environment: Node 24.19.0, npm 11.9.0, Python 3.12.14, uv 0.12.19. Existing dependencies were
installed with `npm ci` and `uv sync --locked`, using writable caches under `/tmp`. Both succeeded
without lockfile changes. npm emitted the existing ESLint 9.39.5 deprecation warning; uv used a
copy fallback because its cache and environment were on different filesystems.

## Focused checks

- `git diff --check`: passed.
- Local documentation links and heading anchors: 46 checked, all resolved, including this note.
- Parsed workflow checks: official action SHAs match the audited refs; `contents: read`, replay mode,
  locked installs, and `npm run verify` are retained. Checkout credentials are not persisted; timeout
  is 20 minutes; cancellation applies only to superseded pull-request runs.
- README scorecard and known-limits sections: byte-identical to the visual baseline, including
  2-of-320 (0.63%) no-shared-ids cross-agency recall and the seen/synthetic caveats.
- `uv run --project engine pytest -q engine/tests/unit/test_audit_security_bob.py
  engine/tests/unit/test_release_0_1_0.py`: 11 passed.

## Fresh dashboard lockfile audits, 22:49 UTC

- `npm audit --package-lock-only --ignore-scripts --omit=dev --json`: exit 0; zero findings.
- `npm audit --package-lock-only --ignore-scripts --json`: completed with expected exit 1; five
  high-severity package nodes, all tracing to braces GHSA-vfj7-8cjw-p6xm. No other advisory URL
  was reported. No dependency upgrades or overrides were applied.

The high-severity development-tool finding remains open. See the
[bounded security review](security-review-2026-10-06.md) and [SECURITY.md](../SECURITY.md) for
coverage, mitigation, reporting, and limitations. A production-only zero does not mean zero total risk.

## Aggregate verification

The first full `npm run verify` invocation passed lint, types, and tests, then was killed during
static generation at 1,205 of 1,607 pages with exit 137 (SIGKILL). Its exact cause was not established.
The build was using eight static workers. No repository source or configuration was changed to retry.

The complete gate was rerun with this process-local environment and reached terminal **exit 0**
at 22:56 UTC:

```bash
UV_CACHE_DIR=/tmp/gyde-bob-hygiene-uv JEV_MODE=replay CIRCLE_NODE_TOTAL=3 npm run verify
```

The installed Next.js 16 configuration maps `CIRCLE_NODE_TOTAL=3` to two build workers. This bounded
the retry's worker concurrency; it does not alter matching, tests, application features, or repo defaults.

- Ruff lint and format: passed; 63 files already formatted.
- Mypy: passed; 35 source files.
- Engine: 392 passed, 2 skipped, 5 expected failures. Existing no-shared-ids recall misses remain;
  this hygiene pass does not fix or hide them.
- Dashboard ESLint and TypeScript: passed.
- Dashboard Vitest: 84 passed in 11 files.
- Next.js production build: passed; all 1,607 static pages generated using two workers, then page
  optimization completed.

Only the required results in this note were filled after the runtime gate. Local links, workflow
settings, whitespace, and unchanged protected code/data/locks were checked again on the final diff.

## Release boundaries

No hosted CI execution, browser check, production-route check, or deployment was performed by this
documentation/CI pass. No push, PR, merge, credentials, paid service, account/security setting, or
access permission change was made. No `.env` or `.env.*` file was opened, including the template.
Published state must be checked against the final release commit separately.
