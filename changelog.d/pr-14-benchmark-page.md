## PR 14: Benchmark page (2026-10-06)

- Add a Benchmark page and nav link that show `benchmark.json`, labeled measured on synthetic data.
- Automatic precision, recall and F1 lead. Recall if every suggestion were confirmed is shown only as a hypothetical, next to the count a reviewer has confirmed and the count awaiting review.
- Missing figures read Not recorded, the model tiers used are listed (none means rules only), and data that is not held out says it does not show accuracy on unseen data.
- The page refuses a malformed `benchmark.json` with a plain message, including a dataset side and status pair the engine never writes or a repeated run id.
