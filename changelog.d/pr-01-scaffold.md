## PR 1: Scaffold (2026-10-05)

- Repo layout copied from plan-diff's scaffold. No matching code yet.
- Engine: Python 3.12 with uv. One package, bob_resolve, with a `bob-resolve` command whose only subcommand is `version`. ruff, mypy strict, pytest, hypothesis.
- Adds jellyfish (MIT license) for Jaro-Winkler name similarity and phonetic keys, used from PR 3.
- `config.py` holds typed placeholders: Jev defaults to replay, the LLM arm is off, and the SPEC targets. Cutoffs and guard rails land in PR 5.
- Dashboard: Next.js 16 (App Router, TypeScript, Tailwind), ESLint, vitest. One placeholder page.
- Root `npm run verify` runs every check. CI runs it on every push and PR once a remote exists.
- `.claude/settings.json` permissions and a Stop hook that runs verify before Claude can end a turn with uncommitted changes.
- One changelog fragment per PR in changelog.d/.
