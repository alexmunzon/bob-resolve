# ADR 002: Keep broker evidence review separate from identity resolution

Date: 2026-10-07. Status: accepted for local implementation; integration and release gates pending.

## Context

An unresolved Bob case needs an owner and an evidence trail without turning a broker response or a review label into an identity merge. The Session 1 integration contract scopes records to explicit agency and Intake run IDs and treats byte hashes as snapshot consistency checks, not authentication. Session 7 owns shared CLI registration, navigation, merges and deployments.

## Decision

Provide a standalone `bob_resolve.broker_workflow` CLI and `/workflow` browser page. Browser actions create a local, exportable draft containing assignment, request, response, acceptance and decision events. Bind the draft to explicit agency/Intake IDs, the native run, queue byte hash, manifest byte hash and opaque native record IDs. Reuse native record IDs without interpreting them or claiming the adapter's hash-derived ID format.

CLI application checks parent bytes, binding, exact saved history and event relationships before publishing a new immutable child. Preserve earlier event history and its original parent bindings. Browser draft import preserves the existing event prefix; identical repeat imports are no-ops and earlier or changed local events are refused. Refuse resolved public output paths, including symlink paths, for standalone export/application and native review children that carry a workflow ledger, before computation. This preserves private replay artifacts and minimized evidence. Context export completes write/flush/fsync in a private sibling staging file and publishes by exclusive hardlink; partial failures leave no final output, permit retry and preserve concurrent winners. Workflow cases remain unresolved; labels and accepted evidence apply no matching changes. Preserve the workflow ledger byte-for-byte during native `review apply` when it is manifest-pinned.

Declare reviewer names and response provenance unauthenticated. Validate the response hash's format, but do not claim to verify response bytes. No external messages or paid model calls are part of this workflow.

## Consequences

The evidence process can progress while identity remains unresolved. Reloading the browser loses unexported work. Operators must retain a trusted context and explicitly apply a draft through the CLI. Further work needs a fresh context from the child. Shared integration and the combined serial full gate belong to Session 7, with no commit before required full evidence. Publication requires exclusive rename support on macOS or Linux and fails closed elsewhere; a lock left by hard process death requires manual inspection and recovery. Native matching still requires its own verified inputs and review process.
