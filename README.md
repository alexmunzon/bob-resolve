# bob-resolve

bob-resolve reads an insurance agency's client list and its carrier enrollment export and decides
which records belong to the same real person. It builds one golden record per person, with the
source file and row of every field, groups people into households, and logs every merge. Pairs it
is not sure about go to a human review queue instead of being merged.

**[Live demo](https://bob-resolve-nine.vercel.app)** · [Walkthrough](#two-minute-walkthrough) ·
[Architecture](#architecture) · [Local setup](#run-it) · [Documentation](docs/README.md) ·
[Contributing](CONTRIBUTING.md) · [Security and boundaries](SECURITY.md)

Built to make identity decisions inspectable: rules and guard rails, field-level provenance,
immutable review runs, and a dashboard that explains the evidence. This is a portfolio demonstration,
not a service for processing real insurance records.

## Status

v0.1.0: a working rules engine and read-only dashboard, measured on synthetic data only.
Overview, Clusters, Review queue, and Benchmark render the committed demo run. No real client
data has ever been used. Jev and the LLM arm are not built; no model is called.

Start with the walkthrough below. [SPEC.md](SPEC.md) defines the intended behavior; the
[documentation index](docs/README.md) separates current guides from historical implementation notes
and validation evidence.

## Agency Data Trust Series

Separate demos, shared trust principles. Read them in this order:

1. [Intake Kit](https://agency-intake-kit.vercel.app): inspect incoming agency files and their data-quality issues.
2. [Bob Resolve](https://bob-resolve-nine.vercel.app): explain which records became one person and which need a human.
3. [Plan Diff](https://plan-diff.vercel.app): inspect year-over-year plan changes and their evidence.

These are independent demos with separately committed runs. This synthetic Bob demo reads a frozen intake-fixture
snapshot with an enrollment side derived from its answer key, not Intake Kit's current `clean/` output.

## Two-minute walkthrough

1. [Strong match](https://bob-resolve-nine.vercel.app/clusters/crm-C-00083): Bob and Robert Murphy become one
   person. Open the golden field sources and merge log; the nickname stays as an alias.
2. [Weak match](https://bob-resolve-nine.vercel.app/review?rule=GR-007): Kevin Khan's name and birth date agree,
   but no extra identifier agrees. This direct pair waits for a human despite its high score. Other accepted
   links have already placed these records in one cluster; the queue now makes that distinction explicit.
3. [Conflicting pair](https://bob-resolve-nine.vercel.app/review?rule=GR-005): incompatible first names keep
   Gabrielle and Carlos Smith from merging. The suggestion is "Different people."
4. [Benchmark](https://bob-resolve-nine.vercel.app/benchmark): compare automatic results with the separately
   labeled hypothetical suggestion figure. No reviewer has confirmed a merge in this demo.

The dashboard is read-only. Review decisions are applied through the CLI to a new immutable run.
The [recorded walkthrough](docs/v1-walkthrough-2026-10-06/README.md) includes screenshots and the original
capture commit; those images document that earlier build.

**Important limit:** without shared identifiers, the seen two-agency regression set automatically merges
only 2 of 320 cross-agency client pairs (0.63%). With shared identifiers it finds 78.75% automatically.
These results do not establish accuracy on unseen data or real agency files. Full figures are below.

## Run it

Prerequisites: Node 24, Python 3.12, and uv. No API key or paid service is needed.
Run these commands from the repository root. Dependencies are locked separately in
`engine/uv.lock` and `dashboard/package-lock.json`; the root package has scripts only.

```bash
(cd engine && uv sync --locked)
(cd dashboard && npm ci)
npm run verify        # every check: lint, types, tests, dashboard build
(cd dashboard && npm run dev)  # open http://localhost:3000
```

The committed demo is ready to view without regenerating data. To reproduce it deliberately,
`npm run demo` overwrites only `dashboard/public/demo-run/` with the fixed-clock, MBI-masked
synthetic run; do not use it for private files. If your home cache is read-only, use
`UV_CACHE_DIR=/tmp/bob-resolve-uv` for uv commands and `npm ci --cache /tmp/bob-resolve-npm`.

To generate a separate run and apply a human decision file:

```bash
cd engine
uv run bob-resolve run --enrollment snapshot --out ../runs --run-id first
uv run bob-resolve review apply --run ../runs/first --decisions decisions.jsonl --out ../runs --run-id reviewed
```

Use the Review queue's "How to decide" panel for the JSONL format and copy each chosen item's own
line. The old run is never edited. Local run output is not published by these commands.

## Architecture

1. **Load and normalize:** the Python engine reads pinned synthetic CRM, policy, and enrollment
   fixtures and retains source file, row, and raw hashes.
2. **Block and score:** candidate generation narrows the comparisons; deterministic rules score
   direct pairs. Guard rails and authoritative identity conflicts can prevent an automatic merge
   even when the score is high.
3. **Resolve and explain:** accepted links form clusters, then golden records and households.
   Outputs include field provenance, an append-only merge log, a review queue, a scorecard, and a
   manifest. A queued direct pair may already share a cluster through other accepted links.
4. **Review as a new run:** the CLI applies an explicit decision file and writes a separate run,
   carrying prior decisions and appending to the log. The dashboard does not submit decisions.
5. **Present committed evidence:** the Next.js dashboard reads the public demo artifacts. The
   published site has no client-file upload or editable review workflow. Jev and the LLM arm are
   not implemented; this run calls no model.

Repository map: `engine/` contains matching and CLI code; `dashboard/` contains the read-only
presentation; `fixtures/` contains synthetic inputs and provenance; `runs/` holds ignored local
outputs; `docs/` holds guides and dated evidence. [SPEC.md](SPEC.md) is the behavioral reference.

## Data and provenance

- Synthetic data only, no real people or contacts, and no SSN. Source records remain linked to
  file, row, and raw hash; every golden field names its winning source and deciding rule.
- The CRM fixture is pinned to Intake Kit commit `9064b4e`; [snapshot provenance](fixtures/agency-a-snapshot/SOURCE.md)
  records the hashes. The [derived enrollment provenance](fixtures/agency-a-derived/SOURCE.md) explains
  precisely which answer-key values were restored and which defects cannot be measured here.
- The published run uses MBI for matching first, then masks it to the last four characters in
  displayed and downloadable records. Masking is not a no-shared-ids evaluation. That separate mode
  withholds MBI and linking policy IDs from blocking and scoring.
- [The demo manifest](dashboard/public/demo-run/manifest.json) records source and output hashes,
  cutoffs, versions, zero model calls, and zero model cost. The fixed clock makes reruns byte-identical.
- Review labels are stored, not learned from. Conflicting authoritative identity fields go to review;
  a high score never overrides a guard rail.
- Hashes support reproducibility and change detection, not proof that an input is safe or true.
  [Security review](docs/security-review-2026-10-06.md) records a bounded dependency/source check,
  including the known unpatched development-tool advisory and areas it did not cover.

## Demo scorecard (measured on synthetic data)

The demo uses the enrollment side derived from the answer key, with shared ids (MBI) used for
matching. The MBI is masked to its last 4 characters in the published people.csv. Synthetic data,
run `demo-run` as of 2026-10-01, read from the committed dashboard/public/demo-run/scorecard.json
at commit b15baf0 (a fresh `npm run demo` on that commit gives identical files).

| Measure | Value |
|---|---|
| Records in | 3,887 |
| People | 2,000 (0 left split) |
| Households | 1,400 |
| Auto-merges | 2,159 |
| Auto-merge precision | 1.0000 (target 0.99) |
| Blocking recall | 1.0000 (target 0.98) |
| Automatic recall | 0.9963 (2,159 of 2,167 true pairs) |
| If every same-person suggestion were confirmed | 0.9963, hypothetical; no same-person suggestions in this run |
| Reviewer-confirmed merges | 0 |
| Review queue | 19 (0 high, 19 medium) |

These numbers come from synthetic data the project generated itself. They say nothing yet about
real agency files.

## Two-agency scorecard (seen, measured on synthetic data)

Generated by agency-data-commons v0.2.0: two agencies (agency A is the snapshot, agency B comes from
the commons generator) that share 300 people, with maiden and hyphenated names, moves, shared
household contacts, and look-alikes such as twins. The matcher was tuned on this world in PR 10b,
so it is a seen regression set, not held out. These figures are not accuracy on unseen data.

```bash
cd engine
uv run bob-resolve run --world multi-a-b --out ../runs --run-id two-agency-ids
uv run bob-resolve run --world multi-a-b --no-shared-ids --out ../runs --run-id two-agency-no-ids
```

| Shared ids | Auto-merge precision | Automatic recall (all pairs) | Automatic recall (320 cross-agency client pairs) | If every suggestion were confirmed (320 pairs, hypothetical) | Look-alike pairs merged (of 164) | Awaiting review |
|---|---|---|---|---|---|---|
| on | 1.0000 | 0.9471 | 0.7875 | 0.8125 | 0 | 507 |
| off | 1.0000 | 0.0085 | 0.0063 (2 of 320) | 0.1250 | 0 | 5,218 |

Automatic figures count only merges the engine made on its own. The hypothetical column counts pairs
the engine only suggested as the same person; no person has confirmed them. The rest are not lost:
every one of the 320 client pairs is either merged or waiting in review. With shared ids, the other 60
wait marked unsure (56 of them for GR-008 alone); without shared ids, 280 do. A reviewer can still
confirm them. Without shared ids the engine merges almost nothing on its own (0.0085 across all
pairs, 2 of the 320 cross-agency client pairs) and sends nearly every pair to review. These figures are lower than before the identity
safety fixes (PRs 21a to 21c): since GR-008, people whose only extra shared detail is a street wait
for a person instead of merging, which lowers automatic recall and keeps wrong merges at 0.
Measured 2026-10-06 at commit b15baf0 (after PR 21c). History: docs/pr-10-notes.md and
docs/pr-10b-notes.md.

## Known limits

- Jev (the second matching opinion) and the LLM arm are not built. Every gray pair goes to a
  human, and no model is called.
- Measured on synthetic data only. The hard cases score recall 0.89 with shared ids on: Nina
  Dorsey's two records stay split until a human decides.
- With shared ids withheld, the shared-MBI conflict check (GR-002) cannot fire.
- The Changes page, direct use of Intake Kit's current `clean/` output, held-out evaluation,
  Jev/LLM comparison, and model cost/latency benchmarking remain outside this rules-only demo.
- The published dashboard is a fixed run, not an upload service or an editable production workflow.
- People.csv is about 1.8 MB because each field carries six provenance columns.
- The demo's 19 review items are all medium severity, with no same-person suggestions. High-severity
  identity conflicts are covered by the hard-case fixtures and tests, not by this published queue.
  A richer financial-impact rule needs premium data the fixtures lack.
