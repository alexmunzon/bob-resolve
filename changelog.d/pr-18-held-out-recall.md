## PR 18: Honest recall names on the two-agency held-out report (2026-10-06)

- The held-out report for the two-agency world no longer has a figure called plain "recall". That figure counted pairs the engine only suggested as the same person, with nobody confirming them, as found.
- Each commons pair block now shows `found_automatically` and `automatic_recall`: pairs the engine merged on its own. A merge a reviewer made does not count, matching the main scorecard.
- The old figure is kept as `recall_if_suggestions_confirmed`, a hypothetical, next to `suggested_same_person`, the count of suggested pairs not merged automatically.
- The same change applies to every injector row in `recall_by_injector`. The must-not-merge block is unchanged.
