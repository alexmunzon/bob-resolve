## PR 04b: Review 1, blocking, normalizer, loader, and answer key fixes (2026-10-05)

- Blocking skips any key value shared by more than 50 records and reports it with a masked value.
- Placeholder phones (like 5555555555), emails (like none@ or test@), and birth dates (1900-01-01) are treated as blank.
- New blocking key: first name (with nicknames) plus full birth date, so a changed or hyphenated surname still meets. The key list is now frozen by a test.
- The answer key counts exact duplicate enrollment rows (27) and lists the 9 unresolved rows as a set.
- Birth dates that make someone under 18 or over 120 are flagged "implausible". The "as of" date is always passed in; the command line takes `--as-of` (default 2026-10-01).
- Suffixes V, 2nd, and 3rd are recognized.
