# Security and trust boundaries

## Scope

bob-resolve v0.1.0 is a public, synthetic-data portfolio demonstration. It is not an approved workflow
for real client or health-insurance records, and no production-readiness or security certification is
claimed. The published dashboard reads committed demo files; it has no client-file upload, account
system, or editable review workflow. The matching engine and review CLI run locally.

- All repository fixtures and published records must remain synthetic. Never commit real personal
  data, SSNs, credentials, or private review files. Local `runs/` output is ignored, not encrypted or
  access-controlled by the application.
- MBI is used for matching before the demo's displayed/downloadable values are masked to their last
  four characters. Masking is not anonymization or a no-shared-ids evaluation. It would not make a real
  client dataset suitable for public release.
- Guard rails reduce false merges; they do not guarantee correct identities. Human review writes a
  new run and preserves its parent. A queued direct pair can already belong to one cluster through
  other links. No decision should be inferred from a score or shared household contact alone.
- Source hashes and append-only logs aid reproducibility and explainability. They do not provide
  external attestation, authenticated input, or tamper-proof storage against someone with write access.
- Jev and the LLM arm are not built; no model is called. Future external processing, uploads, or real
  data require a separate privacy/security design and approval.

## Report privately

Do not put credentials, real records, or exploit details in a public issue. Use the repository's
GitHub **Report a vulnerability** option if it is available. Otherwise, ask the
[repository owner](https://github.com/alexmunzon) for a private reporting channel through a contact
method listed on that profile. If no private contact is available, open a public issue containing only
a request for a private channel, with no sensitive details. Private-reporting configuration and a
response-time commitment have not been verified.

Once a private channel is established, include the affected commit/version, minimal synthetic
reproduction, impact, and relevant commands. Never include an active secret. If a credential was
exposed, its owner should revoke it through the provider; repository removal alone is insufficient.

## Known dependency risk, reviewed 2026-10-06

[braces GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) is a
high-severity stack-exhaustion denial of service through deeply nested brace patterns. The
GitHub-reviewed advisory, updated 2026-10-02, affects braces `<=3.0.3` and lists **no patched
release**.

**Status: braces package removed, one dormant bundled copy, not patched upstream.** No braces
package is installed, but one copy remains bundled inside Vite, the test runner's build tool (a
development dependency): Vite 8.3.2, and the newest release 8.3.3, compile chokidar 3.6.0 with
braces 3.0.3 into `vite/dist/node/chunks/node.js`. Only Vite's file watcher calls it. `npm test` and
CI run `vitest run`, which turns the watcher off, so it runs only in local watch mode, on this
project's own file paths. npm audit cannot see bundled copies. It goes away when Vite ships a
release without it. The dashboard lockfile has no braces or micromatch entry, and `npm audit`
reports zero findings for both the full and the production-only (`--omit=dev`) scope. Before the change, the full audit reported five high-severity
package nodes, all on one lint-tooling path: `eslint-config-next` → `@next/eslint-plugin-next` →
`fast-glob` → `micromatch` → braces. The production-only audit was already zero.

The lint plugin calls fast-glob in one place, and only when an ESLint config sets
`settings.next.rootDir` (this repo does not). An npm override (`"overrides": { "fast-glob":
"$fast-glob" }` with a `file:` development dependency) now gives the plugin a small local stand-in,
`dashboard/vendor/fast-glob-shim`, built on Node's own `fs.globSync`. It matches fast-glob 3.3.1 on the
recorded ordinary patterns (wildcards, `**`, character classes, plain and hidden folders, lists) and
refuses brace or extglob patterns with a clear error instead of expanding them. Known differences: it
does not descend into symlinked folders, and it drops a leading `./` from wildcard results. `dashboard/lib/__tests__/no-braces.test.ts`
checks the lockfile, the resolution and the pattern results. All Next lint rules still run. No package
version changed; 15 packages were removed. The same stand-in is used in agency-intake-kit.

This stand-in is our own code, not an upstream fix. Revisit it when Next or fast-glob changes: an
`eslint-config-next` upgrade must keep the tests green, and if braces ships a fix, decide whether to
return to upstream fast-glob. Do not run `npm audit fix --force`. The weekly advisory watch (a
scheduled read-only workflow that fails when a patched release ships or the advisory changes) lives in
agency-intake-kit, not in this repository.

The [dated review](docs/security-review-2026-10-06.md) records audit coverage and exclusions from before
the removal. It did not review hosting/account settings, runtime storage, Git history, binary fixtures, environment files, or
unknown vulnerabilities. Keep `.env` and `.env.*` contents private and unread during repository work,
including example templates. This demo needs no credentials or paid services.
