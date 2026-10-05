import { ruleName, ruleText, sourceLabel, suggestionLabel } from "@/lib/explain";
import type { Evidence, QueueItem, RecordView, Run } from "@/lib/run-loader";

// Turns the review queue into what the Review queue page shows. Pure, so tests check it without
// rendering. The page only reads: decisions go in a file that `bob-resolve review apply` reads.

export type Status = "agree" | "disagree" | "missing";
export interface EvidenceRow { label: string; values: string[]; status?: Status; note?: string }

// Engine comparison levels (engine score/compare.py) in words, with the status each one means.
const LEVELS: Record<string, [Status, string]> = {
  equal: ["agree", "Same"],
  same: ["agree", "Same"],
  exact: ["agree", "Same"],
  nickname: ["agree", "Nickname of each other"],
  close: ["disagree", "Close spelling, not the same"],
  one_missing: ["missing", "Only one record has one"],
  transposition: ["disagree", "Two digits swapped"],
  month_day_swap: ["disagree", "Month and day swapped"],
  one_edit: ["disagree", "One digit differs"],
  far: ["disagree", "Different"],
  different: ["disagree", "Different"],
};

type Field = { label: string; key?: string; value: (r: RecordView) => string | null };
const FIELDS: Field[] = [
  { label: "First name", key: "first", value: (r) => r.first_name },
  { label: "Last name", key: "last", value: (r) => r.last_name },
  { label: "Birth date", key: "dob", value: (r) => r.dob },
  { label: "MBI (last 4 only)", key: "mbi", value: (r) => r.mbi_masked },
  { label: "Street", key: "street", value: (r) => r.address_line1 },
  { label: "City", value: (r) => r.city },
  { label: "State", key: "state", value: (r) => r.state },
  { label: "ZIP", key: "zip5", value: (r) => r.zip },
  { label: "Phone", key: "phone", value: (r) => r.phone },
  { label: "Email", key: "email", value: (r) => r.email },
  { label: "Source", value: (r) => `${r.source_file}, row ${r.row_number}` },
  { label: "Active policy", value: (r) => (r.active_policy ? "Yes" : "No") },
];

function judge(key: string, ev: Evidence | undefined, values: (string | null)[], sharedIds: boolean) {
  const level = ev?.[key];
  if (typeof level === "string" && LEVELS[level]) {
    const [status, note] = LEVELS[level];
    if (key === "first" && level === "close" && ev?.first_typo === true) return { status, note: "One typo apart" };
    return { status, note };
  }
  if (key === "mbi" && !sharedIds && values.every(Boolean)) return { status: "missing" as const, note: "Not compared: MBI withheld in this run" };
  return { status: "missing" as const, note: "Missing on at least one record" };
}

export function evidenceRows(item: QueueItem, sharedIds: boolean): EvidenceRow[] {
  const ev = item.pairs.length === 1 ? item.pairs[0].evidence : undefined;
  return FIELDS.map(({ label, key, value }) => {
    const values = item.records.map(value);
    const shown = values.map((v) => v ?? "Missing");
    return key && ev ? { label, values: shown, ...judge(key, ev, values, sharedIds) } : { label, values: shown };
  });
}

function nearerLine(item: QueueItem, run: Run): string {
  const score = item.pairs[0]?.score;
  if (score === undefined) return "No scored pair";
  const high = run.manifest.thresholds?.score_high ?? 0.99;
  const low = run.manifest.thresholds?.score_low ?? 0.1;
  const d = item.cutoff_distance.toFixed(3);
  return high - score <= score - low ? `${d} below the auto-match line (${high})` : `${d} above the auto-reject line (${low})`;
}

export function reviewItems(run: Run) {
  return run.queue.map((item, i) => ({
    id: item.item_id,
    position: i + 1,
    severity: item.severity,
    suggestion: item.suggestion,
    suggestionLabel: suggestionLabel(item.suggestion),
    rules: item.rule_ids.map((id) => ({ id, name: ruleName(id), text: ruleText(id) })),
    detail: item.detail,
    score: item.pairs[0]?.score.toFixed(3) ?? "None",
    nearer: nearerLine(item, run),
    alreadyOnePerson: item.already_one_person,
    records: item.records.map((r) => `${sourceLabel(r.source)} ${r.record_id}`),
    rows: evidenceRows(item, run.scorecard.shared_ids),
    decisionLine: JSON.stringify({
      item_id: item.item_id,
      decision: item.suggestion === "different_people" ? "different_people" : "same_person",
      reviewer: "your name",
      decided_at: "2026-10-05T15:00:00+00:00",
    }),
  }));
}

export type ReviewItemView = ReturnType<typeof reviewItems>[number];

/** The filter choices: only values present in this queue, in a fixed order. */
export function filterOptions(items: ReviewItemView[]) {
  const suggestions = [...new Set(items.map((i) => i.suggestion))].sort();
  const rules = [...new Set(items.flatMap((i) => i.rules.map((r) => r.id)))].sort();
  return {
    suggestions: suggestions.map((s) => ({ value: s, label: suggestionLabel(s) })),
    rules: rules.map((r) => ({ value: r, label: `${r}: ${ruleName(r)}` })),
  };
}

export function applyFilters(items: ReviewItemView[], suggestion: string, rule: string) {
  return items.filter(
    (i) => (suggestion === "" || i.suggestion === suggestion) && (rule === "" || i.rules.some((r) => r.id === rule)),
  );
}
