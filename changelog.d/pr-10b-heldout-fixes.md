## PR 10b: Fixes for the held-out benchmark patterns (2026-10-05)

- Name plus birth date alone never auto-merges now (GR-007, Alex's decision). A pair needs one more agreeing fact: MBI, phone, email, street, or a linking policy.
- Look-alike first names that differ only at the end (Andrew and Andrea, Louis and Louise) are no longer treated as a typo (GR-005).
- A person who moved is no longer "ambiguous" with their own old records (GR-004).
- On the seen two-agency world: 0 look-alike false merges in both modes, and recall on commons' 320 client pairs is 0.99 with shared ids and 0.93 without.
- Without shared ids, recall after review drops to about 0.02 to 0.07, because enrollment rows carry only name and birth date. This is recorded as a known miss.
- The demo run now uses shared ids on.
- No fresh held-out world: agency-data-commons needs an agency B seed option first.
