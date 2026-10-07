# Unreleased offline advisory verification

Base: b2788a42008a202c7ff328a18b9dc097e9b389a4
Checked October 7, 2026. Local candidate only; no push, PR, merge or deployment.

- Ruff lint/format: pass
- Mypy: 47 source files, pass
- Full engine suite: 559 passed, 2 skipped, 5 expected failures
- Advisory sidecar boundary tests: 15 passed (included above)
- Dashboard lint/typecheck: pass
- Dashboard tests: 144 passed across 16 files using `npm test -- --maxWorkers=1`
- Dashboard production build: pass using `CIRCLE_NODE_TOTAL=2 npm run build`
- `git diff --check`: pass

The first parallel dashboard test run lost two workers to SIGKILL. The default build then
compiled and typechecked but was killed while generating 1608 routes with eight workers.
Serial tests and the supported Next worker-count environment setting completed all checks.
These were execution-resource retries; no test expectations, app code, or build configuration
were changed to make them pass.

Tests cover source and scored-evidence tampering, stale run bindings, malformed/oversized/
contradictory/missing fixtures, symlink and FIFO refusal, no fixture reads in off mode,
blocked socket calls, source preservation, explicit citations and no-overwrite CLI output.
Existing engine tests retain overwrite recovery, deterministic matching and explanation replay.
No browser UI changed in this candidate. Live providers, real-client validation and dashboard
sidecar display are outside this offline CLI implementation.

Independent review found a fixture-path check/open race in the first local candidate. The
revised reader anchors directory descriptors, opens with no-follow and nonblocking flags,
and verifies the opened file is regular before reading. Added regression tests replace the
file with a symlink or FIFO at open time and replace the directory after anchoring; all stay
pending without reading the outside response or blocking. Unsupported safe-open platforms
fail closed. Final engine gates were rerun after the fix.
