# PR 1 notes: scaffold decisions

Decisions made while building the scaffold, for the orchestrator and Alex to review.

## Copied from plan-diff's pr-0-scaffold
- Same stack and commands: Python 3.12 with uv, Next 16.3.8, React 19.2.8, Node 24, and the same
  `npm run verify` shape at the root (scripts only, no root lockfile).
- Same ruff rules (line length 100; E, F, I, UP, B) and mypy strict on src.
- Dashboard files copied as-is except names: same versions, scripts, configs, and dashboard/package-lock.json
  (the package name is still "dashboard", so the lockfile is valid unchanged; `npm ci` succeeded on it).
- .claude/settings.json and the Stop hook copied byte for byte. Every allow, ask, and deny line kept.
- .github/workflows/verify.yml copied unchanged. It will not run until the repo has a GitHub remote.
- .env.example: JEV_MODE=replay and empty TYPESAFE_API_KEY and ANTHROPIC_API_KEY.
- LICENSE: main had none, so agency-intake-kit's MIT LICENSE was copied (identical to plan-diff's).

## Different from plan-diff, and why
- Package bob_resolve, command `bob-resolve`.
- Adds jellyfish for Jaro-Winkler similarity and phonetic keys (SPEC section 6). License: MIT
  (checked in the installed package metadata), so it fits this MIT repo. Ships compiled Rust wheels.
- Adds engine/src/bob_resolve/config.py with typed Final placeholders: JEV mode replay, LLM arm off,
  the SPEC decision 2 targets, the $0.50 Jev recording cap, and the 1930 two-digit year pivot.
  The cutoffs and guard rails land in PR 5, so they are not guessed here.
- Two engine tests: the version command, and a check that paid modes are off by default.
- No data/raw/ folder or its .gitignore lines: bob-resolve downloads nothing. Fixtures arrive in PR 2
  under fixtures/ and are committed.
- CLAUDE.md invariants come from SPEC section 12 and decisions 2 to 4 (synthetic only, no SSN, false merge
  worse than missed match, guard rails never overridden, append-only merge log, Jev and LLM default off or replay).
- docs/adr/README.md lists the planned bob-resolve ADRs.

## Risks and open items
- The Stop hook runs the full verify (including `next build`) whenever the tree is dirty.
- npm warns that unrs-resolver (an ESLint dependency) has an unapproved install script. Same in plan-diff and aik.
- `next dev` may write dashboard/AGENTS.md and dashboard/CLAUDE.md with em dashes; do not commit them as-is.
- engine/uv.lock was regenerated (not copied) because jellyfish was added; versions may differ slightly from plan-diff's.
