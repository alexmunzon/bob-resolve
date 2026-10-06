## PR 16: Percents that never round to perfect or to none (2026-10-06)

- A rate just under 100% now shows ">99.9%" instead of rounding up to "100.0%". Only a truly perfect rate shows "100.0%".
- A rate just over 0% now shows "<0.1%" instead of rounding down to "0.0%". Only a true zero shows "0.0%".
- Every other percent on the dashboard is unchanged, e.g. automatic recall still shows "99.6%" in the demo.
