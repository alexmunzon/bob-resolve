# PR 9 notes: Clusters and Review queue pages

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-9-pages`, local only. Both pages render the committed demo run, measured on synthetic data.

## Engine
1. **Unidentifiable records are named.** The scorecard gains `unidentifiable_records`: record id,
   source file, and row of each one (9 in the demo, all enrollment rows). The Overview now counts
   them by source (CRM 2,040, Enrollment 1,847, including 9 unidentifiable). Fixes the PR 8 risk.
2. **New run file `members.jsonl`.** One line per record of every person made of two or more
   records, in the same minimized shape as the review queue (names, DOB, address, phone, email,
   MBI masked to the last 4 always, source file and row, active policy flag; no notes, no policy
   numbers). Without it the Clusters page could only show the winning value of each field, not the
   member records side by side. Cost: the demo grows by 1.4 MB (3,432 lines). The loader refuses
   an `mbi` field or an unmasked `mbi_masked` in it, as in the queue.
3. The demo was regenerated twice, byte-identical; the e2e byte-compare test passes.

## Dashboard
4. **Which cluster pages are built:** every person made of two or more records (1,579 in the demo),
   because only they have a merge to explain. Hard-case people fall under the same rule when a demo
   run holds them (the derived demo does not). `dynamicParams = false`, so any other address is a 404.
   The full build takes about 10 seconds. Address: `/clusters/crm-C-00023` for `person:crm:C-00023`.
5. **Cluster page:** golden record (value, source record, file, row, why it won, deciding tier),
   aliases, member records side by side, every merge log line touching the person's records (line
   number, pair, tier, score, rule ids in words), and the household.
6. **Household graph:** plain SVG, no chart library (a 1 to 3 person star needs none). This person on
   the left, the others on the right, one line each. The run has no relationship field (Jev's
   household role comes later), so every line says "same household". The SVG has a title and a
   description, and a text list below says the same thing, with links to other members' pages.
7. **Clusters index:** duplicate CRM clients (40, example 2 among them), nicknames kept as aliases
   (41), and every person with two or more records in a closed details list. Plain links there, not
   next/link, so 1,600 links add no client props or prefetches.
8. **Review page:** the queue in the engine's stored order (severity, then distance from the nearer
   cutoff). Each item: position, severity, suggestion, score and how far from which line, every rule
   id in words, records side by side, and per-field evidence as Agree, Disagree, or Missing (icon plus
   word plus a short note such as "Month and day swapped" or "Not compared: MBI withheld in this run").
   Close variants (typo, swapped digits) count as Disagree with the note saying how close.
9. **Rule words** live in `lib/explain.ts`: GR-001 to GR-007, CLUSTER_CONFLICT, IDENTITY_CONFLICT,
   SCORE-GRAY, AUTO-MATCH-HIGH, REVIEW-DECISION.
10. **No editing (SPEC section 4).** A "How to decide" panel shows one decisions line and the
   `bob-resolve review apply` command; each item has its own ready line in a closed details block.
   Nothing on the page writes, saves, or calls anything. Filters (suggestion, rule id) run in the
   browser with React state.
11. **Nav:** Clusters and Review queue are links. Benchmark and Changes are removed from the list (they
   were text that keyboard users could not reach) and a short line under the nav says they come later.
12. **No new libraries.**

## Tests
Example 2 (C-00023 and C-02011 one person, the merge log line with tier, score, and rule), golden
field sources, the household graph and its text list, the GR-005 item says "first names do not
match", evidence words, the stable order, both filters and their combination, the how-to panel, and
no MBI-shaped value in any rendered text node on the list, the review page, and every cluster page
with 4 records, plus the data of all 1,579 cluster pages. Text nodes, not joined page text: adjacent
cells join into false hits ("ZIP" + "81273" + "CRM" is 11 characters).

## Risks
- The clusters index HTML is about 580 KB and the review page about 870 KB before compression
  (1,579 links; 58 items with tables). Fine for a demo; a search box or paging would cut it.
- The build makes 1,584 pages. A much larger book would need a smaller page rule or on-demand pages.
- The household graph is only tested on households of 1 to 3 people (the demo's largest).
- The demo queue has only SCORE-GRAY, GR-005, and GR-003 items, all medium. High severity, cluster
  conflicts, and identity conflicts render through the same code but have no demo data.
