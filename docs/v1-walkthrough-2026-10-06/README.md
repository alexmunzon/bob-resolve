# Bob Resolve v1 exit walkthrough (2026-10-06)

Recorded live on the public link https://bob-resolve-nine.vercel.app at main `56677c1`
(Vercel production `dpl_2ABXr3UwxFRPK3Y7k8rTwQCfD16e`, READY). In-app browser, no login. All data is synthetic.

| Step | Page | What it shows | Screenshot |
|---|---|---|---|
| 1. Strong match | `/clusters/crm-C-00083` | "Bob Murphy" (CRM) and "Robert Murphy" (enrollment): same birth date 1940-10-11, same MBI last 4 (ET97). Merged automatically, score 0.9999, rule AUTO-MATCH-HIGH. "Bob" kept as an alias. Every golden field names its source file and row and why it was chosen. | `1-strong-match-robert-murphy.jpg` |
| 2. Weak name plus birth date (GR-007) | `/review?rule=GR-007` | Kevin Khan, enrollment rows 209 and 210: name and birth date agree, everything else missing. Score 0.998 is above the auto-match line (0.99), yet the engine did not merge: suggestion "Unsure", a person decides. 8 such items. | `2-weak-gr007-kevin-khan.jpg` |
| 3. Conflicting pair (GR-005) | `/review?rule=GR-005` | Gabrielle Smith and Carlos Smith: same last name and birth date, but first name, street, state, ZIP and phone disagree. Suggestion "Different people"; not merged. 9 such items. | `3-conflict-gr005-smith.jpg` |
| 4. Honest benchmark | `/benchmark` | Automatic precision 100.0%, recall 99.6%, F1 99.8% (engine alone). Confirmed by a reviewer 0, awaiting review 19. Suggestion figure labeled "Hypothetical, not achieved". Says the data is not held out. | `4-benchmark.jpg`, `5-benchmark-375px.jpg` |

Checks: no console errors on any page; at 375px phone width no page scrolls sideways.

Limits, stated honestly:
- The 100.0% precision is exact on this data (2,159 of 2,159 auto-merges correct), not rounded. It is measured on
  data used while building the rules, so it is not accuracy on unseen data.
- No review decision has been applied to the demo run (0 confirmed). Applying decisions is a command-line step
  shown on `/review`; it writes a new run and never edits the old one.
- Cosmetic: at 375px the "Benchmark" tab in the top menu is partly cut off until the menu is swiped. Fixed later the same day in PR 17 (GitHub #12, merge `3f208b5`): the phone menu now wraps.
