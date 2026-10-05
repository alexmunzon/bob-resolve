## PR 3: Normalizers for names, birth dates, addresses, phones, and emails (2026-10-05)

- Names are cleaned the same way on every source. Jr, Sr, II, III, and IV move to their own field instead of being dropped, so Robert Hale Sr and Robert Hale Jr stay apart.
- A hand-written table of 213 common nicknames (Bill and William, Dave and David, Peggy and Margaret) tells the matcher when two first names can be the same person.
- Birth dates get checks for two swapped digits and a swapped month and day, plus an edit distance for the "more than one edit apart" safety rule.
- Addresses use standard USPS abbreviations; phones become 10 digits; emails are trimmed and lowercased; ZIP3 is ready for blocking.
