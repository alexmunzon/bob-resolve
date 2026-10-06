# bob-resolve: SPEC

Written 2026-10-05 from the SPEC interview with Alex (Session B), `HANDOFF-bob-resolve-kickoff.md`, and ROADMAP.md
sections 4, 6, 10, 12, 13. Roadmap name: Project 1, built second. This file wins over the kickoff brief from here on.

## 1. Business outcome

An acquired agency hands over a book of business where the same person shows up several times: once in the CRM with
a nickname, once in the enrollment platform with a legal name, once more as a stray duplicate client. There is no SSN.
bob-resolve decides which records are the same real person, builds one golden record per person with the source of
every field, groups people into households, explains every merge, and sends anything it is not sure about to a human.

Terms, once:
- **Entity resolution:** deciding which records in different files are the same real person.
- **Golden record:** the one best version of a person, built from all matched records, each field naming its source.
- **Blocking:** cheap rules that pick which pairs are worth comparing, so 2,000 clients do not become 2 million comparisons.
- **Gray zone:** pairs whose score is between the auto-reject and auto-match lines. Only these ever reach Jev, an LLM, or a human.

## 2. Decisions locked in the interview (2026-10-05)

1. **Input, phase 1:** a frozen snapshot of agency-intake-kit's seed-42 fixtures, copied into `fixtures/agency-a-snapshot/`
   with the source commit (`9064b4e`) recorded in `fixtures/agency-a-snapshot/SOURCE.md`. No code link to agency-intake-kit.
   **Phase 2:** the generator from `agency-data-commons` (two agencies, harder injectors). **Demo run:** agency-intake-kit's
   real `clean/` output once its PR 12 has merged.
2. **Error policy: a false merge is worse than a missed match.** Auto-merge only when very sure; doubtful pairs go to review.
   Targets: auto-merge precision at least 0.99; recall after review at least 0.90 (a true pair counts as found if it was
   auto-merged or sent to review with "same person" as the suggestion).
3. **Spend:** build all three benchmark arms. Jev recording capped at $0.50 per session. The LLM arm is built but off
   until Alex adds an Anthropic key and approves a cap; the README says its numbers are pending. Every recording is
   still asked for, in Alex's words, each time. Default mode everywhere is `replay` or `off`.
4. **Golden record field winner depends on the field.** Identity fields (birth date, MBI, legal first and last name)
   come from the most authoritative source: enrollment or carrier data over CRM. Contact fields (address, phone, email)
   come from the most recent record. Nicknames are kept as aliases. If two authoritative sources disagree on birth
   date or MBI, the field is not guessed: the person goes to review with reason `IDENTITY_CONFLICT`.
5. **Dashboard first screen answers "How many real people are in this book, and how sure are we?"**
6. **Defaults accepted:** `agency-data-commons` is a public repo; shared code is versioned by git tags with exact pins;
   the intake kit's planted examples move with the generator unchanged; dashboard tokens are copied from the intake kit
   now and extracted later; one changelog fragment per PR under `changelog.d/`; the extraction (commons PR 0a) starts
   only after Session A writes "v0.1.0 tagged" in HANDOFF-ORCHESTRATOR.md section 1.

## 3. Users and what each needs to see

- **Agency owner or Gyde ops lead:** how many real people and households, how many merges were automatic, how big the
  review queue is, what it cost.
- **Reviewer (data ops):** side-by-side records, the evidence per field, the suggested decision, one action to decide.
- **Engineer or hiring manager (George):** the benchmark table and the merge log that explains every decision.

## 4. Out of scope

Real people or real contact lists (ever, including Alex's own contacts); SSNs (refused as in agency-intake-kit
SSN-001); real CRM connectors; editing data in the dashboard; user accounts; training a model on review labels
(labels are stored, not learned from, in v1); any carrier or vendor name beyond the six fictional carriers.

## 5. Inputs

**Phase 1 snapshot** (`fixtures/agency-a-snapshot/`, copied byte for byte, about 1 MB):
- `clients.csv`, `households.csv`, `policies.csv` from `fixtures/agency-a/canonical-defected/`. Clients are the CRM side:
  2,040 rows (2,000 people plus 30 near-duplicate and 10 exact-copy client ids, each with `copy_of`). Identity defects live only here.
- `enrollment_export.csv` from `fixtures/agency-a/drop/`: the enrollment platform side, one row per policy, legal names,
  semicolon delimited, `Birth Dt (mm/dd/yy)` dates (two-digit years pivot at 1930, as in the intake kit), MBI, policy number.
- `ground_truth.json`: the 160 unscored identity defects (60 nickname, 40 name_typo, 20 dob_transposition,
  10 dob_month_day_swap, 30 near_duplicate_client with `copy_of`), each keyed by `client_id`.

**Derived clean enrollment side** (decided 2026-10-05 after PR 2 found the enrollment export repeats the CRM's
defected values): `fixtures/agency-a-derived/enrollment_clean.csv` is built by code from the snapshot, replacing each of
the 130 nickname, name_typo, dob_transposition, and dob_month_day_swap values with its recorded original (`from`), so
the CRM says Dave while enrollment says David. Labeled "derived from the answer key" everywhere it is reported; the
benchmark reports the snapshot and the derived set separately.
Because MBI and policy number still match exactly across files, every target in decision 2 is also measured
with MBI and policy number withheld from blocking and scoring ("no shared ids" mode), and the README leads with that number.

**Pair answer key** (built by code, never hand-edited): an enrollment row and a CRM client are the same person when the
row's policy number resolves through `policies.csv` to that `client_id`; a near-duplicate client is the same person as
its `copy_of`. PR 2 reports any enrollment row that does not resolve, rather than dropping it silently.

**Hard cases** (`fixtures/hard-cases/`, hand-written synthetic, under 30 rows): the must-not-merge examples in section 9
that the generator cannot produce yet.

**Phase 2** (commons PRs C1 and C2): a second agency with a known overlap of people, plus maiden and hyphenated names,
moved households, shared household phones and emails, a child on a parent's policy, the same policy under two member ids.

## 6. Pipeline

1. **Load and normalize** with lineage on every row (source file, row number, raw hash). Names: case, punctuation,
   suffixes (Jr, Sr, II, III kept as a separate field, never dropped), nickname table, phonetic key. DOB: parsed, plus
   the transposition and month-day-swap variants as comparison features. Address, phone, email normalized.
2. **Blocking** (any key puts a pair in the candidate set): exact MBI; exact email; exact phone; DOB plus first initial
   of last name; phonetic surname plus ZIP3. Target: blocking recall at least 0.98 of true pairs.
3. **Scoring (rules arm):** a comparison vector per pair (Jaro-Winkler on names with nickname awareness, DOB exact or
   variant, MBI, address, phone, email, suffix) and hand-tuned weights. Two cutoffs, both in `config.py`: at or above
   the high line, auto-match; below the low line, auto-reject. **Guard rails that override the score:** different
   generational suffix (Jr vs Sr) is never auto-merged; a shared MBI with a DOB that is neither within one edit
   nor a month-day swap is never auto-merged (a pasted MBI is a data-entry error, not identity proof); shared phone or email alone never merges.
   Added 2026-10-05 after reviews: GR-004 a name plus DOB key held by records that conflict never auto-merges, except
   that records tied together by MBI (shared ids on) or an exact phone or email are one person's own records
   and their conflicts do not count (a person who moved is not ambiguous with themselves, PR 10b), though a different
   MBI (shared ids on) always counts and a shared street is not a tie (PR 21c); GR-005
   first names that are not nicknames of each other never auto-merge when they are distinct formal names, under 5
   letters, more than one typo apart, or one edit apart at the end where either name ends in a vowel or y (Patrick
   and Patricia, Mario and Maria, Andrew and Andrea, Louis and Louise), and a shared MBI never overrides it; a
   year-digit DOB substitution counts as a far DOB; GR-006 a DOB transposition that moves the year by more than 1
   needs MBI, phone, email, street, or a linking policy to agree; GR-007 (Alex, 2026-10-05, replaced in PR 10b) name
   plus DOB as the only agreeing evidence never auto-merges: a pair needs one more agreeing fact, MBI (shared ids on),
   phone, email, street, or a linking policy (the same policy id or carrier member id; a shared id, so withheld in no
   shared ids mode), else gray with "unsure"; GR-008 (PR 21b) name plus DOB plus a shared street as the only
   agreeing evidence never auto-merges, since a household or care facility street is shared by many people: gray
   with "unsure". Gray pairs from these rails carry the rule id and a suggestion of
   "different people" or "unsure".
4. **Jev gate on the gray zone** (after commons exists): `noul` "Is record B the same person as record A?" and `choice`
   household role (self, spouse, dependent, unrelated). Payload minimized to the compared fields only, no notes.
   Thresholds in `config.py`; Jev never overrides a guard rail. `off` mode sends every gray-zone pair to review.
5. **LLM arm** (built, off by default): Sonnet writes a one-paragraph rationale for pairs Jev is unsure about; Opus only
   on high-stakes pairs (a merge would move an active policy or a commission line). Own cassettes, own budget argument.
6. **Clusters and golden records:** connected components over accepted matches, then a check that no cluster holds two
   different DOBs from authoritative sources (else `IDENTITY_CONFLICT` to review). Survivorship per decision 4.
7. **Review queue:** one item per gray-zone pair or conflict, with both records, per-field evidence, the deciding tier,
   the suggestion, and a severity (high when money or coverage would move). Decisions are stored as labels.
8. **Merge log:** append-only JSONL, one line per merge or split, with pair, tier, score, confidence, rule or question
   id, run id, and time. Never rewritten; a correction is a new line.

## 7. Run outputs (one immutable run folder, same shape idea as the intake kit)

`manifest.json` (inputs and hashes, versions, timings, Jev and LLM usage and cost, mode per tier), `people.parquet` and
`people.csv` (golden records with per-field source and tier), `households.json`, `merge_log.jsonl`, `review_queue.jsonl`,
`scorecard.json` (blocking recall, auto-merge precision, recall after review, review queue size, per tier counts),
`benchmark.json` (per arm). The dashboard renders the same JSON from a committed demo run.

## 8. Dashboard pages and the one question each answers

- **Overview:** How many real people are in this book, and how sure are we? (records in, people out, households,
  merges by tier, review queue size, cost, run time; one screen at 1440 with no scrolling)
- **Clusters:** Why did these records become one person? (a household as a small graph, golden record with sources)
- **Review queue:** What needs a human, most important first? (side by side, evidence, suggestion)
- **Benchmark:** How good is each approach, and at what cost? (rules, rules plus Jev, rules plus Jev plus LLM)
- **Changes:** What changed since the last run? (people added, merged, split)

## 9. Concrete examples (each becomes a test)

1. **Happy path, snapshot.** The full snapshot runs end to end in `off` mode for Jev and LLM. 2,000 golden people
   (plus or minus the people the run honestly leaves split, reported), auto-merge precision at least 0.99, recall after
   review at least 0.90, blocking recall at least 0.98, every golden field names its source row and deciding tier.
2. **Near-duplicate with a typo.** CRM client C-02011 (last name "Nlan") is a copy of C-00023. They end in one cluster,
   by auto-merge or by a review item suggesting "same person"; the merge log names the tier and the score.
3. **Nickname across sources.** Hard case HC-009 (C-00011 has only an ACA policy, so no enrollment row) and every
   nickname pair in the derived clean enrollment side: CRM says "Dave", enrollment says "David", same DOB and MBI.
   Same person. The golden first name is "David" (enrollment wins identity fields) and "Dave" is kept as an alias.
4. **Must not merge, twins.** Hard case: two people, same last name, same DOB, same address and phone, different first
   names and different MBIs. They stay two people in one household; no merge line in the log.
5. **Must not merge, Jr and Sr.** Hard case: "Robert Hale Sr" and "Robert Hale Jr", same address and phone, DOBs 27 years
   apart. Never auto-merged (suffix guard rail); if anything routes them, it is review with the suggestion "different people".
6. **Must not merge, shared contact details.** Hard case: two spouses share a phone and an email, different names and DOBs.
   Two people, one household, Jev household role (when on) is spouse; shared contact alone never merges.
7. **Must not guess, identity conflict.** Hard case: the same MBI on two records whose DOBs are not within one edit and
   whose names differ. Not auto-merged; review item with reason `IDENTITY_CONFLICT` and severity high.
8. **Jev off.** With `JEV_MODE=off`, every gray-zone pair goes to the review queue, the run still completes, and the
   manifest says Jev was off with zero calls and zero cost.

## 10. End-to-end check

`npm run verify` green, then `npm run demo` writes the committed demo run from the snapshot in `off` mode, and
`tests/e2e/test_snapshot.py` asserts examples 1 to 8 and every target in decision 2 against the pair answer key.

## 11. PR plan

Lanes: **S** serial, **B** matching engine, **C** dashboard, **X** commons (in `agency-data-commons`, after the gate).
Under 400 lines each (expect about twice the estimate after formatting; ship it as one PR and report the real number),
tests first, one changelog fragment per PR.

| PR | Name | Repo | Lane | Needs merged first | Main files | Est. lines | Done when |
|---|---|---|---|---|---|---|---|
| SPEC | This file | bob | S | none | SPEC.md | docs | Alex has read it |
| 1 | Scaffold | bob | S | SPEC | engine (uv), dashboard (Next.js), verify, CI, settings, Stop hook, changelog.d | generated | Verify green locally |
| 2 | Snapshot and answer key | bob | B | 1 | fixtures/agency-a-snapshot, fixtures/hard-cases, loaders with lineage, pair answer key builder | 350 | Every enrollment row resolves or is reported; answer key counts match ground truth |
| 3 | Normalizers | bob | B | 2 | names (nickname table, suffix, phonetic), dob variants, address, phone, email | 350 | Property tests pass; examples 3 and 5 normalize correctly |
| 4 | Blocking | bob | B | 3 | blocking keys, candidate pairs | 250 | Blocking recall at least 0.98 reported |
| 5 | Scoring, cutoffs, guard rails (rules arm) | bob | B | 4 | comparison vectors, weights, cutoffs, guard rails in config.py | 350 | Auto-merge precision at least 0.99 on the snapshot; examples 4, 5, 7 hold |
| 6 | Clusters, golden records, merge log | bob | B | 5 | clustering, survivorship, IDENTITY_CONFLICT, merge log | 400 | Every golden field names source and tier; examples 2, 3 pass |
| 7 | Review queue and run command (tag v0.1.0) | bob | S | 6 | queue, CLI, run folder, manifest, scorecard, `npm run demo` | 400 | Examples 1 to 8 pass end to end in off mode |
| 8 | Dashboard shell and Overview | bob | C | 7 | layout, overview tiles, copied tokens, run loader | 380 | Overview answers the first-screen question at 1440 and 375 |
| 9 | Clusters and Review queue pages | bob | C | 8 | household graph, side-by-side review | 400 | Examples 2, 4, 6 visible |
| C0a | Extract shared packages | commons | X | aik v0.1.0 tagged | three packages, jev_client/config.py, budget and cassette dir as required arguments, import scan test | 300 plus moved code | Verify green; tag commons v0.1.0 |
| C0b | agency-intake-kit depends on commons | aik | X | C0a, coordinated with Session A | pyproject, config.py, delete local copies | 150 | aik CI green, fixtures byte-identical |
| C1 | Second agency with overlapping people | commons | X | C0a | multi-agency world; planting stays agency A only | 350 | Two agencies share a known set of people |
| C2 | Harder identity injectors and pair truth | commons | X | C1 | maiden and hyphenated names, moved households, shared contacts, child on parent policy, two member ids; true-pair and cluster truth | 400 | Every injector labeled; tag commons v0.2.0 |
| 10 | Switch to commons | bob | B | 7, C2 | depend on commons tag; generated two-agency fixtures; snapshot kept as a regression test | 250 | Both fixtures pass; targets reported on each |
| 11 | Jev same-person gate and household role | bob | B | 10 | noul and choice questions, minimized payloads, cassettes | 350 | Replay works offline; recording waits for Alex's yes |
| 12 | LLM gray-zone arm | bob | B | 11 | Sonnet rationale, Opus on high-stakes pairs, own cassettes and budget | 300 | Off by default; replay only in CI |
| 13 | Benchmark | bob | B | 11 | three arms: precision, recall, F1, cost per 10,000 pairs, p50 and p95 latency | 300 | Table generated from committed runs; LLM row says pending if not recorded |
| 14 | Benchmark and Changes pages | bob | C | 9, 13 | benchmark table page, run diff page | 350 | Both pages render the demo run |
| 15 | Demo from intake kit output | bob | S | 14, aik PR 12 | reader for aik `clean/` tables, demo run regenerated | 250 | Demo run reads aik clean output end to end |
| 16 | README, ADRs, screenshots, release | bob | S | all | README standard, ADRs, v1.0.0 | 300 mostly docs | Fable sweep done; tag v1.0.0 |

Parallel lanes: PRs 2 to 7 are a chain; PRs 8 and 9 start when PR 7 merges, alongside the commons lane once its gate opens.

## 12. Guardian rules (every brief repeats these)

- Synthetic data only; never a real name list. No SSN. Model payloads minimized; free-text notes never sent.
- Jev and LLM default `replay` or `off`. No agent ever sets `JEV_MODE=record` or `live`; the orchestrator records, after
  Alex says yes in his own words, within the cap. No Anthropic key is set; the LLM arm stays off until he adds one.
- Never read `.env`. No push, repo creation, PR, or Vercel link without Alex's words for that action.
- Do not break agency-intake-kit: C0b keeps its CI green and fixtures byte-identical, coordinated with Session A, with
  a revert as the rollback path.
- Benchmark numbers are labeled "measured on synthetic data". No em dashes.
