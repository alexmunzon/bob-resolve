# Source of this derived set

**Derived from the answer key.** `enrollment_clean.csv` is not a file the intake kit wrote. It is
the snapshot's `enrollment_export.csv` with each CRM identity defect undone on the enrollment side,
so the CRM says "Dave" while enrollment says "David", as in real life. Report results on this set
separately from the snapshot and always label them "derived from the answer key".

Never edit this file by hand. A test regenerates it and fails if one byte differs.

## How it was made

```
cd engine && uv run bob-resolve fixtures derive --snapshot ../fixtures/agency-a-snapshot --out ../fixtures/agency-a-derived
```

Code: `engine/src/bob_resolve/truth/derive.py`. For each enrollment row, the policy number resolves
through `policies.csv` to a client. If that client has a `nickname`, `name_typo`,
`dob_transposition`, or `dob_month_day_swap` defect in `ground_truth.json`, the recorded original
(`from`) goes back into that one field (`member_first`, `member_last`, or the mm/dd/yy birth date).
Every other byte is unchanged: same header, same `;` delimiter, same row order, UTF-8, `\n` line
endings. Same rows, same policy numbers, so the pair answer key has the same true pairs.

## Input and output SHA-256

| File | SHA-256 |
|---|---|
| `agency-a-snapshot/enrollment_export.csv` | `de4ae408410b4acbcb5ce32fe399ca4543cff9e00ab75b30c0ac322b4d88c2f7` |
| `agency-a-snapshot/ground_truth.json` | `16c6dcdc7d74afbe230d6e9778eda4436399b445d235dd08d06ea7aa5ae16534` |
| `agency-a-snapshot/policies.csv` | `017e616ccd8cb9c68361a7b0e686fc05d9f62e577e9bcc49408594bb57e8b892` |
| `agency-a-derived/enrollment_clean.csv` | `55e3eff422e1b38023e98f735fe36250a10d20892d741ead6b76cc709d9fd70a` |

## What changed

112 of 1,847 enrollment rows changed, one field each. A client with several policies or a
duplicated row changes on every row.

| Defect | Defects | Reached an enrollment row | Rows changed |
|---|---|---|---|
| nickname | 60 | 41 | 46 |
| name_typo | 40 | 31 | 38 |
| dob_transposition | 20 | 16 | 18 |
| dob_month_day_swap | 10 | 9 | 10 |
| **Total** | **130** | **97** | **112** |

**33 defects have no enrollment row** (19 nickname, 9 name_typo, 4 dob_transposition, 1
dob_month_day_swap). Every one is a client whose only policies are ACA; the enrollment export
carries only MA and PDP rows. Those defects stay CRM-only and cannot be measured on this set.
C-00011 "Dave" (SPEC example 3) is one of them, so example 3 lives in the hard cases (HC-009).
