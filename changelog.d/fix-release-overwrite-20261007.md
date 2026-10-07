## Fix: Preserve completed runs when overwrite fails (2026-10-07)

- Restore the previous completed run if publishing its replacement fails, including keyboard interruption.
- Keep the recovery backup if restoration fails; writing failures also preserve existing backups.
- Add synthetic review-run regressions that verify child output bytes, parent immutability, and successful replacement cleanup.
