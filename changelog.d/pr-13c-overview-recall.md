## PR 13c: Honest recall on the Overview (2026-10-06)

- The Overview headline is now "Automatic recall": true pairs the engine merged with no reviewer, with the counts shown (2,159 of 2,167 in the demo). It has no target badge, because the 90% target was set for a different number.
- The old "Recall after review" card is renamed "Recall if every same-person suggestion were confirmed" and says it counts suggestions no one has confirmed.
- A new "Review status" panel shows merges confirmed by a reviewer (0 in the demo) and items awaiting review (19), linked to the review queue.
- An older run without resolution counts shows "Not recorded" instead of borrowing the suggestion figure.
- The run loader accepts the optional scorecard `resolution` block and refuses counts that are not whole numbers, 0 or more.
