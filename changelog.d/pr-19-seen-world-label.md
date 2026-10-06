## PR 19: Honest label on the seen two-agency world (2026-10-06)

- The two-agency (multi-a-b) scorecard label no longer says the world was "held-out" and "never used to tune the matcher". That was false: PR 10b tuned the matcher on this world.
- The label now starts with "seen" and says the matcher was tuned on it, so the figures are not results on unseen data. It appears in `enrollment_side_label`, in `held_out.label` and in the CLI output.
- The constant is renamed from `HELD_OUT_LABEL` to `TWO_AGENCY_LABEL`. The CLI help, module docstrings and the end-to-end test name now call this world seen.
- The scorecard key `held_out` keeps its name for compatibility; the name is historical and does not mean the data is held out. The benchmark `held_out` status is unchanged and is still the only way to call a dataset held out.
- New assertions check that the label starts with "seen" and never says "held-out" or "never used to tune".
- The repo CLAUDE.md command list now calls this world seen.
