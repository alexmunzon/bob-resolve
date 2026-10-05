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
}

export interface QueueItem { item_id: string; reason: string; severity: "high" | "medium"; suggestion: string }
export interface Person { personId: string; householdId: string; recordIds: string[] }
export interface MergeLogSummary { lines: number; merges: Record<string, number> }

export interface Run {
  manifest: Manifest;
  scorecard: Scorecard;
  people: Person[];
  queue: QueueItem[];
  mergeLog: MergeLogSummary;
}

export type RunFiles = Record<keyof typeof FILE_NAMES, string>;

export const FILE_NAMES = {
  manifest: "manifest.json",
  scorecard: "scorecard.json",
  people: "people.csv",
  queue: "review_queue.jsonl",
  mergeLog: "merge_log.jsonl",
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
  const [pid, hid, rids, mbi] = [at("person_id"), at("household_id"), at("record_ids"), at("mbi")];
  return rows.map((line, n) => {
    const cells = splitCsvLine(line);
    check(cells.length === cols.length, `${where} row ${n + 1}`, "wrong number of columns");
    check(cells[mbi] === "" || MASKED_MBI.test(cells[mbi]), `${where} row ${n + 1}`, "MBI is not masked");
    return { personId: cells[pid], householdId: cells[hid], recordIds: cells[rids].split(";") };
  });
}

function usage(value: unknown, where: string): void {
  const u = value as Record<string, unknown>;
  check(typeof u === "object" && u !== null, where, "expected calls, cost, and mode");
  needs(u, where, ["mode", "calls", "cost_usd"]);
  check(typeof u.cost_usd === "number" && Number.isFinite(u.cost_usd) && u.cost_usd >= 0, where, "cost_usd must be a number, 0 or more");
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

  const queue = jsonLines(files.queue, FILE_NAMES.queue).map((item, i) => {
    const where = `${FILE_NAMES.queue} line ${i + 1}`;
    needs(item, where, ["item_id", "reason", "severity", "suggestion"]);
    check(SEVERITIES.includes(item.severity as string), where, `unknown severity ${String(item.severity)}`);
    for (const record of (item.records as Record<string, unknown>[] | undefined) ?? []) {
      check(!("mbi" in record), where, "a full MBI field is not allowed");
      check(record.mbi_masked == null || MASKED_MBI.test(String(record.mbi_masked)), where, "MBI is not masked");
    }
    return item as unknown as QueueItem;
  });

  const merges: Record<string, number> = {};
  const log = jsonLines(files.mergeLog, FILE_NAMES.mergeLog);
  for (const line of log) {
    if (line.action === "merge") merges[String(line.tier)] = (merges[String(line.tier)] ?? 0) + 1;
  }

  const people = parsePeople(files.people);
  const card = scorecard as unknown as Scorecard;
  check(people.length === card.people, FILE_NAMES.people, `has ${people.length} people, scorecard says ${card.people}`);
  check(queue.length === card.review_queue.size, FILE_NAMES.queue, `has ${queue.length} items, scorecard says ${card.review_queue.size}`);

  return {
    manifest: manifest as unknown as Manifest,
    scorecard: card,
    people,
    queue,
    mergeLog: { lines: log.length, merges },
  };
}
