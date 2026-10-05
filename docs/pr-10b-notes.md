# PR 10b notes: fixing the three patterns the held-out world found

Branch `pr-10b-heldout-fixes`. Code: `score/rules.py` (GR-004, GR-007), `normalize/names.py`
(GR-005), `golden/data.py` (linking policies), `score/compare.py`, constants under `# PR 10b`
in config.py. Tests: `tests/unit/test_pr_10b.py` plus updated e2e tests. Measured on synthetic
data, as of 2026-10-01.

## Decisions

1. **GR-007 (Alex, 2026-10-05).** Name plus DOB as the only agreeing evidence never auto-merges.
   One more agreeing fact is needed: MBI (shared ids on), phone, email, street, or a linking
   policy. Otherwise gray, "unsure". The review 2 "unique in the book" check and the ZIP and
   state check are deleted.
2. **Linking policy.** Each CRM client gets its policy ids and carrier member ids from the
   agency's `policies.csv`; each enrollment row gets its policy number and that policy's carrier
   member id. Policy ids carry the agency prefix. It is never a score weight, only evidence.
   **It is withheld in "no shared ids" mode**, like MBI: SPEC section 5 says that mode withholds
   MBI *and policy number*, and the policy number is the very join that builds the answer key,
   so counting it there would make the headline number meaningless. What-if, measured and not
   adopted: counting it without shared ids gives recall after review 0.8791 (snapshot and
   derived) and 0.7102 (multi-a-b), precision 1.0. It is still below 0.90 either way. To switch,
   change one line in `compare.py` and one in `withhold_shared_ids`.
3. **GR-005.** One edit is not a typo when the last letters differ and either name ends in a,
   e, i, o, u, or y (Andrew and Andrea, Christian and Christina, Louis and Louise). The curated
   list in config grew by about 40 names one edit apart away from the end (Francis and Frances,
   Jesse and Jessie, Jason and Mason, Larry and Harry). I wrote these by hand; I did not read
   Faker's or commons' name sources. A shared MBI does not override GR-005 (tested).
4. **GR-004.** Holders of one name plus DOB key are grouped by ties (exact MBI with shared ids
   on, phone, email, or street, followed through chains). A conflict between two records in one
   group is one person's own history and is not counted. Two Owen Marlowes tied by nothing still
   conflict (example 9 unchanged), and a copy of one of them is still stopped.
5. **Demo switched to shared ids on.** With Alex's GR-007 and no shared ids, the derived demo
   becomes 3,838 people and 2,157 queue items, almost all "unsure", and the review page takes
   about 10 seconds per render in tests. The demo is now `--shared-ids` (2,000 people, 19 items).
   Dashboard tests were updated to the new demo numbers; no check was removed. Going back to a
   no shared ids demo needs a paged review page first.
6. **Tests changed because the rule changed, not to make them pass.** Tests that asserted the
   old "unique" exception (Dave and David auto-merging without shared ids, Nina without shared
   ids) now assert the new behavior (gray, GR-007, "unsure"). Recall after review without shared
   ids is a **strict xfail** with the measured numbers (snapshot, derived, multi-a-b). The two PR
   10 strict xfails now pass in both modes, so those markers are removed.

## Results (precision / auto-merges / gray / recall after review)

| Set | Shared ids | Before (PR 10) | After (PR 10b) |
|---|---|---|---|
| snapshot | on | 1.0000 / 2,167 / 11 / 1.0000 | 1.0000 / 2,159 / 19 / 0.9963 |
| snapshot | off | 1.0000 / 2,167 / 30 / 1.0000 | 1.0000 / 40 / 2,157 / 0.0185 |
| derived | on | 1.0000 / 2,167 / 11 / 1.0000 | 1.0000 / 2,159 / 19 / 0.9963 |
| derived | off | 1.0000 / 2,139 / 58 / 1.0000 | 1.0000 / 40 / 2,157 / 0.0185 |
| multi-a-b (seen) | on | 0.9994 / 4,645 / 565 / 0.9573 | 1.0000 / 4,766 / 445 / 0.9827 |
| multi-a-b (seen) | off | 0.9970 / 4,595 / 660 / 0.9322 | 1.0000 / 298 / 4,962 / 0.0676 |

Multi-a-b, now labeled **seen** (a regression set, no longer held out):

| Shared ids | Commons 320 pairs recall | Must-not-merge merged (by type) | moved_household found |
|---|---|---|---|
| on | 0.9938 (PR 10: 0.8938) | 0 of 164 (PR 10: twins 4) | 30 of 32 (PR 10: 7) |
| off | 0.9250 (PR 10: 0.8812) | 0 of 164 (PR 10: twins 12, name_dob 4) | 8 of 32 (PR 10: 2) |

0 merges in every must-not-merge type (twin_lookalike, name_dob_lookalike, father_son_same_name,
child_on_parent_policy, shared_household_contact) in both modes. Blocking recall 1.0 everywhere.
0 people holding two true people in every set.

The 8 GR-007 pairs with shared ids on the snapshot: blank MBI, nothing else agreeing.

## Fresh held-out world: not generated
`synth generate-multi` has no agency B seed option: B's seed is always `--seed + 1`, and
`--seed` other than 42 fails ("planted records need P-00417 as an MA policy (use seed 42)"),
also with `--no-agency-a`. So the pinned CLI can only make the world we have now seen.
**agency-data-commons needs a `--b-seed` option** (its `build_agency_b` already takes a B seed;
the CLI just does not expose it). Commons was not edited. Until then there is no unseen
two-agency number after this PR.

## Risks
- Without shared ids the matcher now merges almost nothing across CRM and enrollment: the
  enrollment export has no contact fields, so every such pair is name plus DOB only. This is
  the direct cost of decision 1 and is why recall is 0.02 to 0.07 there. Alex should know the
  README's "no shared ids" headline number now reads as a failed target.
- The GR-005 ending rule also blocks real end-of-name typos (Michell for Michelle). They go to
  review as "different people", which a reviewer may trust too readily.
- No fresh held-out measurement exists for these fixes; every number above is on data the
  fixes were designed against (snapshot) or have now seen (multi-a-b).
- The demo now shows the easier shared-ids mode.
