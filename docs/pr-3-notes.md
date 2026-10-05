# PR 3 notes: normalizers

- **Names:** casefold, no accents, apostrophes and periods deleted, other punctuation to spaces.
- **Suffix:** a trailing Jr, Sr, II, III or IV in either field moves to `suffix`, only when another
  token remains (a surname "Iv" stays). If both fields carry different suffixes, the last name's
  wins and the first name keeps its token, so nothing is dropped. The snapshot has none.
- **Nicknames:** `data/nicknames.csv`, 213 hand-written pairs, permissive on purpose (Pat maps to
  Patricia and Patrick), so precision relies on other fields and guard rails. `names_compatible`:
  equal, a shared formal name, or a one-letter initial. `canonical_first_name` is the alphabetically
  first formal name, a blocking hint only. All 60 snapshot nickname defects are covered (tested).
- **Phonetic key: metaphone, not NYSIIS.** On the 40 snapshot surname typos, metaphone keeps typo
  and true name on one key 20 times, NYSIIS 11 ("Nolan" and "Nlan" are both NLN). It feeds the
  phonetic surname plus ZIP3 blocking key, where recall matters.
- **DOB:** YYYYMMDD strings; `dob_edit_distance` is Damerau-Levenshtein (an adjacent swap is one
  edit). All 20 snapshot transpositions are one edit; all 10 month-day swaps are detected.
  **For PR 5:** a month-day swap is usually two or more edits, so the "shared MBI, DOBs more than
  one edit apart" guard rail would block it. PR 5 should decide whether it counts as one edit.
- **Address:** uppercase, a 22-entry USPS Publication 28 table. zip5 is the first five digits of
  a 5 or 9 digit value, never padded. **Phone:** 10 digits after dropping a leading 1, else None.
- **Email:** trim and lowercase; None unless it looks like local@domain.tld. **No gmail dot
  stripping:** gmail-only rule, other providers treat dots as real, and folding addresses only
  adds false shared-email signals. **MBI:** uppercase, non-alphanumerics removed.
- `normalize_record` returns a frozen `NormalizedRecord` (lineage, city, state stay on the raw one).
