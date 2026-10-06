## PR 13: Benchmark report builder (2026-10-06)

- Add a deterministic report builder for metrics saved in immutable run folders, labeled "measured on synthetic data".
- Report automatic precision, recall and F1 from auto-merges only. "Recall if every same-person suggestion were confirmed" stays separate as a hypothetical, next to merges a reviewer actually confirmed and items still awaiting review. A run without resolution counts (added to runs by the next change) reports these as null, never the suggestion figure.
- Only a two-agency run can be marked held out, and only through its status. Refuse impossible inputs: missing, negative or non-numeric counts, more found pairs than true pairs, rates outside 0 to 1. Errors name the run.
- List which model tiers actually made calls. Model comparison, cost and latency are left for later.
