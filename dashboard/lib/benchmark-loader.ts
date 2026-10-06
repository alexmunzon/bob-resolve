import { readFile } from "node:fs/promises";
import path from "node:path";

// Reads and checks benchmark.json (written by the engine's benchmark builder). Strict on purpose:
// a malformed file stops the page with a plain message instead of showing a wrong number.
export const BENCHMARK_LABEL = "measured on synthetic data";
const FILE = "benchmark.json";
const DEMO_PATH = path.join(process.cwd(), "public", "demo-run", FILE);

export type DatasetStatus = "snapshot" | "derived" | "seen" | "held_out";
export type ModelTier = "jev" | "llm";
export const METRICS = [
  "automatic_precision", "automatic_recall", "automatic_f1", "recall_if_suggestions_confirmed", "human_confirmed_merges", "awaiting_review",
] as const;
export type MetricName = (typeof METRICS)[number];
const COUNTS = new Set<MetricName>(["human_confirmed_merges", "awaiting_review"]);
// The only side and status pairs the engine writes.
const STATUSES_BY_SIDE: Record<string, readonly DatasetStatus[]> = {
  snapshot: ["snapshot"], derived: ["derived"], "multi-a-b": ["seen", "held_out"], "hard-cases": ["seen"],
};

export interface BenchmarkRun {
  run_id: string;
  dataset: { side: string; label: string; status: DatasetStatus };
  shared_ids: boolean | null;
  candidate_pairs: number | null;
  model_tiers_used: ModelTier[];
  metrics: Record<MetricName, number | null>;
}
export interface BenchmarkReport { label: typeof BENCHMARK_LABEL; generated_at: string | null; runs: BenchmarkRun[] }

function check(ok: boolean, where: string, problem: string): asserts ok {
  if (!ok) throw new Error(`${FILE} ${where}: ${problem}`);
}
function obj(value: unknown, where: string): Record<string, unknown> {
  check(typeof value === "object" && value !== null && !Array.isArray(value), where, "expected an object");
  return value as Record<string, unknown>;
}
function oneOf<T extends string>(value: unknown, allowed: readonly T[], where: string, problem: string): T {
  check(allowed.includes(value as T), where, problem);
  return value as T;
}

function metric(value: unknown, name: MetricName, where: string): number | null {
  if (value === null) return null;
  check(typeof value === "number" && Number.isFinite(value) && value >= 0, where, "expected a number or null");
  if (COUNTS.has(name)) check(Number.isInteger(value), where, "must be a whole number");
  else check(value <= 1, where, "must be a rate from 0 to 1");
  return value;
}

function parseRun(value: unknown, index: number): BenchmarkRun {
  const where = `runs[${index}]`;
  const run = obj(value, where);
  const dataset = obj(run.dataset, `${where}.dataset`);
  const raw = obj(run.metrics, `${where}.metrics`);
  for (const key of Object.keys(raw)) check(METRICS.includes(key as MetricName), `${where}.metrics`, `unexpected ${key}`);
  const metrics = {} as Record<MetricName, number | null>;
  for (const name of METRICS) {
    check(name in raw, `${where}.metrics`, `missing ${name}`);
    metrics[name] = metric(raw[name], name, `${where}.metrics.${name}`);
  }
  const pairs = run.candidate_pairs;
  check(pairs === null || (Number.isInteger(pairs) && (pairs as number) >= 0), `${where}.candidate_pairs`, "expected a whole number or null");
  check(run.shared_ids === null || typeof run.shared_ids === "boolean", `${where}.shared_ids`, "expected true, false or null");
  check(Array.isArray(run.model_tiers_used), `${where}.model_tiers_used`, "expected a list");
  const tiers = run.model_tiers_used.map((tier) => oneOf(tier, ["jev", "llm"] as const, `${where}.model_tiers_used`, "expected jev or llm"));
  check(new Set(tiers).size === tiers.length, `${where}.model_tiers_used`, "tiers must not repeat");
  check(typeof run.run_id === "string" && run.run_id !== "", `${where}.run_id`, "expected a run id");
  check(typeof dataset.label === "string" && dataset.label !== "", `${where}.dataset.label`, "expected a label");
  const side = oneOf(dataset.side, Object.keys(STATUSES_BY_SIDE), `${where}.dataset.side`, "unknown dataset side");
  const status = oneOf(dataset.status, ["snapshot", "derived", "seen", "held_out"] as const, `${where}.dataset.status`, "unknown dataset status");
  check(STATUSES_BY_SIDE[side].includes(status), `${where}.dataset`, `run ${run.run_id} cannot pair side ${side} with status ${status}`);
  return {
    run_id: run.run_id,
    dataset: { side, label: dataset.label, status },
    shared_ids: run.shared_ids as boolean | null,
    candidate_pairs: pairs as number | null,
    model_tiers_used: tiers,
    metrics,
  };
}

export function parseBenchmark(source: string): BenchmarkReport {
  let parsed: unknown;
  try {
    parsed = JSON.parse(source);
  } catch {
    throw new Error(`${FILE}: not valid JSON`);
  }
  const report = obj(parsed, "top level");
  check(report.schema_version === 1, "schema_version", "unsupported schema_version");
  check(report.label === BENCHMARK_LABEL, "label", `label must say ${BENCHMARK_LABEL}`);
  check(report.generated_at === null || typeof report.generated_at === "string", "generated_at", "expected text or null");
  check(Array.isArray(report.runs), "runs", "expected a list");
  const runs = report.runs.map(parseRun);
  const seen = new Set<string>();
  runs.forEach(({ run_id }, i) => {
    check(!seen.has(run_id), `runs[${i}].run_id`, `run ${run_id} appears more than once`);
    seen.add(run_id);
  });
  return { label: BENCHMARK_LABEL, generated_at: report.generated_at as string | null, runs };
}

// Server only. Read once per build worker, like the demo run.
let demo: Promise<BenchmarkReport> | undefined;
export function loadDemoBenchmark(): Promise<BenchmarkReport> {
  demo ??= readFile(DEMO_PATH, "utf8").then(parseBenchmark, () => {
    throw new Error(`Could not read ${FILE} in ${path.dirname(DEMO_PATH)}`);
  });
  return demo;
}
