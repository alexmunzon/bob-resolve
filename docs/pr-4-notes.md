# PR 4 notes: blocking

Blocking picks which record pairs are worth scoring. Any shared key value puts a pair in the
candidate set. Code in `engine/src/bob_resolve/block/`; `bob-resolve block --enrollment
snapshot|derived [--no-shared-ids]` prints the numbers below. Measured on synthetic data.

## Results (3,887 records, 7,552,441 possible pairs, 2,167 true pairs)

| Enrollment side | Shared ids | Candidate pairs | Blocking recall |
|---|---|---|---|
| snapshot | on | 3,452 | 1.0000 |
| snapshot | off | 3,452 | 1.0000 |
| derived from the answer key | on | 3,454 | 1.0000 |
| derived from the answer key | off | 3,454 | 1.0000 |

Reduction: 99.95% of all pairs are skipped. Recall per key (derived side): mbi 0.9695, email 0,
phone 0.0185, dob_last_initial 0.9871, surname_zip3 0.0125, dob_digits_last_initial 1.0,
surname_birth_month_day 0.9659. On the snapshot dob_last_initial alone is 1.0, because enrollment
repeats the CRM's defected values (PR 2 notes).

## Decisions
- **Keys:** the five SPEC keys (exact MBI, email, phone; DOB plus last-name initial; metaphone
  surname plus ZIP3) and two birth date variant keys.
- **DOB variant keys, measured on the derived side with no shared ids** (SPEC keys alone: 0.9871
  recall, 2,882 pairs): sorted DOB digits plus last initial reaches 1.0 for 484 more pairs;
  surname plus birth year also reaches 1.0 but costs 890 more. Chosen: **sorted DOB digits plus
  last initial** (a digit transposition and a month-day swap keep the same eight digits).
  Also kept: **surname plus birth month and day** (86 more pairs), which catches a wrong birth
  year and is the only key that pairs Robert Hale Sr's CRM row with Jr's enrollment row (hard case
  example 5, where enrollment drops the suffix). Surname plus birth year was dropped.
- **No shared ids mode** (`SHARED_IDS_DEFAULT` in config.py, `--no-shared-ids`): the MBI key is
  removed. Policy number is never a blocking key in either mode (CRM has no policy number).
  Candidate counts are equal in both modes: every MBI pair also shares a DOB key.
- **Pair kinds:** CRM to enrollment, CRM to CRM, and enrollment to enrollment are all kept, so
  recall is measured on all 2,167 answer key pairs and the twins' enrollment rows are compared too.
- Pairs are (a, b) with a < b as strings, the answer key's order. `keys` is a sorted list.
- Null key values never match (polars joins skip nulls), so the 9 blank orphan rows pair with
  nothing.

## Hard cases
- With shared ids, every must-not-merge pair (examples 4 to 7) and every same-person pair is a
  candidate, so PR 5's guard rails get to rule.
- Without shared ids, example 7's pairs are not candidates: the pasted MBI is the only thing the
  two people share, so there is no conflict to surface. Their true pairs are still found. Tested.

## Risks
- The email key finds no snapshot pair: copied clients have a blank email and no two CRM rows
  share one. It matters for hard case 6 and phase 2 shared contacts.
- No block size cap. A shared agency phone or a common surname in one ZIP3 would grow the
  candidate set. The largest block today holds 8 records (sorted DOB digits); phase 2 should
  report block sizes.
- 100% recall here reflects defects the variant keys were chosen against; phase 2 injectors
  (maiden names, moved households) will test the surname keys harder.
