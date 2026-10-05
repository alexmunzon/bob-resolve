# PR 2 notes: snapshot, hard cases, loaders, answer key

Decisions and findings for the orchestrator and Alex to review.

## Facts about the snapshot that differ from SPEC section 5
- **CRM has 2,040 rows, not 2,030.** The extra 10 (C-02001 to C-02010) are the scored
  `name_dob_collision` defect: exact copies of a client (same name, DOB, phone, address, MBI) with
  `copy_of` in ground_truth.json. They are the same person as their original, so the answer key
  follows `copy_of` for both `near_duplicate_client` (30) and `name_dob_collision` (10). Result:
  2,040 CRM rows, 2,000 people. SPEC section 5 should say 2,040 (2,000 people plus 40 copies).
- **The enrollment export mirrors the CRM's defected identity values.** The intake kit writes it
  after the identity injectors, so every nickname, name typo, and DOB defect that has an
  enrollment row shows the same defected value on both sides (41 of 60 nicknames, 31 of 40 typos,
  all 25 DOB defects with rows). There is no "Dave in CRM, David in enrollment" signal in the
  snapshot. A test pins this (C-00063 "Jhnston" on both sides).
- **SPEC example 3 cannot hold on the snapshot.** C-00011 "Dave" has one policy, P-00015, which
  is ACA; the enrollment export only carries MA and PDP rows, so Dave has no enrollment row at all.
  A test pins this. Example 3 is added to the hard cases instead (HC-009 Dave Lindqvist in CRM,
  enrollment row 9 David Lindqvist, same DOB and MBI). The SPEC example should be reworded, or the
  phase 2 generator should write enrollment names before the nickname injector.

## Answer key
- Join column: the enrollment `policy_number` matches `policies.csv` column `policy_id`
  (1,820 of 1,820 distinct values). No other policies column matches any value.
- policies.csv has 34 exact duplicate rows (2,634 rows, 2,600 policy ids); every duplicated
  policy id has one client_id, so none is ambiguous. The code still reports `policy_ambiguous` if
  one ever does.
- Enrollment has 1,847 rows (1,820 distinct policy numbers; the extras are duplicate rows). Each
  duplicate row is its own record and joins the same person.
- **Unresolved: 9 enrollment rows**, all reason `client_not_in_crm`: rows 250, 278, 332, 559, 915,
  1359, 1464, 1628, 1847 (P-00373, P-00420, P-00504, P-00818, P-01324, P-01913, P-02077, P-02299,
  P-02600). Cause: the scored `orphan_policy` defect rewrote each policy's client_id to an id that
  does not exist (C-9xxxx), and the enrollment writer then left the name, DOB, and MBI blank. The
  rows carry no identity, so they stay out of every cluster and are listed in `unresolved`. The
  other 4 orphan policies are ACA or Medigap and have no enrollment row.
- Person id is the original client_id. Clusters: 2,000 (399 of size 1, 1,336 of 2, 253 of 3,
  12 of 4). True pairs: 2,167, every within-cluster pair, stored as (smaller id, larger id).
- Record ids: `crm:<client_id>` and `enrollment:<row number>`. Enrollment uses the row number
  because policy numbers repeat on duplicate rows.

## Loaders
- Row numbers are 1-based data rows, header not counted, so C-00011 is row 11. The intake kit's
  `row_ref` in ground_truth.json counts the header (C-00011 is 12). Do not mix the two.
- The raw row hash is SHA-256 of the row's text line (UTF-8, no line ending). The reader refuses a
  file whose line count differs from the parsed row count (a quoted newline would break lineage).
- CRM `notes` is dropped at load: free text never travels into records or model payloads.
- All columns load as text (zips keep leading zeros); dates become polars Date.
- **Two-digit year rule:** with the 1930 pivot from config, 30 to 99 read as 1930 to 1999 and 00
  to 29 as 2000 to 2029 (same as the intake kit). A resulting DOB after the as-of date (default
  today) is rejected: `dob` is null and `dob_issue` is `future`. It is never shifted back 100
  years, because guessing identity fields is against SPEC decision 4. "01/02/29" is rejected;
  "01/02/05" is 2005-01-02. Blank DOBs are `missing`; malformed or impossible dates are `invalid`.
  The CRM reader applies the same future rule to ISO dates. The snapshot has no future or invalid
  DOBs; only the 9 orphan rows are `missing`.

## Hard cases
- 9 CRM rows and 9 enrollment rows (18 total). MBIs start with `9A` and pass the MBI format;
  phones are (555) 555-01xx; emails are example.com; places are invented ("Testville").
- Suffix lives in `last_name` ("Hale Sr", "Hale Jr") because the CRM has no suffix column; the
  enrollment row for Jr drops the suffix on purpose. PR 3's normalizer splits it out.
- expected.json lists people, must-not-merge pairs (examples 4 to 7, with reasons) and
  same-person pairs (examples 3, 5, 7). The loader checks every same-person label lands in one
  person and the test checks every must-not-merge pair lands in two.

## Risks
- Because enrollment mirrors CRM identity, the snapshot is easy: most cross-source pairs agree
  exactly. Precision and recall on it will look better than on real data. Phase 2 should fix this.
- `read_crm` and `read_enrollment` default the future-DOB check to today's date; pass `as_of`
  for reproducible runs.
