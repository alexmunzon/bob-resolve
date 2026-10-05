## PR 08: Release 0.1.0 fixes (2026-10-05)

- `review apply` refuses a new run folder that is the old run, holds it, or sits inside it (real paths, symlinks followed), and refuses a new run id equal to the old one. Before, `--overwrite` could replace the old run.
- `decisions_applied` counts only "same person" merges that survive the cluster check. Merges the check cuts again are listed as `decisions_cut`. A second review keeps the first review's merges and labels.
- Severity is high only for an identity conflict, or a "same person" suggestion where both records hold active policies under different client ids. Within a severity the closest calls (score nearest a cutoff) come first. The demo queue is now 0 high and 89 medium (was 65 and 24).
- New `--mask-mbi` option. A run written under a `public` folder is refused without it. The public demo shows only the last 4 MBI characters, and a test checks it for any full MBI.
- Version 0.1.0. Hard cases run in both shared-ids modes in the end-to-end tests, and a test rebuilds the demo and compares it byte for byte with the committed copy.
