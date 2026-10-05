# Review 2 notes: false-merge holes in the scorer, and metrics on final edges

Code in `engine/src/bob_resolve/score/`, `normalize/names.py`, `normalize/dob.py`, `cluster/`;
constants under `# Review 2` in config.py; tests in `engine/tests/unit/test_review_2.py` and
`tests/e2e/test_snapshot.py::test_review_2_examples_11_to_13_never_merge`. SPEC decision 2: a
false merge is worse than a missed match. Measured on synthetic data, as_of 2026-10-01.

## F1 and F4: formal or short first names one edit apart are not a typo
`names.first_name_typo` replaces the bare "one Damerau-Levenshtein edit" test. One edit is a typo
only when both names have at least 5 letters (`FIRST_NAME_TYPO_MIN_LENGTH`) and they are not
both known formal given names (a formal name in the nickname table, or the curated
`FORMAL_GIVEN_NAMES`: Mario and Maria, Dan and Dana, Mary and Mark, Jon and Jan, Eric and Erica,
Paul and Paula, Denis and Denise, Carl and Carla, and similar). Equal names and nicknames are
unaffected. GR-005 reads it, so such pairs never auto-match and go to gray with "different
people"; a shared MBI does not override a guard rail. The cluster re-check uses the same test
(a "close" first name that is not a typo is a conflict), so a chain cannot sneak them together.
Before this fix, hard case Denis and Denise Okafor (same DOB, address, phone, email, MBI) was
merged; the new end-to-end test failed on main for that reason.

## F2: what a "close" DOB is
`dob_level` now says one_edit only for exactly one changed digit in the month or day (YYYYMMDD
index 4 and up, `DOB_SUBSTITUTION_MIN_INDEX`). Transposition (any two adjacent digits) and the
month-day swap are unchanged. One changed year digit is "far" (Robert Hale 1950 and 1980).
GR-002 reads "far", so a shared MBI with a changed year digit is an IDENTITY_CONFLICT.
**GR-006:** a transposition whose years differ by more than `DOB_TRANSPOSITION_MAX_YEARS` (1)
never auto-matches unless MBI, phone, email, or street also agrees. Gray, suggestion "unsure"
(it may be one person with a typo; a reviewer decides).

## F3 (Alex's decision): name plus DOB as the only evidence, GR-007
One function, `rules.name_dob_only_guard`, is the whole rule. A pair is "name plus DOB only"
when first name is equal, nickname, or a typo; last name equal or close; DOB close; and no
independent evidence agrees (`INDEPENDENT_EVIDENCE_LEVELS`: MBI, phone, email, street exact;
a "close" street does not count, since it can be a neighbor's house number; ZIP is not
evidence). Such a pair gets GR-007 (gray, "unsure"; below the low line still rejected) unless
(a) its name plus DOB is unique in the book and (b) ZIP5 and state do not disagree where both
have a value. State is now on NormalizedRecord and Comparison for (b).

**How "unique" is judged (a decision, please confirm).** Alex's words: no other record "that
the pair's own evidence cannot tie to it". `name_dob_unique_checker` looks at every other record
with the same last name and DOB and a first name sharing a formal name with either side, judged
over the whole book and never the answer key. Such a holder is tied when it agrees with the pair
record on an independent field, or when it disagrees with neither pair record on anything (MBI,
phone, email, street, ZIP5, state, suffix): it is the same name and DOB with nothing pointing
elsewhere. One untied holder makes the key not unique. A stricter reading (every other holder
must share an MBI, phone, email, or street) was measured first and **dropped recall after review
in no shared ids mode to 0.6567 (snapshot) and 0.6613 (derived)**, and to 0.9875 with shared ids,
with 0 false merges caught: a person with two enrollment rows (two policies) and blank MBIs has
three records with the same name and DOB and nothing else to tie them. That reading would fail
SPEC decision 2, so it is not used; switching is a one-line change in `_tied`.

### F3 counts (candidate pairs with name plus DOB as the only agreeing evidence)
| Enrollment side | Shared ids | Pairs | True pairs | Auto-matched | Distinct keys | Keys held by exactly the 2 records | Unique (adopted rule) | Location conflict |
|---|---|---|---|---|---|---|---|---|
| snapshot | on | 59 | 59 | 59 | 40 | 32 | 59 | 0 |
| snapshot | off | 2,127 | 2,127 | 2,127 | 1,619 | 1,349 | 2,127 | 0 |
| derived from the answer key | on | 59 | 59 | 59 | 40 | 32 | 59 | 0 |
| derived from the answer key | off | 2,127 | 2,127 | 2,099 | 1,631 | 1,359 | 2,127 | 0 |

With shared ids the 59 are rows with a blank MBI. Without shared ids almost every CRM to
enrollment pair is name plus DOB only, because enrollment rows carry no contact fields. GR-007
hits are 0 on all four combinations: the fixtures have no two people sharing a name and DOB.

## F8: metrics on final edges
`evaluate_scores(..., kept=...)` measures precision and recall after review on the merge edges
that survive the cluster split. An auto-match the split cuts is not a merge, and it is not found
(its CLUSTER_CONFLICT queue item suggests "different people"). `run` passes the merge lines of
the log; `bob-resolve score` runs the split itself and prints the cut count. Without `kept` the
old score-stage numbers come back. Cut edges on the fixtures: 0 on all four combinations.

## Results (4-way score table; before in brackets)
| Enrollment side | Shared ids | Auto-merge | Gray | Reject | Precision | Recall after review | GR-005 | GR-006 | GR-007 |
|---|---|---|---|---|---|---|---|---|---|
| snapshot | on | 2,167 | 11 (16) | 1,278 (1,273) | 1.0000 | 1.0000 | 1,278 (1,277) | 0 | 0 |
| snapshot | off | 2,167 | 30 (61) | 1,259 (1,228) | 1.0000 | 1.0000 | 1,278 (1,277) | 0 | 0 |
| derived from the answer key | on | 2,167 | 11 (16) | 1,280 (1,275) | 1.0000 | 1.0000 | 1,280 (1,279) | 0 | 0 |
| derived from the answer key | off | 2,139 | 58 (89) | 1,261 (1,230) | 1.0000 | 1.0000 | 1,280 (1,279) | 0 | 0 |

The gray pairs that moved to reject (5 with ids, 31 without) are non-true pairs whose birth
years differ by one digit: they were "one edit" (+2) and are now "far" (-5). Golden people are
unchanged: 2,000 / 2,000 / 2,000 / 2,025, 0 cluster splits, 0 people holding two true people.

## New hard cases (fixtures/hard-cases, 28 rows, both shared-ids modes)
- Example 11: Denise and Denis Okafor (HC-006, HC-014; shared MBI) and Carl and Carla Wexley
  (HC-007, HC-015): gray, GR-005, "different people".
- Example 12: Robert Hale born 1948 (HC-016) against Sr 1941 and Jr 1968: DOB far, not merged,
  never "same person". Ellen Quarry 1952 and 1925 (HC-001, HC-017): GR-006, "unsure".
- Example 13: two James Smiths, same DOB, ZIPs 43001 and 44101 (HC-018, HC-019): GR-007, "unsure".
- Dave and David still auto-merge in both modes (name plus DOB only without shared ids, unique).
Hard-case tests now skip blank MBIs and phones in the "obviously synthetic" check: two new rows
need a blank MBI so the pair is not decided by a different MBI.

## Risks
- The adopted uniqueness reading lets two different people with the same name and DOB and no
  other data at all auto-merge (nothing points elsewhere). The strict reading closes that but
  costs about a third of recall without shared ids on these fixtures. Alex should pick.
- A real typo that turns one formal name into another (Mark typed as Mary) or a short-name typo
  (Jon and John) now goes to review as "different people", which a reviewer may trust too much.
- One changed year digit is now "far"; a real one-key slip in the year needs review.
- CLAUDE.md and SPEC list guard rails GR-001 to GR-005; GR-006 and GR-007 should be added there.
