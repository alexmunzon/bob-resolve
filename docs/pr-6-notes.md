# PR 6 notes: clusters, golden records, merge log

Code in `engine/src/bob_resolve/cluster/`, `golden/`, `mergelog/`; constants under `# PR 6` in
config.py. `golden.data.resolve_side` runs one fixture side end to end. Measured on synthetic data.

## Results (as_of 2026-10-01)

| Enrollment side | Shared ids | Golden people | Auto-merge lines | Pending gray | Cluster splits | IDENTITY_CONFLICT |
|---|---|---|---|---|---|---|
| snapshot | on | 2,000 | 2,167 | 16 | 0 | 0 |
| snapshot | off | 2,000 | 2,167 | 61 | 0 | 0 |
| derived from the answer key | on | 2,000 | 2,167 | 16 | 0 | 0 |
| derived from the answer key | off | 2,025 | 2,139 | 89 | 0 | 0 |

Every combination: no golden person holds records of two answer-key people (no false merge), and
the 9 blank enrollment rows are listed as unidentifiable, not people. Derived without shared ids
leaves 25 people honestly split: their 28 true pairs (transposed and swapped birth dates) are gray,
and gray pairs do not merge until the review queue (PR 7). Derived: 41 people carry a nickname alias.

## Decisions
- **Clusters:** connected components over AUTO_MATCH pairs only. Gray pairs are carried as
  `pending_gray`, never merged here.
- **Split on conflict:** every record pair inside a component is re-checked: first name far,
  different suffix, or DOB far (`CLUSTER_CONFLICT_LEVELS`). Also two different formal names from the
  nickname table (Patrick and Patricia score Jaro-Winkler 0.92, "close") conflict: a typo is not a
  second known name. For each conflicting pair, the weakest auto-match edge (lowest score, then ids)
  on a shortest path between them is cut until they are apart. One CLUSTER_CONFLICT review item per
  component lists its records, the conflicting pairs, and the cut pairs. Each cut edge gets a
  `split` line in the merge log and no `merge` line.
- **Survivorship:** identity fields (first and last name as one unit, suffix, DOB, MBI) are ranked
  by source authority (enrollment 0, CRM 1), then most recent, then record id; the first record with
  a value wins. The suffix is taken from the first record that has one, so enrollment dropping "Jr"
  never drops it from the golden record. Contact fields (address as one unit of line1, city, state,
  zip; phone; email) come from the most recent record with a value.
- **"Most recent" rule:** an enrollment row's own policy effective date; a CRM client's latest
  policy effective date in policies.csv. A record with neither (copied clients, hard cases) sorts
  oldest. Ties fall back to source authority, then record id. Enrollment rows carry no contact
  fields, so in practice contact fields come from the CRM client with the newest policy.
- **IDENTITY_CONFLICT:** if two enrollment records in one cluster disagree on DOB or MBI, that field
  is empty with every authoritative candidate listed, and the person gets a high-severity review
  item. CRM-only disagreements are not authoritative and follow the normal ranking. GR-002 gray
  pairs (example 7) are also carried as high-severity IDENTITY_CONFLICT review items.
- **Aliases:** other first names in the cluster that are nickname-compatible with the golden first
  name. Typo variants (Nlan) are not aliases; they stay visible through provenance and the log.
- **Provenance:** every golden field has a value plus record id, source file, row, rule
  (`authoritative_source` or `most_recent`) and tier (`rules` for an auto-matched record, `single`
  when the person is one record), or no value with rule `no_value` or `identity_conflict`.
- **Unidentifiable:** a record with no name, DOB, or MBI is not a person.
- **Person id:** `person:<smallest record id>`, stable while membership is stable.
- **Merge log:** JSONL, keys sorted, one line per auto-match (`merge`, tier `rules`, score, rule id
  `AUTO-MATCH-HIGH`) or cut edge (`split`, `CLUSTER_CONFLICT`), with run id and time from a caller
  supplied clock. The writer only opens in append mode, refuses a file whose last line is cut off,
  and a `correction` line must name the line number it corrects.
- In no shared ids mode MBI is withheld from matching only; the golden record still carries it.

## Risks
- The scorer rates Patrick and Patricia "close" and would auto-match them on their own (score about
  0.996 with the same surname and DOB). The cluster re-check catches it and sends it to review, but
  PR 5's first-name level should learn the formal-name rule too.
- No splits or identity conflicts fire on the fixtures; both paths are proven only by synthetic
  tests. Phase 2 data must exercise them.
- Recency from future-dated policies (effective after as_of) still counts as most recent.
