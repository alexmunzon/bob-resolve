# PR 12: Optional rationale replay

`bob_resolve.llm.replay.review_pair` provides a completed, independently testable rationale
reader. It defaults off. Replay is the only enabled mode; live and record are rejected and
no API client or credential is loaded. Its separate budget argument defaults to zero.

Callers supply structured compared-field pairs, gray-zone eligibility, Jev uncertainty,
existing guardrail IDs, and whether coverage or commission would move. Sonnet is selected
for ordinary uncertain pairs; Opus is selected only for high-stakes pairs. Unknown fields
including notes are rejected. With shared_ids=False, MBI and policy keys are omitted from the hashed request.

Cassettes belong in a caller-selected directory and are named `<request_key>.json`. The
SHA-256 key includes the sorted compared fields, guardrails, schema version and model tier.
Each cassette contains exactly request_key, model, rationale, provenance and cost_usd.
Rationale and provenance must be nonempty bounded strings; recorded cost must be finite
and nonnegative. Model/key mismatches and invalid cassettes raise ValueError. Replay cost
is always zero; recorded cost is separate evidence. Missing cassettes return pending.

Every response requires human review. There is no decision or merge field and guardrails
are preserved. This module is not wired into the run CLI yet: PR 11 owns that integration.
No recorded model answers or benchmark accuracy are claimed. Until an authorized recording
exists, the optional LLM benchmark row remains pending.

Validation: engine lint, format and mypy pass; 320 pytest pass with 2 skips and 5 expected
failures. Dashboard lint, generated type checks and 28 Vitest tests pass. Default
Turbopack production build is blocked by this sandbox's worker port binding restriction;
the equivalent webpack production build is used to validate the dashboard artifact.
