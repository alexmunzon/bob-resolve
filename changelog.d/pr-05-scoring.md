## PR 5: Scoring, cutoffs, and guard rails (2026-10-05)

- New `bob-resolve score --enrollment snapshot|derived [--no-shared-ids]` command: compares every candidate pair field by field, gives a score from 0 to 1, and decides auto-match, review (gray), or auto-reject. It prints auto-merge precision, counts, and recall after review.
- Cutoffs live in config.py: auto-match at 0.99 or above, auto-reject below 0.10.
- Three safety rules override the score and are recorded on the pair: Jr and Sr never auto-match (GR-001); a shared MBI with very different birth dates goes to review as an identity conflict (GR-002); a shared phone or email alone never auto-matches (GR-003).
- On every enrollment side, with or without shared ids: auto-merge precision 1.0 and recall after review 1.0 (measured on synthetic data).
- Leak fixes: household id is no longer visible to matching, MBI is blanked on the records in no shared ids mode, and a test proves decisions do not depend on record ids or row order.
