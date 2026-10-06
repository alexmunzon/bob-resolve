## PR 21c: A shared street never ties records, a different MBI always conflicts (2026-10-06)

- GR-004: a shared street no longer ties two records as one person's own records, and with shared ids on a different MBI always counts as a conflict, even between records tied by phone or email.
- A different MBI tied by phone or email can be a reissued MBI for one real person. That person now waits in review (GR-004) instead of merging automatically.
- Moves test cases g (ambiguity with differing MBIs and a person who moved) and j (two people sharing a phone with different MBIs) from 21b, and restores the full GR-004 check in case a.
