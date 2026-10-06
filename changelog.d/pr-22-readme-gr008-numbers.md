## PR 22: README two-agency numbers after the identity safety fixes (2026-10-06)

- Remeasures the README two-agency scorecard at commit b15baf0, after PRs 21a to 21c. With shared ids on: automatic recall 0.9471 across all pairs, 0.7875 on the 320 cross-agency client pairs, 507 awaiting review. With shared ids off: 0.0085, 0.0063 and 5,218. Precision stays 1.0000 and no look-alike pair merges.
- Explains the drop: since GR-008, people whose only extra shared detail is a street wait for a person instead of merging.
- Fixes the stale README demo scorecard so every row matches the committed demo-run scorecard.json at b15baf0: 2,000 people, 0 left split, 1,400 households, 2,159 auto-merges, recall 0.9963, 19 awaiting review. It also corrects the old claim that the demo withholds shared ids: the demo matches on the MBI and masks it to the last 4 characters in people.csv.
- Seen world, synthetic data only. These are not results on unseen data.
- Notes that client pairs not merged wait in review as unsure; none is lost (e2e test from PR 21b).
