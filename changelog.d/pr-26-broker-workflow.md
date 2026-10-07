## PR 26: Offline broker evidence workflow (2026-10-07)

- Add a synthetic browser draft for case ownership, evidence requests, declared responses, evidence acceptance and review labels. Export before reloading; nothing is sent to a broker.
- Add a standalone CLI that validates agency/Intake/run and byte-hash bindings, then appends events in a new immutable child run. Decisions never merge identities.
- Preserve the manifest-pinned workflow ledger unchanged through native review application. Reviewer names and response hashes remain unauthenticated declarations.
- Preserve local event prefixes on draft import, reject resolved public output paths, and publish child runs with an exclusive no-replace rename. Publish complete context exports atomically with a private staging file and exclusive hardlink; native review also refuses public destinations when carrying a workflow ledger.
- Add focused refusal, preservation and browser-state tests, plus synthetic examples and integration handoff. Shared CLI registration, navigation and release remain Session 7's work.
