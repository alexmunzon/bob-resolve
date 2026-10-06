# bob-resolve

Project 1 of the Agency Data Trust Series (built second). Entity resolution for an acquired agency's
book of business: decides which records are the same real person, builds one golden record per person
with the source of every field, groups people into households, logs every merge, and sends doubtful
pairs to a human review queue. SPEC.md is the source of truth.

## Commands
- `npm run verify`            all checks: ruff, mypy, pytest, eslint, tsc, vitest, next build. Must pass before any commit.
- `cd engine && uv run bob-resolve version`   print the engine version.
- `cd engine && uv run bob-resolve fixtures derive --snapshot ../fixtures/agency-a-snapshot --out ../fixtures/agency-a-derived`   rebuild the derived clean enrollment side.
- `cd engine && uv run pytest -q tests/unit/test_cli.py -k version`   run one test file or test.
- `cd engine && uv run bob-resolve run --enrollment snapshot --out ../runs --run-id <id>`   write one immutable run folder (add `--no-shared-ids`, `--as-of`, `--now` as needed).
- `cd engine && uv run bob-resolve run --world multi-a-b --out ../runs --run-id <id>`   seen two-agency world from agency-data-commons v0.2.0 (the matcher was tuned on it in PR 10b) (generated into git-ignored fixtures/generated/).
- `cd engine && uv run bob-resolve review apply --run ../runs/<id> --decisions <file.jsonl> --out ../runs --run-id <new id>`   apply human decisions as a new run; the old run is never changed.
- `npm run demo`   regenerate the committed demo run in dashboard/public/demo-run/ (derived side, shared ids on, MBI masked). Byte-identical on a rerun.
- `cd dashboard && npm run dev`   local dashboard.

## Invariants (never break these)
- Synthetic data only. Never a real name list, real contacts, or real client files. No SSN, ever.
- A false merge is worse than a missed match. Auto-merge only when very sure; doubtful pairs go to review.
- Guard rails override the score and are never overridden by Jev or an LLM: different generational
  suffix is never auto-merged (GR-001); a shared MBI with DOBs more than one edit apart is never
  auto-merged (GR-002); shared phone or email alone never merges (GR-003); an ambiguous identity key
  never auto-merges, but one person's own records tied by MBI, phone, email, or street never count as conflicting
  (GR-004); first names that are not compatible, more than one typo apart, or one edit apart at a vowel or y ending
  (Patrick and Patricia, Andrew and Andrea) never auto-merge, even with a shared MBI (GR-005); a year-changing DOB
  transposition needs another agreeing identifier (GR-006); name plus DOB as the only agreeing evidence never
  auto-merges: it needs MBI (shared ids on), phone, email, street, or a linking policy (GR-007).
- Two authoritative sources that disagree on DOB or MBI are never guessed: review with IDENTITY_CONFLICT.
- The merge log is append-only JSONL. Never rewrite a line; a correction is a new line.
- JEV_MODE defaults to replay. The LLM arm defaults off. live and record spend money: no agent sets them;
  the orchestrator records only after Alex says yes in his own words, within the cap. CI is always replay.
- Model payloads carry only the compared fields. Free-text notes are never sent.
- Never read .env or any .env.* file. Secrets live only in .env, which git ignores.
- Cutoffs, thresholds, and guard rails live in engine/src/bob_resolve/config.py (filled in PR 5).
- Benchmark numbers are labeled "measured on synthetic data".

## Gotchas
- Use uv, not pip. Use polars, not pandas. jellyfish provides Jaro-Winkler and phonetic keys.
- Node 24 (Node 20 is end of life). Dashboard is Next 16; its APIs differ from older Next.
  Read node_modules/next/dist/docs/ before writing dashboard code.
- `typecheck` runs `next typegen` first, because Next 16 generates some page types at build time.
- Docs and UI strings: plain language, no em dashes.
- The repo path contains a space ("Data intake"). Quote every absolute path in shell commands and scripts.

## Workflow
- One PR per session per worktree. Branch names pr-NN-short-name. Under 400 changed lines.
- Tests first from SPEC examples, then implementation, then `npm run verify`, then show the output.
- Add one changelog fragment per PR in changelog.d/ (see changelog.d/README.md). Do not edit CHANGELOG.md directly.
- Never push, open a PR, merge, create a GitHub repo, or link Vercel without Alex's explicit go-ahead.
- Record lasting decisions as ADRs in docs/adr/.
