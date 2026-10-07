# Offline second-opinion sidecar

This unreleased command connects the existing advisory contract to native Intake integration
resolution. It is separate from the existing `--llm-mode` saved-explanation feature. No
provider is contacted, no credentials are read, and no match or human review is approved.
All examples require synthetic inputs.

From `engine`, after `bob-resolve integration resolve` has written a native resolution:

```sh
uv run bob-resolve advisory sidecar \
  --source-packet /path/to/intake-packet.json \
  --resolution /path/to/bob-resolution.json \
  --intake-root /path/to/intake-run \
  --out /path/to/new-advisory.json
```

Default `off` emits disabled review entries and never opens fixture files. It still validates
source artifacts and recomputes the deterministic resolution. Existing output files are never
replaced; output must be outside the Intake source directory.

To exercise offline replay, create a local directory of hand-written synthetic JSON fixtures.
Each filename is the emitted `request.key` followed by `.json`. Its body is:

```json
{
  "version": "bob-second-opinion-v1",
  "request_key": "COPY_THE_EXACT_REQUEST_KEY_FROM_THE_OFF_SIDECAR",
  "origin": "hand_written_synthetic_fixture",
  "opinion": "unsure",
  "evidence": ["dob"]
}
```

Choose evidence actually present in that request, then rerun with `--mode replay --responses
/path/to/fixtures` and a new output path. This is an illustrative fixture template, not a model
recording or a universal answer. Missing, malformed, oversized, stale, contradictory and
symlinked fixture files stay pending without a suggestion. Every accepted fixture remains
`needs_review`. `live` is not a CLI mode. Fixture reads use anchored directory descriptors,
no-follow/nonblocking opens and regular-file checks, including when paths are replaced
during the read. Platforms without these safe-open capabilities fail closed.

Bindings include the canonical resolved packet hash, canonical GRAY-pair queue hash, sorted
source record-ID hash, and exact saved resolution byte hash. Original artifact byte pins are
verified before deterministic recomputation; altered scored evidence is refused. Source row
citations remain outside the minimized request. The command neither rewrites the source run
nor feeds advice into scoring, merge logs, review decisions or downstream identity output.

This is CLI-only integration. The dashboard does not import this new sidecar yet. Existing
brown styling, explanation replay, and interrupted-overwrite recovery are unchanged. No live
model quality or real-client benefit is demonstrated by these synthetic fixtures.
