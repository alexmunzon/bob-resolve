# ADR 0010: Consolidate review summaries and put caveats beside their evidence

Date: 2026-10-08. Status: accepted for local implementation; release review pending.

## Context

The V2 overview repeated its unresolved workload in three panels and repeated synthetic-data caveats across the sidebar, global notice and page. Reviewers need an obvious next action without losing source evidence or mistaking a candidate grouping for confirmed identity.

## Decision

Use one shared, visible synthetic-demo and human-review notice. Keep the read-only restriction beside the review action, candidate-identity qualifications beside grouped records, and browser-local, unauthenticated workflow warnings beside the workflow. Show unresolved pairs once in the default overview; retain severity, suggestions and the independently recorded review status in a native disclosure within that summary. Preserve differences and missing values in recorded status rather than deriving replacements from the queue count.

Move the identifier-masking explanation and demo's non-held-out limitations into the existing benchmark disclosure alongside its measurements. This supersedes ADR 0009's requirement to keep those technical limitations expanded on the default overview; measurements and their caveats appear together. The Benchmark page retains its run-specific caveats.

Use Bob Resolve as the display name and place the theme control after the series navigation in the sidebar footer. Evidence workflow remains a distinct function and route.

## Consequences

The initial view has one unresolved-workload total and one general trust notice. Keyboard-accessible disclosures preserve detailed evidence, unknown states and source actions. Matching rules, calculations, source records, fixtures, immutable outputs and workflow semantics are unchanged. There is no production-access claim, new approval authority, connected pipeline, recording or analytics activation.
