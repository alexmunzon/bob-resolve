# Release 0.1.0 notes

Fixes from the release review, before a local v0.1.0 tag. Measured on synthetic data, as of
2026-10-01. Jev and the LLM arm are off. Tests: `engine/tests/unit/test_release_0_1_0.py` and
`engine/tests/e2e/test_snapshot.py`. New constants under `# Release 0.1.0` in config.py.

## F5: review apply can no longer replace its parent run
- Reproduced first: `review apply --run X --out <parent of X> --run-id <X's id> --overwrite`
  replaced X with the new run, so the "never touched" old run was gone.
- Now refused when the new folder's real path (symlinks followed) equals the old run's folder,
  holds it, or sits inside it, and when the new run id equals the parent's id, even in another
  folder. The check runs before anything is written. Test covers same folder, ancestor,
  descendant, a symlinked runs folder, and the same id elsewhere.

## F6: decisions_applied counts only kept merges
- `decisions_applied` in the manifest is the number of this review's "same person" merges that
  survive the PR 6 cluster check. Merges the check cuts again are listed in `decisions_cut` (as
  record id pairs) and come back to the queue as cluster conflicts. The CLI prints both.
- Found while testing: a second `review apply` on a reviewed run lost the first review's merges,
  because only the new file's labels were forced. Now the manifest records `review_pairs` (every
  human merge in effect), the next review carries them forward, and `decisions.jsonl` keeps every
  earlier label. Tested with a run, a review, and a second review.

## F7: severity and order
- High only for IDENTITY_CONFLICT, or a "same person" suggestion where two records each hold an
  active policy and those policies belong to different client ids. A CRM client's owner is its
  own client id; an approved enrollment row's owner is the client whose policy id equals its
  policy number in policies.csv, or the row itself when no policies file names one (hard cases).
  Everything else is medium.
- Sort: high first, then `cutoff_distance` (how far the item's closest pair score sits from the
  nearer cutoff, smallest first; an item with no scored pair counts as 0), then item id. The
  distance is stored on each item so the reviewer sees why it is near the top.
- New split (high / medium): demo (derived, no shared ids) 0 / 89, was 65 / 24. Snapshot with
  shared ids 0 / 16, was 11 / 5. Snapshot no shared ids 0 / 61. Derived with shared ids 0 / 16.
  Why zero high: every "same person" suggestion on the fixtures joins a CRM client to that same
  client's own enrollment row (26 of them hold two active policies, both owned by one client), so
  no money or coverage would move. On the hard cases with shared ids the two GR-002 items stay high.

## F9: no full MBI in public files
- New `--mask-mbi` run option masks the MBI column in people.csv (and Parquet) to the last 4
  characters, like the queue. `npm run demo` passes it. A run whose `--out` path has a folder named
  `public` is refused without it, so the dashboard can never serve a full MBI by accident.
- The full run folder outside `dashboard/public` keeps the synthetic MBI. `review apply` carries
  the parent's masking choice forward.
- Test: every file under `dashboard/public` is searched for any 11-character MBI-shaped value
  (dashes allowed); there are none.

## F10: version and changelog
- Version 0.1.0 in pyproject.toml, `__init__.py`, and uv.lock. The demo manifest records it.
- `fix-gr-005.md` and `fix-review-1.md` were renamed to `pr-05b-gr-005.md` and
  `pr-04b-review-1.md` (one commit), then every fragment was assembled into CHANGELOG.md under
  "## 0.1.0 (2026-10-05)" in PR order and deleted, as changelog.d/README.md says. This release's
  own entry is "PR 7b" because the roadmap's PR 8 is the dashboard shell.
- README is an honest interim page: what it does, status, three commands, the demo scorecard
  labeled synthetic, and known limits.

## F11: commands and deny lines
- CLAUDE.md lists `bob-resolve run`, `bob-resolve review apply`, and `npm run demo`.
- `.claude/settings.json` denies `Bash(cat .env*)` and `Bash(*echo $ANTHROPIC_API_KEY*)`.

## F12: end-to-end tests
- The hard cases run in both shared-ids modes. Example 7 in no-shared-ids mode states why it
  differs: the MBI is withheld, so the GR-002 conflict cannot be seen; the pair still stays apart.
- Example 1 no longer uses `people_left_split`. It joins every answer-key pair except the true
  pairs still waiting in the queue as gray pairs, and the groups must equal the run's people
  exactly (count and members).
- Example 5: each Jr and Sr pair is either queued suggesting "different people", or absent
  because the rules arm itself rejects it (recomputed in the test) or never pairs it.
- A test rebuilds the demo from the `npm run demo` script into a temp folder and compares every
  file byte for byte with the committed copy. The demo was regenerated twice, byte-identical.

## Not fixed (open)
- Jev and the LLM arm are not built.
- Severity has no premium or commission data, so "would move money" means "two different clients
  each hold an active policy".
- The dashboard does not render the demo run yet (roadmap PR 8).
