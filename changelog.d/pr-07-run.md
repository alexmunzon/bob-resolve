## PR 7: Review queue, run command, and demo run (2026-10-05)

- New `bob-resolve run` command: loads, matches, and writes one run folder with the manifest, golden people (CSV and Parquet), households, merge log, review queue, and scorecard. A run folder is never changed after it is written.
- Review queue: one item per doubtful pair or conflict, with both records side by side (MBI masked to the last 4), the evidence per field, the suggestion, the guard rail ids, and a severity. High means an identity conflict or a merge that would move an active policy.
- New `bob-resolve review apply`: takes a reviewer's decisions file and writes a new run. The old run is kept as it was, and the merge log only gains new lines.
- Scorecard: blocking recall, auto-merge precision, recall after review, queue size, and counts per tier, each labeled "measured on synthetic data" with the side and shared-ids mode.
- `npm run demo` writes the committed demo run (derived side, no shared ids): 2,025 people, 1,425 households, 2,139 automatic merges, 89 items to review, precision 1.0, recall after review 1.0 (measured on synthetic data). Jev and the LLM arm are off, with zero calls and zero cost.
