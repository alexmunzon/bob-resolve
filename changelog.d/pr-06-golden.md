## PR 6: Clusters, golden records, and the merge log (2026-10-05)

- Records that auto-match are grouped into one person. Every record pair inside a group is checked again, so a nickname chain like Patrick, Pat, Patricia is split and sent to review instead of becoming one person.
- Each person gets one golden record. Name, birth date, and MBI come from enrollment before the CRM; address, phone, and email come from the record with the newest policy. Nicknames are kept as aliases, and every field names its source file, row, and how it was decided.
- If two enrollment records disagree on birth date or MBI, the field is left empty and the person goes to review as an identity conflict.
- New append-only merge log: one line per merge or split with the pair, tier, score, rule id, run id, and time. Old lines are never rewritten; a correction is a new line.
- Golden people: 2,000 on the snapshot and on the derived side with shared ids; 2,025 on the derived side without shared ids, where 28 true pairs wait for review (measured on synthetic data).
