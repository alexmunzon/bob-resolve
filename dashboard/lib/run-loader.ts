// Parses one run folder's files from text, so the server (the committed demo run) and a future
// in-browser loader share the same checks. Pattern copied from plan-diff lib/run-loader.ts (c13d5c3).
// Shape checks only: the engine is the real validator. These catch a wrong folder, a mixed-up run,
// or an unmasked MBI before anything reaches the page.

export type Mode = "off" | "replay" | "record" | "live" | "on";
export interface Usage { mode: Mode; calls: number; cost_usd: number }
export interface Metric {
  value: number;
  target: number;
  meets_target: boolean;
  label: string;
  enrollment_side: string;
  shared_ids: boolean;
}

export interface Manifest {
  run_id: string;
  created_at: string;
  as_of: string;
  jev: Usage;
  llm: Usage;
  timings_ms: Record<string, number> | null;
  decisions_applied: number;
  versions: { engine: string };
  thresholds?: { score_high: number; score_low: number };
}

/** How the true pairs ended up. Older runs do not write it. */
export interface Resolution {
  true_pairs: number;
  found_automatically: number;
  suggested_same_person: number;
  human_confirmed_merges: number;
  awaiting_review: number;
}

export interface Scorecard {
  records_in: number;
  people: number;
  households: number;
  unidentifiable: number;
  people_left_split: number;
  enrollment_side_label: string;
  shared_ids: boolean;
  label: string;
  merges: { auto: number; review: number; splits: number };
  metrics: Record<"blocking_recall" | "auto_merge_precision" | "recall_after_review", Metric>;
  per_tier: { jev: { calls: number; mode: Mode }; llm: { calls: number; mode: Mode } };
  review_queue: { size: number; by_severity: Record<string, number>; by_reason: Record<string, number> };
  resolution?: Resolution;
  unidentifiable_records?: { record_id: string; source_file: string; row_number: number }[];
}

/** A record as the reviewer sees it: minimized, MBI masked to the last 4. */
export interface RecordView {
  record_id: string;
  source: string;
  source_file: string;
  row_number: number;
  first_name: string | null;
  last_name: string | null;
  dob: string | null;
  address_line1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  phone: string | null;
  email: string | null;
  mbi_masked: string | null;
  active_policy: boolean;
}
export type Evidence = Record<string, number | string | boolean | null>;
export interface PairEvidence { a: string; b: string; score: number; decision: string; evidence: Evidence }
export interface QueueItem {
  item_id: string;
  kind: string;
  reason: string;
  severity: "high" | "medium";
  suggestion: string;
  rule_ids: string[];
  cutoff_distance: number;
  already_one_person: boolean;
  records: RecordView[];
  pairs: PairEvidence[];
  detail: string;
}
export const GOLDEN_FIELDS = [
  "first_name", "last_name", "suffix", "dob", "mbi", "address_line1", "city", "state", "zip", "phone", "email",
] as const;
export type GoldenField = (typeof GOLDEN_FIELDS)[number];
export interface GoldenValue { value: string; source: string; sourceFile: string; row: string; rule: string; tier: string }
export interface Person {
  personId: string;
  householdId: string;
  recordIds: string[];
  aliases: string[];
  fields: Record<GoldenField, GoldenValue>;
}
export interface MergeLine { line: number; action: string; a: string; b: string; tier: string; score: number; rule_ids: string[] }
export interface MergeLogSummary { lines: number; merges: Record<string, number>; entries: MergeLine[] }
export interface Household { household_id: string; person_ids: string[] }
export type Member = RecordView & { person_id: string };

export interface Run {
  manifest: Manifest;
  scorecard: Scorecard;
  people: Person[];
  queue: QueueItem[];
  mergeLog: MergeLogSummary;
  households: Household[];
  members: Member[];
}

export type RunFiles = Record<keyof typeof FILE_NAMES, string>;

export const FILE_NAMES = {
  manifest: "manifest.json",
  scorecard: "scorecard.json",
  people: "people.csv",
  queue: "review_queue.jsonl",
  mergeLog: "merge_log.jsonl",
  households: "households.json",
  members: "members.jsonl",
} as const;

const SEVERITIES = ["high", "medium"];
// The run only ever writes the last 4 characters of an MBI, behind 7 stars.
const MASKED_MBI = /^\*{7}[A-Z0-9]{4}$/;

function check(ok: boolean, where: string, problem: string): void {
  if (!ok) throw new Error(`${where}: ${problem}`);
}

function parseJson(text: string, where: string): Record<string, unknown> {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    throw new Error(`${where}: not valid JSON (${(error as Error).message})`);
  }
  check(typeof value === "object" && value !== null && !Array.isArray(value), where, "expected an object");
  return value as Record<string, unknown>;
}

function needs(record: Record<string, unknown>, where: string, keys: string[]): void {
  for (const key of keys) check(key in record, where, `missing ${key}`);
}

function jsonLines(text: string, name: string): Record<string, unknown>[] {
  return text
    .split("\n")
    .map((line, i) => [line, i + 1] as const)
    .filter(([line]) => line.trim() !== "")
    .map(([line, n]) => parseJson(line, `${name} line ${n}`));
}

/** Splits one CSV line, honoring quoted fields. people.csv has no line breaks inside fields. */
export function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted && ch === '"' && line[i + 1] === '"') {
      field += '"';
      i++;
    } else if (ch === '"') quoted = !quoted;
    else if (ch === "," && !quoted) {
      out.push(field);
      field = "";
    } else field += ch;
  }
  out.push(field);
  return out;
}

function parsePeople(text: string): Person[] {
  const where = FILE_NAMES.people;
  const [header, ...rows] = text.split(/\r?\n/).filter((line) => line !== "");
  const cols = splitCsvLine(header ?? "");
  const at = (name: string) => {
    const i = cols.indexOf(name);
    check(i >= 0, where, `missing column ${name}`);
    return i;
  };
  const [pid, hid, rids, mbi, alias] = [at("person_id"), at("household_id"), at("record_ids"), at("mbi"), at("aliases")];
  const cell = (cells: string[], name: string) => cells[at(name)];
  return rows.map((line, n) => {
    const cells = splitCsvLine(line);
    check(cells.length === cols.length, `${where} row ${n + 1}`, "wrong number of columns");
    check(cells[mbi] === "" || MASKED_MBI.test(cells[mbi]), `${where} row ${n + 1}`, "MBI is not masked");
    const fields = Object.fromEntries(
      GOLDEN_FIELDS.map((f) => [f, {
        value: cell(cells, f), source: cell(cells, `${f}_source`), sourceFile: cell(cells, `${f}_source_file`),
        row: cell(cells, `${f}_row`), rule: cell(cells, `${f}_rule`), tier: cell(cells, `${f}_tier`),
      }]),
    ) as Record<GoldenField, GoldenValue>;
    return {
      personId: cells[pid], householdId: cells[hid], recordIds: cells[rids].split(";"),
      aliases: cells[alias] ? cells[alias].split(";") : [], fields,
    };
  });
}

/** A record may carry only a masked MBI: never an `mbi` field, never more than the last 4. */
function maskedOnly(record: Record<string, unknown>, where: string): void {
  check(!("mbi" in record), where, "a full MBI field is not allowed");
  check(record.mbi_masked == null || MASKED_MBI.test(String(record.mbi_masked)), where, "MBI is not masked");
}

function usage(value: unknown, where: string): void {
  const u = value as Record<string, unknown>;
  check(typeof u === "object" && u !== null, where, "expected calls, cost, and mode");
  needs(u, where, ["mode", "calls", "cost_usd"]);
  check(typeof u.cost_usd === "number" && Number.isFinite(u.cost_usd) && u.cost_usd >= 0, where, "cost_usd must be a number, 0 or more");
}

const RESOLUTION_KEYS = [
  "true_pairs", "found_automatically", "suggested_same_person", "human_confirmed_merges", "awaiting_review",
] as const;

/** Optional, but when present every count must be a whole number, so the Overview never shows a made-up rate. */
function resolution(value: unknown): void {
  if (value === undefined) return;
  const where = `${FILE_NAMES.scorecard} resolution`;
  check(typeof value === "object" && value !== null && !Array.isArray(value), where, "expected an object");
  const r = value as Record<string, unknown>;
  for (const key of RESOLUTION_KEYS) {
    const n = r[key];
    check(typeof n === "number" && Number.isInteger(n) && n >= 0, where, `${key} must be a whole number, 0 or more`);
  }
  check((r.found_automatically as number) <= (r.true_pairs as number), where, "more pairs found than true pairs");
  check(
    (r.found_automatically as number) + (r.suggested_same_person as number) <= (r.true_pairs as number),
    where,
    "found plus suggested pairs exceed true pairs",
  );
}

export function parseRun(files: RunFiles): Run {
  const manifest = parseJson(files.manifest, FILE_NAMES.manifest);
  needs(manifest, FILE_NAMES.manifest, ["run_id", "created_at", "as_of", "jev", "llm", "timings_ms", "versions"]);
  usage(manifest.jev, `${FILE_NAMES.manifest} jev`);
  usage(manifest.llm, `${FILE_NAMES.manifest} llm`);

  const scorecard = parseJson(files.scorecard, FILE_NAMES.scorecard);
  needs(scorecard, FILE_NAMES.scorecard, [
    "records_in", "people", "households", "unidentifiable", "merges", "metrics", "per_tier", "review_queue", "label",
  ]);
  check(scorecard.label === "measured on synthetic data", FILE_NAMES.scorecard, "label must say measured on synthetic data");
  resolution(scorecard.resolution);

  const queue = jsonLines(files.queue, FILE_NAMES.queue).map((item, i) => {
    const where = `${FILE_NAMES.queue} line ${i + 1}`;
    needs(item, where, ["item_id", "reason", "severity", "suggestion"]);
    check(SEVERITIES.includes(item.severity as string), where, `unknown severity ${String(item.severity)}`);
    for (const record of (item.records as Record<string, unknown>[] | undefined) ?? []) maskedOnly(record, where);
    return item as unknown as QueueItem;
  });
  const members = jsonLines(files.members, FILE_NAMES.members).map((m, i) => {
    const where = `${FILE_NAMES.members} line ${i + 1}`;
    needs(m, where, ["person_id", "record_id", "source_file", "row_number"]);
    maskedOnly(m, where);
    return m as unknown as Member;
  });
  const hh = parseJson(files.households, FILE_NAMES.households);
  check(Array.isArray(hh.households), FILE_NAMES.households, "missing households list");

  const merges: Record<string, number> = {};
  const log = jsonLines(files.mergeLog, FILE_NAMES.mergeLog);
  for (const line of log) {
    if (line.action === "merge") merges[String(line.tier)] = (merges[String(line.tier)] ?? 0) + 1;
  }
  const entries = log.map((e, i) => ({ ...(e as unknown as MergeLine), line: i + 1 }));

  const people = parsePeople(files.people);
  const card = scorecard as unknown as Scorecard;
  check(people.length === card.people, FILE_NAMES.people, `has ${people.length} people, scorecard says ${card.people}`);
  check(queue.length === card.review_queue.size, FILE_NAMES.queue, `has ${queue.length} items, scorecard says ${card.review_queue.size}`);

  return {
    manifest: manifest as unknown as Manifest,
    scorecard: card,
    people,
    queue,
    mergeLog: { lines: log.length, merges, entries },
    households: hh.households as Household[],
    members,
  };
}
