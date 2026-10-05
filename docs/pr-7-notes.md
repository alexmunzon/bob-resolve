# PR 7 notes: review queue, run command, run folder, scorecard, demo

Code in `engine/src/bob_resolve/queue/` and `run/`; constants under `# PR 7` in config.py.
Jev and the LLM arm are off: every run records mode off, zero calls, zero cost. Measured on
synthetic data, as_of 2026-10-01.

## Commands
- `bob-resolve run --enrollment snapshot|derived|hard-cases [--no-shared-ids] --out <runs> --run-id <id> [--overwrite] [--as-of <date>] [--now <iso>] [--no-parquet]`
- `bob-resolve review apply --run <run folder> --decisions <file> --out <runs> --run-id <new id>`
- `npm run demo`: derived side, no shared ids (the honest headline mode), writes
  `dashboard/public/demo-run/` (JSON and CSV only). Byte-identical on a second run.

## Results (scorecard of each run)
| Enrollment side | Shared ids | People | Households | Auto-merges | Queue (high / medium) | Precision | Recall after review |
|---|---|---|---|---|---|---|---|
| snapshot | on | 2,000 | 1,400 | 2,167 | 16 (11 / 5) | 1.0000 | 1.0000 |
| derived from the answer key | off (demo) | 2,025 | 1,425 | 2,139 | 89 (65 / 24) | 1.0000 | 1.0000 |

Blocking recall 1.0000 and no person holding two answer-key people on all four combinations
(tests/e2e/test_snapshot.py). 9 unidentifiable rows. The demo leaves 25 people split (25 extra one-person households): their 28
true pairs wait in the queue with "same person".

## Decisions
- **Run side `hard-cases`.** The run command also takes the hand-written hard cases, so SPEC
  examples 3 to 7 (and 9, 10) run through the same command as the snapshot.
- **Queue items:** kind `gray_pair` (one per gray pair, every one queued: SPEC example 8),
  `cluster_conflict`, or `identity_conflict` (authoritative records in one cluster disagree).
  A gray pair stopped by GR-002 has reason IDENTITY_CONFLICT. Rule ids come from the pair's guard
  rails (GR-001 to GR-005), or `SCORE-GRAY` when only the score put it in gray. The suggestion
  is the scorer's (GR-005 gives "different people"). Item id is a hash of kind plus record ids,
  stable across runs.
- **Severity high** for IDENTITY_CONFLICT, or when two or more of the item's records each carry
  an active policy (an approved enrollment row, or a CRM client with an ACTIVE policy), so a
  merge would move coverage or a commission line. Otherwise medium. Sort: high first, then
  reason (identity, cluster, gray), then highest score, then item id.
- **Minimized records:** names, DOB, address, phone, email, MBI masked to the last 4, source
  file and row, and the active policy flag. No notes, policy numbers, or full MBI.
- `already_one_person` marks a gray pair whose records were joined anyway by other auto-matches.
- **Households:** people linked through the agency's own CRM household ids; a person with only
  enrollment rows is a household of one. Not a match signal (it is never scored).
- **Immutable folder:** written to a temp folder, then renamed into place. An existing folder
  is refused unless `--overwrite`, which keeps the old one until the new one is complete. The
  manifest lists every output file's SHA-256; `review apply` refuses an old run whose files
  changed, or whose input files no longer match their recorded hashes.
- **Determinism:** with `--now`, every time in the folder is that value and `timings_ms` is
  null (wall-clock timings would break byte-identical reruns). Without `--now`, stage timings
  are recorded. Input paths are stored relative to the fixtures folder, never absolute.
- **Review apply is full, not a stub.** Decisions file: JSONL, one line per item:
  `{"item_id", "decision": "same_person"|"different_people", "reviewer", "decided_at", "note"?}`.
  A "same person" label on a gray pair becomes a merge with tier `review` and rule id
  `REVIEW-DECISION`; every other label (different people, cluster or identity items) is stored
  in the new run's `decisions.jsonl`, not applied. The new merge log is the old log's bytes plus
  new lines only. Decided items leave the new queue. The old run is never touched. Labels are
  stored, never learned from (SPEC section 4). A human may merge a pair a guard rail stopped;
  the rails only forbid automatic merges.
- Scorecard metrics (precision, recall after review) are from the rules arm before any review
  decision; review merges are counted separately under `merges.review`.

## Risks
- Severity "high" covers 65 of the demo's 89 items, because most records hold an active
  policy. A finer rule (premium at stake, commission split) needs data the fixtures lack.
- A human "same person" on a pair that conflicts inside its cluster is still cut by the PR 6
  cluster check and comes back as a CLUSTER_CONFLICT item. Tested only through the code path.
- The demo run is about 2.7 MB (people.csv carries six provenance columns per field).
- On the hard cases, Nina Dorsey (example 7) is left split: her pair is GR-004 "unsure", the
  reviewer decides. Recall on the hard cases is 0.89; the targets apply to the snapshot sides.
