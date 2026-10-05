# PR 2b notes: derived clean enrollment side

Why: PR 2 found the snapshot's enrollment export repeats the CRM's defected identity values, so
cross-file matching was too easy. Alex decided to rebuild a clean enrollment side from the answer
key. Results on it are labeled "derived from the answer key".

## What the code does
- `bob-resolve fixtures derive --snapshot <dir> --out <dir>` writes `enrollment_clean.csv`.
  Code in `engine/src/bob_resolve/truth/derive.py`.
- Each enrollment row's policy number resolves through `policies.csv` to a client (only policy
  ids with exactly one owner count, same rule as the answer key). If that client has a nickname,
  name_typo, dob_transposition, or dob_month_day_swap defect, the defect's `from` value goes back
  into `member_first`, `member_last`, or `Birth Dt (mm/dd/yy)` (ISO turned into mm/dd/yy).
- The rewrite works on the raw text lines, not through a CSV writer, so every other byte (header,
  `;`, row order, trailing newline) is untouched. The file has no quoted fields, so splitting on
  `;` is exact.
- Safety check: before replacing, the code checks the row holds the defect's `to` value and stops
  with an error if not. It also stops if a client ever carries two identity defects (none do).

## Results
- 112 of 1,847 rows changed, one field each: nickname 46, name_typo 38, dob_transposition 18,
  dob_month_day_swap 10. Rows exceed defects because a client with several MA/PDP policies or a
  duplicated row changes on every row.
- 97 of 130 defects reached a row. **33 have none**, all clients whose only policies are ACA
  (the export carries only MA and PDP). They cannot be measured on this set.
- Example: C-00079 is "Mike" in the CRM and "Michael" on enrollment row 73.
- The answer key built on the derived side has the same 2,167 true pairs and the same 9
  unresolved rows: only values change, never identities.

## Decisions
- `build_snapshot_answer_key(snapshot_dir, enrollment_csv=None)` takes the enrollment file as a
  parameter. The loader `read_enrollment(path)` already takes any path; lineage `source_file`
  becomes `agency-a-derived/enrollment_clean.csv`, so records say which set they came from.
- The derived folder holds only the enrollment file. CRM, policies, and ground truth are read from
  the snapshot; no copies.
- `near_duplicate_client` and `name_dob_collision` are not undone: they are extra CRM rows, not
  enrollment values.

## Risks
- Still easier than real life on other fields: MBI and policy numbers match exactly across files.
- A future snapshot with quoted enrollment fields would need a real CSV parser here; the
  byte-identical test would catch a change.
