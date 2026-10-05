# Architecture decision records

One short file per lasting decision, named `NNNN-short-name.md`, with context, the decision, and its
consequences. None are written yet. Planned:

- 0001: Error policy. A false merge is worse than a missed match: auto-merge only when very sure,
  everything doubtful goes to review (targets: precision at least 0.99, recall after review at least 0.90).
- 0002: Blocking keys and the blocking recall target (at least 0.98).
- 0003: Rules first, with guard rails that override the score. Jev and LLMs only see the gray zone and
  never override a guard rail.
- 0004: Golden record survivorship: identity fields from the most authoritative source, contact fields
  from the most recent record, IDENTITY_CONFLICT instead of guessing.
- 0005: Append-only merge log; a correction is a new line, never a rewrite.
- 0006: Frozen snapshot of agency-intake-kit fixtures for phase 1, then the agency-data-commons generator.
- 0007: Synthetic data only, no SSN, and minimized model payloads (no free-text notes).
- 0008: Static-first dashboard that renders a committed demo run.
