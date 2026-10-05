## PR 2: Snapshot, hard cases, loaders, and the pair answer key (2026-10-05)

- Frozen copy of the intake kit's seed-42 fixtures in `fixtures/agency-a-snapshot/`, with the source commit and a SHA-256 per file in SOURCE.md. A test fails if any byte changes.
- Hand-written synthetic hard cases in `fixtures/hard-cases/` for SPEC examples 4 to 7 (twins, Robert Hale Sr and Jr, spouses sharing contact details, a pasted MBI), plus example 3 (Dave and David), with an expected.json answer key.
- Loaders for the CRM clients file and the enrollment export. Every row carries its source file, row number, and a hash of the raw row. Dates load as real dates; two-digit birth years pivot at 1930 and a birth date in the future is rejected, never guessed.
- The pair answer key is built in code: 2,040 CRM rows and 1,838 enrollment rows resolve to 2,000 people (2,167 same-person pairs). The 9 enrollment rows that do not resolve are listed with a reason, never dropped.
