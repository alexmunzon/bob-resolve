# PR 12: Run integration for saved explanations

`bob-resolve run ... --llm-mode replay --llm-cassettes <folder>` attaches saved explanations,
replayed offline, to gray pairs. The default is `--llm-mode off`, which reads nothing and
writes exactly what earlier runs wrote, so the demo run is unchanged.

Jev is not part of this build (PR 11 stays out of scope), so every gray pair counts as
Jev-unsure and is eligible. The Opus tier is expected when either record holds an active
policy (a merge would move coverage or a commission line, SPEC step 5); Sonnet otherwise.
This only picks which saved file is looked up; nothing is called.

Replay writes `llm_assessments.jsonl` (pair ids, status, tier, guard rails, plain-text
explanation, provenance, a label saying it is a saved explanation replayed offline, and
`requires_human_review: true`). The manifest reports replayed, pending (no saved file) and
invalid (unreadable or wrong file) counts, zero calls and zero cost. Recorded costs from saved
files are kept separately and counted once per request. The CLI prints a line saying how many
saved explanations were found and that no model was called.

Safety: a run with replay into a folder named `public` is refused. `review apply` carries the
old run's mode. Tests compare people, households, members, review queue, merge log (ignoring
run id), scorecard and review pairs across off, pending, invalid and replayed runs, with shared
ids on and off, while network connections are blocked.
