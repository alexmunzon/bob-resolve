# GR-005 notes: first names incompatible

Code in `engine/src/bob_resolve/score/` (`compare.py` adds `first_typo`, `rules.py` adds the
rail); constant under `# GR-005` in config.py. Measured on synthetic data, as_of 2026-10-01.

## Problem
`names_compatible("Patrick", "Patricia")` is False, but their Jaro-Winkler is 0.92, so the PR 5
first-name level was "close" (+1.5). With the same surname, DOB, and address and no MBI to tell
them apart, opposite-sex twins scored about 0.996 and auto-merged. The PR 6 cluster re-check
caught it after the fact; a false merge is the worse error (SPEC decision 2), so the scorer must
refuse it up front.

## Rule (orchestrator decision)
A pair never auto-matches unless one of these holds for the two normalized first names:
- `names_compatible` is True (equal, a shared formal name in the nickname table, or an initial);
- they are within `FIRST_NAME_TYPO_MAX_EDITS` (1) Damerau-Levenshtein edits, a typo
  (a deleted, inserted, or changed letter, or two adjacent letters swapped);
- either first name is missing.
Otherwise the rule id GR-005 is recorded. Like GR-001 and GR-003 it only stops an auto-match:
a pair above the low line goes to gray with "different people" (everything else matched: same
household, likely twins or spouses); a pair below the low line is still rejected.

## Decisions
- The typo test lives in `compare` as `first_typo` (a boolean beside the first-name level), so
  the rail reads only the comparison, like the other rails. No weight changed; the hard case
  was not used to tune anything.
- It fires on "far" first names too, not only "close": the rule is about compatibility, not
  the Jaro-Winkler band. Far names already could not reach "same person" (PR 5 rule), so this
  only changes their gray suggestion from "unsure" to "different people".
- Dave and David (nickname), and one-letter typos such as Patrik, Patirck, Patricks, still
  auto-match (tested in both shared-ids modes).
- The PR 6 cluster check on two different formal names stays as a second line of defense.

## Results
| Enrollment side | Shared ids | Auto-merge | Gray | Reject | Precision | Recall after review | GR-005 hits |
|---|---|---|---|---|---|---|---|
| snapshot | on | 2,167 | 16 | 1,273 | 1.0000 | 1.0000 | 1,277 |
| snapshot | off | 2,167 | 61 | 1,228 | 1.0000 | 1.0000 | 1,277 |
| derived from the answer key | on | 2,167 | 16 | 1,275 | 1.0000 | 1.0000 | 1,279 |
| derived from the answer key | off | 2,139 | 89 | 1,230 | 1.0000 | 1.0000 | 1,279 |

No auto-merge, gray, reject, precision, or recall number moved. Of the GR-005 hits, 2 per
combination are "close" names (both already rejected) and the rest are "far"; 14 (ids on) or 53
(ids off) land in gray, of which 13 or 52 changed suggestion from "unsure" to "different people".
No GR-005 hit is a true pair. The PR 6 golden table is unchanged: 2,000 / 2,000 / 2,000 / 2,025
people, 0 splits, 0 IDENTITY_CONFLICT.

## Risks
- A real person whose first name is recorded two typos apart (Kathrine and Catherine without a
  nickname row) can no longer auto-match; it goes to gray with "different people", which a
  reviewer may trust too readily. The snapshot has none; phase 2 data must test it.
- A first name that changed (a legal name change, or a middle name used as first) is now
  "different people" in review. The nickname table is the place to add known pairs.
- Short names one edit apart (Jon and Jan, Mary and Mara) still pass as a typo; precision there
  relies on the other fields.
