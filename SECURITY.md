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

The locked dashboard development tooling includes **braces GHSA-vfj7-8cjw-p6xm / CVE-2026-93687**.
The [GitHub-reviewed advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), updated
2026-10-02, lists braces `<=3.0.3` as affected and no patched release at the time of review. Deeply
nested brace patterns can exhaust the stack and cause denial of service. npm reports five high-severity
package nodes in this repository's full audit; they trace to this one underlying advisory.

The production-only npm lockfile audit (`--omit=dev`) reported **zero findings**. That result does not
resolve the tooling vulnerability or prove runtime safety. Avoid feeding untrusted glob/brace patterns
to affected build/lint tooling. Revisit a supported upstream fix when available; no forced upgrade or
unverified dependency override has been applied.

The [dated review](docs/security-review-2026-10-06.md) records audit coverage and exclusions. It did not
review hosting/account settings, runtime storage, Git history, binary fixtures, environment files, or
unknown vulnerabilities. Keep `.env` and `.env.*` contents private and unread during repository work,
including example templates. This demo needs no credentials or paid services.
