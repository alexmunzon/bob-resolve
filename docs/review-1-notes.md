# Review 1 notes: blocking, normalizers, loaders, answer key

Fixes from the first code review. Constants live under `# Review 1` in config.py. Tests in
`engine/tests/unit/test_review_1.py`. Measured on synthetic data.

## Decisions
1. **Block size cap** (`MAX_BLOCK_SIZE` = 50). A key value shared by more than 50 records is left
   out of that key only; the other keys still pair those records. `dropped_blocks()` lists each
   one with the key, the record count, and the first 12 hex characters of the value's SHA-256
   (never the value). The `block` command prints them. Today no block is over the cap.
2. **Placeholder stop lists.** Phones: any one digit repeated ten times, plus 1234567890 and
   0123456789. Emails: local part none, noemail, no-email, na, n/a, test, unknown, noreply, with
   any domain. These become None in `normalize_phone` and `normalize_email`. DOBs 1900-01-01 and
   1901-01-01 become None at load with `dob_issue` "placeholder", and `dob_key` also returns None
   for them, so they never block. No fixture value hit the stop lists.
3. **New key `first_name_dob`**: every formal name the given name may stand for (the nickname
   set, not only the alphabetically first one) plus the full DOB. "Mary Smith-Jones" and
   "Mary Smith" with the same DOB now meet; so do "Bill" and "William".
4. **Key list frozen** after this review: the comment in `block/candidates.py` and
   `test_blocking_key_list_is_frozen` pin the eight keys, so phase 2 measures this blocker.
5. **Exact duplicate rows.** `AnswerKey.exact_duplicate_rows` counts enrollment rows whose raw line
   hash repeats an earlier row: **27** in the snapshot export and the derived side.
   `AnswerKey.summary()` reports it. The hash stays in lineage only; a test asserts neither
   `raw_sha256` nor `lineage` is a NormalizedRecord field.
6. **Implausible DOB.** An age under 18 or over 120 at `as_of` gets `dob_issue` "implausible".
   The date is kept (it may be a typo, and we do not guess); future dates and placeholders become
   None. "07/04/25" reads as 2025-07-04 and is flagged. No snapshot row is implausible today.
7. **as_of is explicit.** `read_crm`, `read_enrollment`, `load_normalized`, and
   `build_snapshot_answer_key` (keyword `as_of`) all require it. Library code never calls
   `date.today()`. The CLI takes `--as-of`, default `DEFAULT_AS_OF` = 2026-10-01.
8. **Suffixes** add V, 2nd, 3rd (periods are already dropped, so "3rd." works).
9. **`AnswerKey.unresolved_ids`**: the 9 unresolved enrollment rows as a frozenset, for metrics
   to exclude before looking a record up in `person_of`.

## Re-measured blocking (3,887 records, 2,167 true pairs)

| Enrollment side | Shared ids | Candidate pairs (PR 4) | Candidate pairs now | Recall |
|---|---|---|---|---|
| snapshot | on | 3,452 | 3,456 | 1.0000 |
| snapshot | off | 3,452 | 3,456 | 1.0000 |
| derived | on | 3,454 | 3,458 | 1.0000 |
| derived | off | 3,454 | 3,458 | 1.0000 |

`first_name_dob` alone recalls 1.0000 on the snapshot and 0.9871 on the derived side. It adds 4
pairs that no other key finds; none are true pairs in this fixture (it has no surname changes).
Blocks over the cap: 0 on every side.

## Risks
- A one-letter "V" at the end of a first name field ("John V") now reads as a suffix, not a
  middle initial. A wrong suffix only blocks an auto-merge (the safe direction).
- The cap can hide a real pair whose only shared key is a huge block. Dropped blocks are
  reported so a person can look.
- PR 5 code that calls the loaders or the answer key builder must now pass `as_of`.
