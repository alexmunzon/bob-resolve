# Documentation

Start with the [repository overview and live walkthrough](../README.md). This index distinguishes
the current rules-only demo from historical implementation notes and dated checks.

## Current guides

- [Specification](../SPEC.md): intended matching, guard rails, survivorship, and review behavior.
- [Architecture and repository map](../README.md#architecture): engine, immutable outputs, and dashboard.
- [Locked local setup](../README.md#run-it) and [contributing](../CONTRIBUTING.md): installation and checks.
- [Security and threat boundaries](../SECURITY.md): synthetic/public scope, reporting, known tooling risk.
- [Snapshot provenance](../fixtures/agency-a-snapshot/SOURCE.md) and
  [derived enrollment provenance](../fixtures/agency-a-derived/SOURCE.md): frozen inputs and restored values.
- [Committed demo manifest](../dashboard/public/demo-run/manifest.json): versions, hashes, cutoffs,
  and model-use/cost evidence. [Scorecards and limits](../README.md#demo-scorecard-measured-on-synthetic-data)
  explain what those synthetic measurements establish.

## Dated evidence

- [Recruiting-demo acceptance, 2026-10-06](recruiting-demo-acceptance-2026-10-06.md): earlier local tests
  and HTTP checks, with its tested baseline and remaining browser/publication checks.
- [Recorded walkthrough, 2026-10-06](v1-walkthrough-2026-10-06/README.md): screenshots of the original
  capture commit. Images are historical evidence, not proof of the latest live layout.
- [Security review, 2026-10-06](security-review-2026-10-06.md): bounded dependency/source inventory,
  known advisory, coverage exclusions, and CI hardening.
- [Repository hygiene verification, 2026-10-06](hygiene-verification-2026-10-06.md): exact local
  checks, fresh lockfile audits, unchanged scope, and remaining release checks.

## Implementation history

These notes describe their own revision and may contain superseded counts or unfinished work.
Use the current README and committed artifacts for the demo's present claims.

- [Release 0.1.0](release-0.1.0-notes.md), [changelog](../CHANGELOG.md), and
  [pending changelog fragments](../changelog.d/README.md).
- [Initial two-agency evaluation](pr-10-notes.md) and [seen-world fixes](pr-10b-notes.md):
  the matcher was tuned on this world; it is not a held-out evaluation.
- [GR-005 investigation](gr-005-notes.md), [review safeguards](review-1-notes.md),
  and [review score explanations](review-2-score-notes.md).
- [Architecture decision-record index](adr/README.md): planned decisions, not completed ADRs.

The dashboard is read-only. Review changes require the CLI and a new immutable run. Automatic
merges, reviewer-confirmed merges, and hypothetical suggestion-inclusive figures are separate;
MBI masking happens after matching. Without shared identifiers, the seen two-agency automatic
cross-agency client-pair recall is 2 of 320 (0.63%). None of these results establishes accuracy on
real or unseen agency files.
