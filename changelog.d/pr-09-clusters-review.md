## PR 09: Clusters and Review queue pages (2026-10-05)

- New Clusters pages answer "Why did these records become one person?": the golden record with the source file, row, and deciding tier of every field, aliases, the member records side by side, the merge log lines, and the household as a small graph with a text list.
- New Review queue page answers "What needs a human, most important first?": items in the engine's order with per-field evidence (agree, disagree, missing), the suggestion, every rule explained in plain words, filters by suggestion and rule, and how to record decisions with `bob-resolve review apply`. The page never edits data.
- The run folder gains `members.jsonl` (the records behind each person, MBI masked), and the scorecard names the source file and row of each unidentifiable record.
- The nav lists only built pages, so every item is reachable by keyboard.
