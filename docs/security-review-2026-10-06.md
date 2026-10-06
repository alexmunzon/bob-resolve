# Bounded security review, 2026-10-06

The dependency and tracked-source inventory ran 22:38–22:43 UTC on the October 6 working tree.
Repository hygiene was prepared separately on visual baseline `7d20551`. This is dated evidence,
not a security certification, a penetration test, or approval to process real insurance records.
The hygiene changes do not alter engine behavior, dependencies, fixtures, or benchmark artifacts.

## Results and reproduction

- **Dashboard, all dependencies:** npm 11.9.0 reported five high-severity package nodes tracing to
  one advisory, braces [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) /
  CVE-2026-93687. The October 2 advisory lists `<=3.0.3` affected and no patched release. The
  full audit's nonzero exit status is an advisory finding, not an unsuccessful network request.
- **Dashboard, production only:** zero known npm audit findings when development dependencies
  were omitted. No braces, micromatch, or fast-glob runtime import was found in tracked dashboard
  TS/TSX/JS. This narrow source check is not complete runtime reachability proof.
- **Python:** pip-audit 2.10.1 queried the exact 39 registry package versions from `engine/uv.lock`
  against live PyPI advisories and reported zero known vulnerabilities, no skipped registry packages.
  It did not cover the editable project or direct Git dependency `agency-data-commons`.
- **Credentials:** detect-secrets 1.5.0 and supplemental token/private-key patterns scanned 192 of
  198 tracked files as UTF-8 text. Twenty-one candidates were reviewed as integrity/provenance
  hashes; no convincing committed credential candidate was found in that scope. Credential
  verification was disabled. No candidate values are included in this document.

To repeat the npm lockfile checks, from `dashboard/`:

```bash
npm audit --package-lock-only --ignore-scripts --json
npm audit --package-lock-only --ignore-scripts --omit=dev --json
```

Audit reports change as advisories change. Full-audit findings remain open until a supported fix
exists; do not use `npm audit fix --force` or an unverified braces override. Avoid untrusted
glob/brace patterns in affected development tooling.

## Supply-chain controls

Both dependency installers use the committed locks: `npm ci` and `uv sync --locked`. npm entries
resolve over HTTPS to registry.npmjs.org with integrity metadata; registry Python downloads have
hashes. The direct commons dependency is locked to commit
`a9a670fbd9ebced6f2201177d20716fb9944a4c0`, although its project declaration names tag `v0.2.0`.
Locks and hashes constrain resolution; they do not certify dependency integrity or behavior.

The hygiene pass pins the three existing official CI actions to full commit SHAs resolved from
their upstream tag refs on 2026-10-06:

| Action | Version reference | Verified commit |
|---|---|---|
| actions/checkout | v5 | `fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09` |
| actions/setup-node | v5 | `a0853c24544627f65ddf259abe73b1d18a591444` |
| astral-sh/setup-uv | v10.2.0 | `c18668ad3cf93ea998bef934396af7bb5c839dc7` |

CI retains `contents: read`, replay mode, Node 24, locked installs, and `npm run verify`. Checkout
does not persist credentials. A 20-minute job timeout bounds hung runs; superseded pull-request
verification runs cancel, while main-branch runs do not cancel automatically. GitHub-hosted
execution of this edited workflow still requires publication and a successful run for that commit.

## Threat boundaries and exclusions

The dashboard reads developer-selected committed public run files, with no tracked upload or
mutation API route found in the targeted source check. Its static theme initialization script
maps stored values to light/dark choices. These observations are not a comprehensive web audit.
See [SECURITY.md](../SECURITY.md) for intended use and private reporting instructions.

Excluded or unverified:

- `.env` and every `.env.*` file, including the tracked example template, were never opened.
- Binary images, non-UTF-8 fixtures, archived contents, ignored/untracked files, and Git history.
- Hosting security headers, authentication, account/branch settings, collaborator access, Actions
  policies, private storage, and secret-scanning configuration.
- Unknown vulnerabilities, malicious dependency behavior, and privacy/security design for real data.
- Public deployment and hosted CI state. Local verification evidence is recorded separately.

No hosting/account settings, credentials, history, or access permissions were changed by this pass.
Zero production-only audit findings and no convincing scanned credential candidate do not mean zero
total risk. Recheck advisories and affected sources after dependency, workflow, or publication changes.
