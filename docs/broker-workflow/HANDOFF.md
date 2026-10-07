# Broker workflow handoff

Recorded 2026-10-07. Local implementation is uncommitted on `pr-26-broker-workflow`, based on `3ccdbe9420a9f2bb32605574cd027db6f9a8321c`, in `/Users/alexmunzon/Data intake/bob-broker-workflow`. No commit, published PR, merge or deployment is established by this handoff. The filename PR number is the planned work item, not evidence of a GitHub PR.

## Current orchestration rule

Astra coordinates planning/delegation/review/integration, explicit Sol workers implement/debug/test/verify; no Astra implementation subagents; parallel independent ownership; Session7 sole merge/deploy owner.

This current explicit user rule supersedes conflicting historical model and ownership instructions below. The standing section is preserved word for word as required; consult workspace `CLAUDE.md` and the actual current user authorization before release actions.

## Standing rules (carry these into every future handoff, word for word)

These are Alex's standing instructions. Copy this whole section into the next handoff file unchanged, then add any
new rule Alex gives.

**How to run the work**
- **Use 5 subagents.** Divide the work and grind in parallel: typically two builders, two independent reviewers and
  one tester, each in its own worktree. Use fewer only when there is truly no independent work.
- **Use Opus 5.5** for the subagents, to work as fast and efficiently as possible.
- **If it's using a browser, use a browser.** Anything a person would see in a page gets checked in the real
  browser before it is called done: desktop and 375px phone width, console errors, sideways overflow, and the live
  production URL after a deploy. Use the in-app browser (IAB) only. Never launch or drive Chrome, Edge, a personal
  browser or a local Playwright browser.
- **It's on Claude.** The work runs in Claude Code (desktop app). The live status page is a Claude artifact:
  https://claude.ai/artifact/NnfWmHWLKrGSCJuVtgJjeu. Update that same artifact (same file path or its URL) after
  meaningful progress; do not create a new one.
- Root (the main session) is the only integrator: it alone commits, pushes, opens PRs and merges. Agree interfaces
  first, one owner per worktree, builders leave changes uncommitted for root.
- Run heavy suites (`npm run verify`) serially, by root only, on the exact final commit. Subagents run focused
  checks only.
- Plan big, execute small: Fable/Opus does judgment and synthesis; bulk reading, sweeps and checks go to subagents
  that return distilled findings.

**Permission rules (never assume a past approval carries over)**
- Never push a branch, open a PR or merge without Alex's explicit permission in his own words for that specific
  action, each time.
- No new deploy, tag, release, protection or settings change without explicit approval. Vercel protection was
  checked on 2026-10-06 and deliberately left unchanged (see "Public demo links").
- No paid model calls (Jev or LLM `live`/`record`), no real PHI, no SSNs, no real client files, no carrier
  downloads, no live portals, no external messages, no `.env` or secret reads.
- Never sign in, enter passwords or create accounts on Alex's behalf.

**Quality and safety rules**
- Tests first. Never weaken an assertion or extend a timeout to make a test pass.
- One changelog entry per PR (Bob uses a fragment in `changelog.d/`). No PR size limit, and related changes may share one PR
  (Alex, 2026-10-06, replacing the old 400-line and one-idea-per-PR rules). Every PR still gets the full checks below.
- Every final exact commit needs an independent review and a green exact-head hosted `verify` run before merge.
  Merge pinned to the reviewed head (`gh pr merge --merge --match-head-commit <sha>`). After merge: confirm merged
  tree equals reviewed tree, post-merge main `verify` green, Vercel production READY at the merge SHA, and a live
  browser check.
- Preserve every checkout, branch, stash and uncommitted change. Never pop or drop stashes, never remove worktrees,
  never reset other people's work. Back up uncommitted or unpushed saved work (bundle or tar plus checksums in
  `backups/`) before building on it.
- Synthetic results are labeled "measured on synthetic data". Never claim real savings, human-confirmed resolution
  or accuracy on unseen data. A suggestion is not a resolution until a person confirms it.
- Plain language in docs and UI. Never use em dashes. Quote paths: the folder name contains a space.
- Guardian mandate: raise secrets, security, data-safety, money, privacy, cost and edge-case risks unprompted, in one
  plain sentence, before building.

**Talking to Alex**
- Alex is a sharp UCLA student without a coding background. Plain words, define a term once in at most two
  sentences, frame decisions as business outcomes, teach through the real work, never condescend.

## Scope and current work

Implemented locally: append-only assignment, request, response, acceptance and decision events; browser import/export; standalone CLI context export and immutable application; explicit agency/Intake/run, queue hash and manifest hash binding; unchanged native identity outputs; manifest-pinned ledger preservation through native review application.

The native IDs in `identities` are opaque existing queue `record_id` values. They are reused, never interpreted or replaced with guessed cross-agency IDs. Explicit agency and Intake scope fields follow the Session 1 contract at `/Users/alexmunzon/Data intake/bob-contract-adapters/docs/contracts/agency-integration-v1.md`. This native artifact does not claim adapter hash-derived IDs or independently verified agency identity.

Response provenance contains a declared source file, SHA-256, row and received time. Hashes for response evidence are not checked against independently acquired bytes; reviewer/owner names are unauthenticated. Workflow decisions are labels only and keep identity unresolved. No real savings, unseen accuracy, or human-confirmed identity resolution is established.

Deferred: shared CLI registration and shared navigation (Session 7); authentication, response byte acquisition/authentication, messages, persistent browser storage, identity matching changes, paid calls, and real data. Nothing is sent externally.

## Ownership and integration boundaries

Root coordinates integration; Session 7 owns the combined serial full check on integrated content. No builder heavy gate and no commit before required full evidence. Explicit Sol workers own independent implementation, documentation, review and browser verification areas; root records final agent names/status here before release. Session 7 alone owns merge/deploy and shared integration.

New engine implementation: `engine/src/bob_resolve/broker_workflow/` and focused unit tests. New dashboard implementation: `dashboard/app/workflow/`, `dashboard/components/broker-workflow.tsx`, `dashboard/lib/broker-workflow.ts` and two focused test files. This documentation owner edited only README, ADR, changelog fragment and this handoff.

The shared `engine/src/bob_resolve/run/__init__.py` patch is bounded to three areas: `Parent.workflow` optional bytes at line 99; `write_folder` copies the ledger at lines 487-488 before manifest output hashing; `apply_review` reads it only when manifest-pinned at lines 620-622. Session 7's separate overwrite repair owns the surrounding `execute()` implementation. The combined review found that native review application could carry a private workflow ledger into a public child. The workflow repair now adds a scoped `execute()` guard at lines 546-547: when `parent.workflow` is present, refuse a resolved final public path before computation, including symlink aliases. Preserve this guard and Session 7's overwrite repair during integration.

Browser imports preserve the complete existing event prefix: identical repeated imports are a no-op, while older or differing local events are refused. Standalone export/application and native review children carrying a workflow ledger refuse resolved public output paths (`PUBLIC_FOLDER_NAMES`), including symlink paths, to preserve private replay outputs and minimized evidence. Combined review also found direct context export could leave a partial final file on write failure. Repaired export uses a private sibling staging file, full write/flush/fsync and exclusive hardlink publication; normal failure cleans staging, leaves no final file and permits retry. Existing files/symlinks and concurrent winners survive. Both findings used synthetic evidence. Exclusive child publication uses macOS/Linux no-replace rename and fails closed on unsupported platforms/filesystems. A stale workflow lock after hard process death needs manual inspection and recovery. Repaired engine files are frozen with no blockers on independent repaired-state review; UI files are also frozen. Independent Sol engine/UI source-and-test review found no blocking issue; the complete integrated content freeze remains pending.

## Saved work and examples

Searches of branches, stashes, workspace filenames/text and git history found no prior broker_workflow drafts. Existing saved work was preserved. This is a searched absence, not permission to remove unrelated work.

Synthetic examples: `docs/broker-workflow/context.json`, `draft.json`, `expected-ledger.json`, `synthetic-response.json`. Local demonstration output: `runs/workflow-demo`. The sample request remains unaccepted, the declared response says identifier proof is missing, and the decision is `leave_unresolved`. A changed demo parent invalidates its example bindings.

Uncommitted changes include the engine workflow module/test, the three bounded native review ledger edits, dashboard workflow page/components/helpers/tests, these docs and the existing JSON examples. Reconcile `git status` before integrating; concurrent workers may still add changes. No worktree, branch or stash should be removed.

## Verification and release gates

| Check | Evidence / state |
|---|---|
| Focused engine tests | Repaired final freeze: 48 passed in 0.65s, including five atomic-export and two native public-output regressions beyond the prior 41. Ruff lint clean, four files formatted, mypy three source files clean. Independent repaired-state verification passed 48/48 in 0.84s, Ruff lint/format, mypy three source files and diff checks; prior state independently passed 41. |
| Focused dashboard tests | Final frozen UI: 37/37 Vitest across two files in 2.23s; next typegen + tsc and focused ESLint passed. Original test timeout retained. |
| Native review ledger preservation | Covered by focused engine tests; full combined integration still pending. |
| Full local verify on final content | Pending Session 7 combined serial gate; no builder heavy gate or commit before required evidence. |
| Final bounded independent review | Earlier independent Sol final engine/UI source-and-test read found no blockers. Session 7 combined review then found atomic export P2 and native public ledger P1; both are repaired with focused regressions. Independent repaired-state verification passed with no blocking findings. Earlier engine checks independently rerun green. Independent dashboard rerun: 37/37 in two files, 2.68s; focused ESLint and next typegen + tsc clean with Node 24.21.0. Final source/read and diff checks clean. |
| Exact-head hosted verify | Pending root update; no final commit yet. |
| Desktop/375px IAB, console and overflow | Builder environment unverified: only Chrome extension ID 1 was exposed and no alternate browser was used. Session 7 now has an IAB worker and owns the combined integration-candidate browser check; result pending. |
| Merge and merged-tree equivalence | Pending Session 7; no merge performed. |
| Production READY at merged SHA and live IAB | Pending Session 7; no deployment performed. |

Do not convert pending entries to passed without exact evidence. Current evidence demonstrates focused local behavior only. Session 7 owns the pending IAB integration check; the earlier builder environment had no IAB and no alternate browser was substituted. No final reviewed manifest/content freeze is claimed.

## Next three actions

1. Root transfers the frozen reviewed work to Session 7 with its exact manifest and records remaining limits here; the repaired engine focused checks and frozen dashboard independent recheck have passed; final independent repaired-engine review also passed with no blocking findings.
2. Root coordinates the bounded native ledger patch with Session 7's separate `execute()` repair; Session 7 runs the combined full gate serially before any commit. Record final content, exact commit and actual gate evidence.
3. Session 7 handles shared registration/navigation and any authorized PR/merge/deploy sequence, then records reviewed head, merged tree equivalence, production commit and desktop/375px live IAB results. Keep drafts and saved work preserved.
