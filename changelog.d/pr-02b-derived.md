## PR 2b: Derived clean enrollment side (2026-10-05)

- New `bob-resolve fixtures derive` command and `fixtures/agency-a-derived/enrollment_clean.csv`, derived from the answer key: the enrollment side gets back each client's original name or birth date, so the CRM says "Mike" while enrollment says "Michael". 112 rows changed for 97 of 130 identity defects; the other 33 belong to ACA-only clients with no enrollment row.
- The pair answer key can be built on either enrollment side and gives the same 2,167 same-person pairs on both.
