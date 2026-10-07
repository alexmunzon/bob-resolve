## PR 13b: Benchmark report in every run (2026-10-06)

- Each run folder now includes `benchmark.json`, and its hash is recorded in the manifest.
- The run scorecard gains a `resolution` block: true pairs, pairs found automatically, pairs the engine suggested as the same person before any review, merges a reviewer confirmed and items awaiting review.
- The committed demo run is regenerated with these files.
