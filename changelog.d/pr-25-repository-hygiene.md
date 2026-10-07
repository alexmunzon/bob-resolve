## PR 25: Repository hygiene and trust boundaries (2026-10-06)

- Add a clearer repository front door, architecture map, locked setup, and documentation index with dated evidence separated from current guides.
- Add contributor and private security-reporting guidance; explain synthetic/public-only scope, matching before MBI masking, immutable review runs, and known tooling risk without claiming certification.
- Pin the three existing official CI actions to verified commit SHAs, disable persisted checkout credentials, bound verification to 20 minutes, and cancel superseded pull-request runs while retaining read-only permissions and the same checks.
- Document the unpatched braces development-tool advisory and bounded audit exclusions. Leave dependency versions, matching behavior, fixtures, benchmark claims, and dashboard presentation unchanged.
