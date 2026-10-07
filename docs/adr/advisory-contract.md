# Advisory second opinions v1 (2026-10-07)

`bob_resolve.advisory.Request`, `Response`, and `Result` are separate contracts from
`bob_resolve.llm`. Existing explanation replay, CLI flags, cassettes and outputs are unchanged.
`model_json_schema()` exports each schema; `model_dump(mode="json")` exports artifacts.

Integration hook: after deterministic scoring, construct Request only for a GRAY pair.
Provide SHA-256 bindings to immutable run, queue and pair identity artifacts. Map compared
fields to agree/conflict/similar/missing; pass every fired guardrail. Do not serialize record
values, names, contacts, IDs, notes or raw source rows. Hashes stay local. Synthetic inputs only.
The caller must derive comparisons and bindings from trusted deterministic output; a supplied
hash or data-kind label is not independent proof of provenance or de-identification.

Call `evaluate(request, mode="replay", response=fixture_bytes)` and attach its result as a
separate review artifact. Never feed it to scoring, merges or review-apply decisions. Missing,
malformed, stale, unsupported or contradictory evidence has no suggestion. A valid suggestion
still has `review_state="needs_review"`. No API in this module clears guardrails or resolves cases.
Do not mistake `status="replayed"` for approval or model validation.

Definite opinions require supporting cited comparisons: same_person needs at least one cited
agree and different_people needs at least one cited conflict. Uncited comparisons cannot supply
that support, and similar alone supports neither definite opinion. Existing conflict and guardrail
checks still reject same_person. This is minimum advisory grounding, not a matching threshold;
unsure remains available and every accepted suggestion still needs human review.

Modes: off (default) ignores response bytes; replay validates an in-memory fixture; live returns
live_blocked. Every mode reports zero calls and zero cost. No network, file, environment or
credential access exists. Origin is explicitly hand_written_synthetic_fixture; actual provider
recordings need a future versioned provenance contract, not a relabeled fixture.

Session 7 owns CLI/navigation registration and integration with Session 1's artifact IDs.
Use the local hashes as adapters to those IDs once the shared contract lands. The new module
is not registered into the production run pipeline in this change.

Live validation remains unperformed. Alex must approve the exact provider/model and a specific
USD spending limit and authorize each live session. Credentials must be securely configured
without reading secret files. A future transport must enforce the cap, timeout/retry policy,
record actual provider/model/request IDs and usage, and test failures and adversarial outputs
using synthetic minimized requests. No live SDK or new dependency is introduced here.

Aligned with Session 1's agency-integration 1.0.0 contract: review_state is always
needs_review, never approved/resolved. Hash canonical_json(packet) bytes (including the
trailing newline) for run_hash so agency_id, run_id and intake_run_id remain bound locally.
Verify artifact byte pins before constructing requests; retain provenance outside the payload.
Hash the exact immutable queue bytes for queue_hash; hash canonical sorted source record IDs
for pair_hash. Use Session 1 record_ids, not names, and never mark an identity resolved here.
