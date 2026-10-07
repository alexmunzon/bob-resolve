## Offline integration CLI and workflow registration (2026-10-07)

- Add `bob-resolve integration resolve` for pinned Intake evidence, with explicit agency and run IDs, a frozen date, and synthetic input labeling. Its immutable canonical envelope retains native resolution, scores, merge evidence, and the downstream packet; `integration packet` extracts that packet to a new file.
- Register the offline broker workflow as `bob-resolve workflow`. Workflow review remains separate from identity merges and sends no messages.
- Add cross-repository command examples and focused tests for deterministic reruns, immutable output publication, stale evidence, malformed inputs, and root CLI registration.
