# bob-resolve

bob-resolve reads an insurance agency's client list and its carrier enrollment export and decides
which records belong to the same real person. It builds one golden record per person, with the
source file and row of every field, groups people into households, and logs every merge. Pairs it
is not sure about go to a human review queue instead of being merged.

## Status

v0.1.0: engine complete on synthetic data, Jev and LLM arms not built yet, measured on synthetic
data only. There is no dashboard page yet and no real client data has ever been used.

## Run it

```bash
npm run verify        # every check: lint, types, tests, dashboard build
npm run demo          # writes the demo run to dashboard/public/demo-run/
cd engine && uv run bob-resolve run --enrollment snapshot --out ../runs --run-id first
```

A human decision file can then be applied with `bob-resolve review apply` (see docs/pr-7-notes.md).

## Demo scorecard (measured on synthetic data)

The demo uses the enrollment side derived from the answer key, with shared ids (MBI) withheld
from matching. Synthetic data, as of 2026-10-01.

| Measure | Value |
|---|---|
| Records in | 3,887 |
| People | 2,025 (25 left split, waiting in the review queue) |
| Households | 1,425 |
| Auto-merges | 2,139 |
| Auto-merge precision | 1.0000 (target 0.99) |
| Blocking recall | 1.0000 (target 0.98) |
| Recall after review | 1.0000 (target 0.90) |
| Review queue | 89 (0 high, 89 medium) |

These numbers come from synthetic data the project generated itself. They say nothing yet about
real agency files.

## Known limits

- Jev (the second matching opinion) and the LLM arm are not built. Every gray pair goes to a
  human, and no model is called.
- Measured on synthetic data only. The hard cases score recall 0.89 with shared ids on: Nina
  Dorsey's two records stay split until a human decides.
- With shared ids withheld, the shared-MBI conflict check (GR-002) cannot fire.
- The dashboard does not show the demo run yet.
- People.csv is about 1.8 MB because each field carries six provenance columns.
- The demo's queue has no high items: every "same person" suggestion joins a client to that
  client's own policy, so no money would move. A richer rule needs premium data the fixtures lack.
