## PR 17: Match scores that never round to certain, and a phone menu that fits (2026-10-06)

- A match score just under 1 now shows ">0.999" on the review queue and ">0.9999" in a person's merge log on the Clusters page, instead of rounding up to "1.000" or "1.0000". Only a truly perfect score shows 1.
- The distance from a score to the auto-match or auto-reject line now shows "<0.001" when it is tiny, instead of the self-contradictory "0.000 above the line".
- Every other score and distance on the dashboard is unchanged, e.g. the demo still shows "Score 0.998, 0.008 above the auto-match line (0.99)".
- On a phone, the menu tabs now wrap onto a second line instead of scrolling sideways, so the Benchmark tab is no longer cut off. Tabs are also taller and easier to tap. The desktop sidebar is unchanged.
