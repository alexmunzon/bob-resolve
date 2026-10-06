# Recruiting demo acceptance (2026-10-06)

Base: main `d832167`. Branch: `pr-23-recruiting-demo-finish`.
Scope: finish the existing rules-only recruiting demonstration. Matching rules, fixtures, generated
run files, dependencies, and the separate offline-rationale PR are unchanged.

## Delivered

- Overview links directly to the strong match, weak direct pair, conflicting pair, and benchmark.
- Every page links the three projects in walkthrough order and says they are separate demos.
- Overview and Benchmark explain that MBI was available for matching before display masking.
  A no-shared-ids run explicitly says MBI and linking policy IDs were withheld.
- The first screen labels its fixtures as seen, synthetic evidence rather than real-world accuracy.
  Automatic recall and hypothetical suggestion-inclusive recall remain separate.
- Review items disclose `already_one_person` when other accepted links have already joined the
  records. The queued direct pair still needs review. All eight GR-007 demo items have this state.
- README describes the existing dashboard, setup, source provenance, guarded review workflow,
  no-shared-ids limitations, and remaining roadmap honestly. The earlier screenshot walkthrough
  now explains the direct-pair versus cluster distinction and retains its original capture commit.

## Validation

Run in a clean cloud checkout with Node 24.19.0, Python 3.12.14, and uv 0.12.19. Installed the
existing locks with `npm ci` and `uv sync --frozen`; no package changes. Writable temporary caches
were needed because the environment's default home caches are read-only.

Tests were added before implementation. The new navigation, evidence links, shared-ID disclosures,
seen-fixture caveat, and joined-record notice failed first, then passed.

`npm run verify` completed successfully:

- Ruff lint and format: passed, 63 files already formatted
- Mypy: passed, 35 source files
- Engine: 392 passed, 2 skipped, 5 expected failures
- Dashboard ESLint and TypeScript: passed
- Dashboard: 77 tests passed in 10 files, including 8 new acceptance tests
- Next.js production build: passed, 1,607 pages generated

The existing expected failures document no-shared-ids recall misses; they are not fixed or hidden
by this UI work. The two skips concern a snapshot that repeats its CRM nickname rather than
providing a distinct enrollment value.

A production server HTTP smoke test also passed:

| Route | Verified |
|---|---|
| `/` | 200, guide links, matching-before-masking disclosure, seen-fixture caveat, separate-demo text |
| `/clusters` | 200, cluster question |
| `/clusters/crm-C-00083` | 200, Robert Murphy and golden record |
| `/review?rule=GR-007` | 200, eight filtered items, Kevin Khan, already-joined notice |
| `/review?rule=GR-005` | 200, nine filtered items, Gabrielle and Carlos, different-people suggestion |
| `/benchmark` | 200, hypothetical label and shared-ID explanation |
| `/demo-run/manifest.json` | 200, synthetic label and model tiers off |
| `/clusters/not-a-person` | 404 |

`git diff --check` passed. The engine, committed demo artifacts, and dependency manifests/locks
remain unchanged from the base commit.

## Remaining release checks

No browser was launched for this change. Current desktop/mobile visual layout, browser history,
keyboard interaction, and console checks still need a supported browser pass; the old screenshots
are not evidence for this new UI. HTTP checks are not browser checks.

No push, PR, merge, deployment, or paid model call was made for this change. Publication requires
approval, then CI for the published commit and a production-route check. This note is local
verification evidence, not a claim that the public site contains the new changes.
