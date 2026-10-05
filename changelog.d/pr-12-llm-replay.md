## PR 12: Saved explanations replayed offline (2026-10-06)

- Add an optional step that attaches saved explanations to gray pairs, replayed offline from a
  local folder. It is off by default (`--llm-mode off`). The only other mode is `replay`; there is
  no live or record mode, no model client, no network access, and no API key is read.
- No real saved explanations exist yet. Tests use synthetic stand-in files labeled as test
  stubs, not model output. The demo run and its numbers are unchanged.
- An explanation is advisory only. Scoring, merges, the review queue and every guard rail
  (GR-001 to GR-008) are decided first and never read it; every row still needs a person.
- A missing saved explanation is counted as pending; a broken, oversized, linked or non-UTF-8
  file is counted as invalid. Neither stops a run or changes a decision.
- Replay writes `llm_assessments.jsonl` and manifest counts with zero calls and zero cost. Rows
  carry no hash of the compared fields, explanation text is reduced to plain text, and a replay
  run into a public folder is refused.
- `review apply` keeps the old run's mode. The dashboard LLM tile reads "Saved explanations
  replayed offline. Recorded advisory only, no live calls." in replay mode.
