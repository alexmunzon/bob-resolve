# Offline broker workflow

This workflow records who owns an unresolved review case, what evidence was requested, what response was declared, and what a reviewer decided. It uses synthetic data only. Browser actions stay in memory until exported; nothing is sent to a broker.

A decision is a label, not an identity merge. Every workflow case stays `identity_state: "unresolved"`, including after accepting evidence or recording `same_person`. Matching and the existing native human review process remain separate.

## Use the standalone CLI

Run these commands from `engine/`. The shared `bob-resolve` command registration belongs to Session 7; this change supplies a standalone module.

```bash
uv run python -m bob_resolve.broker_workflow export \
  --run ../dashboard/public/demo-run \
  --agency-id synthetic-demo --intake-run-id synthetic-fixture \
  --out /tmp/broker-context.json
```

Open `/workflow` in the local dashboard, load the CLI context, and add actions. Shared navigation is left to Session 7. Export the draft before reloading: the page has no server persistence, authentication, or browser storage. To resume, load the same empty-events context first, then import its matching draft. A subsequent import must retain the complete existing event prefix. An identical repeat changes nothing; an older draft or a draft that changes local events is refused.

```bash
uv run python -m bob_resolve.broker_workflow apply \
  --run ../dashboard/public/demo-run \
  --draft /tmp/broker-workflow-draft.json \
  --out ../runs/broker-child \
  --agency-id synthetic-demo --intake-run-id synthetic-fixture
```

The output must be a new child folder outside its parent run. Export and apply refuse resolved output paths inside `PUBLIC_FOLDER_NAMES`, including paths that reach a public folder through symlinks. Native `review apply` also refuses a public or symlink-aliased public child when it carries a workflow ledger, before matching computation. Keep private replay artifacts and minimized workflow evidence outside public folders. Context export writes a private sibling staging file, flushes and fsyncs complete bytes, then publishes with an exclusive hardlink. A partial-write or sync failure leaves no final context; staging cleanup permits retry. Existing files, symlinks and concurrent winners are preserved. The CLI refuses existing output folders, stale files, modified bindings or history, duplicate events, unknown cases, missing requests/responses, and invalid action fields. It copies verified parent outputs, appends a `broker_workflow.json` ledger, and writes a new manifest. It changes no identity outputs. Export a fresh context from the child to append further events.

## Actions and evidence state

| Action | Stored meaning |
|---|---|
| `assign` | `text` declares the case owner; `actor` declares who recorded it. |
| `request` | Opens an evidence request identified by its event ID. |
| `response` | References a request and declares source file, SHA-256, positive source row and timezone-aware received time. |
| `accept` | References that request and one recorded response; only one response can be accepted per request. |
| `decision` | Records `same_person`, `different_people` or `leave_unresolved` with a reason. |

A case is `open` before requests, `needs_evidence` while any request lacks an accepted response, and `evidence_reviewed` after every request has an accepted response. A decision does not close an evidence request. Historical cases remain visible even if a later native review queue no longer contains them. New events may target only the current queue.

## Binding and append-only history

The version `1.0.0` draft contains explicit `agency_id`, `intake_run_id`, producer `run_id`, `data_kind: "synthetic"`, `queue_sha256`, and `base_hash` (the exact parent manifest byte SHA-256). `identities` binds each queue item to sorted opaque native `record_id` values. The workflow reuses those values without interpreting their spelling or manufacturing Session 1 adapter record IDs. The caller supplies agency and Intake IDs; neither is inferred from a name or filename.

The Session 1 contract (workspace source: `/Users/alexmunzon/Data intake/bob-contract-adapters/docs/contracts/agency-integration-v1.md`; integrated `docs/contracts/agency-integration-v1.md` is pending Session 7) defines agency/run identity scope and distinguishes consistency from authenticity. This workflow follows its explicit scope fields but is a native Bob workflow artifact, not an adapter packet. It does not claim that native record IDs have the contract adapter's hash-derived format.

The browser draft keeps saved `history` separate from new `events`. Application requires the history and context to match the current parent exactly. Every newly saved event retains its parent run, queue hash and manifest hash. Earlier history is appended to, never edited. Native `review apply` carries the ledger bytes unchanged when the parent manifest pins that output, and includes the copied ledger in the new output hashes.

Hashes of run artifacts are checked against actual bytes by the CLI. A response hash is a reviewer declaration: response bytes are not fetched or independently authenticated. Reviewer and owner names are unauthenticated declarations. Keep a trusted parent context; matching hashes cannot prove who supplied it.

## Synthetic walkthrough artifacts

- `context.json`: exported context for the committed native demo run.
- `draft.json`: assignment, missing-identifier request, declared synthetic response and `leave_unresolved` decision.
- `synthetic-response.json`: explicitly says identity proof remains missing.
- `expected-ledger.json`: expected ledger after that draft is applied to the demonstration child.

The sample intentionally leaves its evidence request unaccepted and its identity unresolved. Regenerate the context if the demo run changes; pinned hashes make an older draft refuse rather than silently reuse it. The local `runs/workflow-demo` is a demonstration output, not deployed evidence.

## Limits and verification

No messages, real client data, paid calls, identity merges, independent response authentication, or durable browser storage are provided. This demonstrates an offline evidence trail, not human-confirmed resolution, accuracy on unseen data, or real savings.

Publication uses an exclusive rename on macOS and Linux, so a concurrent destination is never overwritten. It fails closed on unsupported platforms or filesystems. macOS publication passed focused checks; actual Linux execution awaits the hosted gate. A hard process death can leave a workflow lock: inspect the child, lock and staging files before manual recovery rather than retrying blindly.

After Session 7 combined review found partial context-export publication and native-review public-destination gaps, the repaired engine freeze passed 48 focused tests in 0.65s; Ruff lint passed, four files were formatted, and mypy passed on three source files. Independent repaired-state verification passed 48/48 tests in 0.84s, Ruff lint/format, mypy and diff checks, with no blocking findings. Final frozen dashboard files passed 37/37 focused tests across two files, next typegen + tsc and focused ESLint. Independent Sol final engine/UI source-and-test review found no blocking issue; the independent dashboard rerun also passed 37/37 tests in 2.68s, focused ESLint and next typegen + tsc using Node 24.21.0. Session 7 owns the required combined serial full gate; no builder runs that heavy gate and no commit is made before its evidence is available.

The builder environment exposed only Chrome extension browser ID 1, so its desktop, 375px, console and overflow checks remain unverified; no alternate browser was used. Session 7 now has an IAB worker and owns the pending browser check on the combined integration candidate. Hosted and deployment evidence remain pending in [HANDOFF.md](HANDOFF.md).
