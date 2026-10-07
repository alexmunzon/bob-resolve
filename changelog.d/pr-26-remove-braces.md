## PR 26: Remove braces from the install (2026-10-06)

- Give Next's lint plugin a small local fast-glob stand-in built on Node's `fs.globSync` (npm override), so braces GHSA-vfj7-8cjw-p6xm (no patched release) and micromatch are no longer installed as packages (Vite still bundles a dormant copy in its file watcher, which test runs turn off; see SECURITY.md). 15 packages removed, none upgraded; the full `npm audit` now reports zero findings, and the production-only audit stays at zero.
- The stand-in matches fast-glob 3.3.1 on recorded ordinary `rootDir` patterns and refuses brace patterns; a new test checks the lockfile, the resolution and the pattern results. All lint rules still run. The same stand-in is already used in agency-intake-kit.
- SECURITY.md now says the braces package is removed, with one dormant copy bundled in Vite, not patched upstream. Engine, matching behavior, fixtures, benchmark numbers and the deployed site are unchanged.
