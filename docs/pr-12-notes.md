# PR 12: Saved explanations replayed offline

`bob_resolve.llm.replay.review_pair` reads one saved explanation for one pair from a local
folder. It defaults off. Replay is the only other mode; live and record are rejected, and the
`llm` package imports no model client, no HTTP library and reads no environment variables. A
test checks those imports. No real saved explanations exist yet: every file used in tests is a
synthetic stand-in labeled "synthetic-test-stub-not-model-output".

Requests carry only the structured fields the rules compare (names, DOB, street, ZIP, phone,
email, and MBI and policy keys only when shared ids are on). Notes and lineage are never
included. The file name is a SHA-256 of that request, the guard rails and the model tier. The
hash stays inside the run: `llm_assessments.jsonl` does not record it.

A saved file must be a regular file (not a link or folder), at most 8 KB, UTF-8 JSON with
exactly request_key, model, rationale, provenance and cost_usd. Anything else is invalid.
Explanation text is reduced to plain text: control, format and bidi characters are removed.
Any guard rail the engine knows (GR-001 to GR-008) is accepted.

Every row requires human review. There is no decision or merge field, and the run computes
scoring, merges, the review queue and guard rails before the explanation step and never reads
its output. See pr-12-cli-notes.md for the run integration.
