# PR 13 notes: benchmark report

Each run folder writes `benchmark.json` from its own `manifest.json` and `scorecard.json`. To rebuild a report for
one or more saved runs, from the repo root:

```sh
cd engine
uv run python scripts/build_benchmark.py --run ../dashboard/public/demo-run --out /tmp/benchmark.json
```

Every figure is measured on synthetic data. `snapshot` and `derived` keep their own dataset status; `multi-a-b` is
`seen` because the matcher has been tuned against that world. A run is `held_out` only when its manifest records
`benchmark_status: "held_out"`, and only a two-agency run may. No held-out result is present.

Automatic results count only auto-merges: automatic precision, automatic recall (true pairs found by auto-merges,
divided by all true pairs) and automatic F1. A same-person suggestion is not a resolution until a reviewer confirms
it, so the engine's "recall after review" figure appears only as `recall_if_suggestions_confirmed`, a hypothetical.
Human review appears as counts: merges a reviewer confirmed and items awaiting review. These come from the
scorecard's `resolution` block. `suggested_same_person` is counted from the engine's scores before any review, so a
confirmed pair is in both that count and `human_confirmed_merges`; the two are never added. A run without the block
reports null rather than the suggestion figure.

The demo (derived from the answer key, shared ids on, no model tiers used): automatic precision 1.0, automatic
recall 0.996308 (2,159 of 2,167 true pairs), automatic F1 0.998151. No same-person suggestions were made, 19 items
await review and no reviewer has confirmed a merge. On the two-agency world the gap shows: automatic recall 0.959147
against 0.982693 if every suggestion were confirmed. These are synthetic results, not unseen evaluation. Model
comparison, cost and latency are left for later.
