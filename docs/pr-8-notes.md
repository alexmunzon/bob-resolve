# PR 8 notes: dashboard shell and Overview

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-8-dashboard`, local only. The page renders the committed demo run, measured on synthetic data.

## Decisions
1. **Design copied from plan-diff at c13d5c3** (which copied agency-intake-kit at a54faee): tokens
   in globals.css (slate neutrals, one indigo accent, class-based dark mode, system font, no web
   font download), the inline theme script plus toggle (no next-themes), the 240px nav, nav link
   with "coming soon" items, tile and severity badge components, a 3-line `cn`, and the parseFloat
   lint ban. Each copied file says so in its first comment.
2. **One library added:** `lucide-react` 1.52.0 (ISC), the same icon set and version as plan-diff.
3. **Loader.** `lib/run-loader.ts` parses text (manifest, scorecard, people.csv, review queue,
   merge log), so a future in-browser loader shares the checks; `lib/run-dir.ts` reads the demo
   folder at build time. It refuses: any MBI in people.csv or the queue that is not 7 stars plus 4
   characters, a full `mbi` field in a queue record, a scorecard not labeled "measured on synthetic
   data", an unknown severity, a negative or missing cost, and a people or queue count that
   disagrees with the scorecard. Errors name the file and line or row.
4. **Records in by source** is counted from people.csv record ids (CRM 2,040, enrollment 1,838).
   The 9 unidentifiable rows are not in any run file with their source, so the tile says "plus 9
   unidentifiable" instead of guessing. The test checks the sum equals `records_in` (3,887).
5. **Merges by tier** come from the merge log (rules 2,139, which equals `merges.auto`). Jev and
   LLM show "Off" with the reason; human review shows 0 and "No review decisions applied".
6. **Costs are JSON numbers** in this engine (plan-diff used decimal text). `lib/format.ts`
   formats them with two decimals and refuses negatives; the parseFloat ban stays.
7. **Run time** is `timings_ms: null` in the demo (fixed clock so reruns are byte-identical), so it
   shows "Not recorded" with that reason. A run with timings shows their sum in seconds.
8. **Metrics** are shown as percents with the target, a "Meets target" or "Below target" badge
   (icon plus word), the enrollment side label, and "shared ids off (MBI withheld)", each ending
   "Measured on synthetic data." Precision is the rules arm before any review, as the scorecard says.
9. Numbers use a fixed en-US formatter so server and browser print the same text.
10. Old placeholder page test replaced by loader, Overview, and nav tests.

## Checked by hand
On a local production build: at 1440 by 900 the content ends at 694px (no scroll, no sideways
scroll); at 375 there is no sideways scroll and the nav scrolls inside its own bar.

## Risks and follow-ups
- The page loads people.csv (1.8 MB) at build time only to count sources; fine now, and it never
  ships to the browser. A scorecard field for records by source would be cleaner (engine change).
- The "Below target" and "High" severity paths have no demo data; covered by mapping code only.
- "Coming soon" nav items are plain text, so keyboard users skip them until their PRs land.
