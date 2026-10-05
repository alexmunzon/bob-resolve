# PR 5 notes: scoring, cutoffs, and guard rails (rules arm)

Code in `engine/src/bob_resolve/score/`; constants under `# PR 5` in config.py.
`bob-resolve score --enrollment snapshot|derived [--no-shared-ids]` prints the numbers below.
Measured on synthetic data.

## Results (2,167 true pairs)

| Enrollment side | Shared ids | Auto-merge precision | Auto-merge count | Gray | Reject | Recall after review |
|---|---|---|---|---|---|---|
| snapshot | on | 1.0000 | 2,167 | 16 | 1,269 | 1.0000 |
| snapshot | off | 1.0000 | 2,167 | 57 | 1,228 | 1.0000 |
| derived from the answer key | on | 1.0000 | 2,167 | 16 | 1,271 | 1.0000 |
| derived from the answer key | off | 1.0000 | 2,139 | 85 | 1,230 | 1.0000 |

Guard rail hits (every side and mode): GR-001 0, GR-002 0, GR-004 0, GR-003 273 (271 already below the
low line, 2 stopped in gray; none on a true pair). GR-001 and GR-002 fire only on the hard cases.
On the derived side without shared ids, the 18 transposed and 10 month-day swapped birth dates
land in gray with "same person" (score 0.989, just under the high line), not auto-merged.

## How the score works
- `compare(a, b)` gives each field a level: first name (equal, nickname, close, far, plus the
  Jaro-Winkler number), last name (equal, close, far, plus Jaro-Winkler and metaphone equal),
  suffix (same, one missing, different), DOB (exact, transposition, month-day swap, one edit,
  far), MBI (same, different; None in no shared ids mode), zip5, street, phone, email.
  A missing value is None and adds nothing.
- Score: logistic of a bias plus one hand-set weight per level (Fellegi-Sunter style log odds),
  so it lies in [0, 1]. Agreement on contact fields adds a little; disagreement costs little,
  because people move. A different MBI costs a lot (-6), because twins share everything else.
- **Cutoffs: high 0.99, low 0.10.** High 0.99 means names and DOB must agree exactly (or one
  nickname or one surname typo) when no other field confirms; a DOB variant needs one more
  agreeing field (MBI, phone, address) to auto-merge. The hardest true pair auto-merged scores
  0.9933; the highest non-true pair scores 0.78. Low 0.10 keeps the gray queue small (16 to 85)
  while every true pair sits far above it.
- **Gray suggestion:** "same person" when score is at least the midpoint (0.545) and no guard
  rail fired; "different people" when a rail fired; otherwise "unsure". Recall after review counts
  auto-matches plus gray "same person" (SPEC decision 2).

## Guard rails (override the score, rule id recorded on the pair)
- GR-001: different generational suffix never auto-matches.
- GR-002: shared MBI with a DOB that is neither within one edit nor a month-day swap: always
  gray with reason IDENTITY_CONFLICT, whatever the score (SPEC: never guess).
- GR-003: shared phone or email, no shared MBI, and names plus DOB not all compatible.
- GR-004 (ambiguous identity key, orchestrator decision before merge). The identity key is
  (canonical first name, normalized last name, DOB); a record missing any part has no key. A key
  is ambiguous when two or more records hold it and at least one pair of holders conflicts:
  different MBI (shared ids on, both present), different suffix (both present), or a different
  non-blank phone AND street address AND email (all three present on both and all three differ).
  Then every scored pair whose two records both hold that key goes to gray, suggestion "unsure",
  rule id GR-004, whatever the score. Checked once per run over all records, not per pair.
  Snapshot and derived: no key is held by two different people, so 0 hits and no change in the
  table. Hard case example 9 (HC-010 and HC-011, two Owen Marlowes, same DOB, nothing else in
  common) tests it; Dave and David (same key, no conflicting holder) still auto-merge.
- GR-001 and GR-003 only stop an auto-match. A pair they hit that scores below the low line is
  still rejected (rejecting never merges anyone); the rule id is still recorded.

## Decisions
- A month-day swap counts as close for GR-002 (SPEC updated); such pairs are scored. Tested.
- Policy number is never a feature. In no shared ids mode MBI is set to null on the records
  before scoring (`withhold_shared_ids`), not only dropped from blocking. Tested.
- Weights tuned by hand on the snapshot and derived sides only; the hard cases are tests. The
  commons generator (later PR) is the held-out check.
- **Leak fixes from review:** `household_id` removed from NormalizedRecord (blank on exactly the
  40 copies in the snapshot; households come in PR 6). A test renames every record id to a random
  token and shuffles row order, and expects identical decisions, precision, and recall.
- **Unresolved rows:** the 9 blank enrollment rows are in no cluster, so in no true pair. Any
  auto-match touching one is a false merge and is also counted separately (0 today; tested).
- Hard case Nina Dorsey (example 7): her CRM row carries Carl's pasted MBI, so her CRM and
  enrollment rows disagree on MBI. With shared ids that pair is gray ("unsure"), not found; the
  reviewer decides. Without shared ids it auto-merges. Not tuned around.

## C-00755 and C-00756 (fixed as a rule gap, no weight change)
Matthew Hunt and Shannon Hunt: same surname, same DOB (1949-11-11), same street and ZIP, same
household H-00508; different first names, phones, and MBIs, and only Shannon has an email. A
couple with one birthday. They were gray with "same person" with ids off (score 0.78). GR-003
misses them (no shared phone or email) and GR-004 misses them (different first names, so
different keys). The gap was the suggestion rule: it now never suggests "same person" when the
first names are "far" (not equal, nickname, or Jaro-Winkler close); such pairs say "unsure".
No true pair has a far first name, so recall is unchanged. Tested on all four combinations.

## Risks
- Perfect numbers reflect easy synthetic data: MBIs match across files and every true pair has
  an exact or near DOB. Two different people with the same first name, last name, and DOB and
  no MBI would auto-merge. Phase 2 data must test this.
- Not yet tested on real-world collisions: GR-004 has 0 hits on the fixtures, only the hard cases.
