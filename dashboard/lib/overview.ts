import { count, formatUsd, percent, plural } from "@/lib/format";
import type { Metric, Run, Usage } from "@/lib/run-loader";

// Turns a run into the numbers the Overview shows. Pure, so tests check it without rendering.

const SOURCE_NAMES: Record<string, string> = { crm: "CRM", enrollment: "Enrollment" };
const SUGGESTIONS: Record<string, string> = {
  same_person: "Same person",
  different_people: "Different people",
  unsure: "Unsure",
};
const OFF_REASONS = {
  jev: "Off: not built yet. Recording costs money and needs approval each time.",
  llm: "Off until an Anthropic key and a spend cap are approved.",
};

export interface Row { label: string; value: string; note?: string }
export interface MetricView { name: string; value: string; meets: boolean; target: string; context: string }

const words = (key: string) => key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function bySource(run: Run): Row[] {
  const counts: Record<string, number> = {};
  for (const person of run.people) {
    for (const id of person.recordIds) {
      const source = id.split(":")[0];
      counts[source] = (counts[source] ?? 0) + 1;
    }
  }
  return Object.entries(counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([source, n]) => ({ label: SOURCE_NAMES[source] ?? words(source), value: count(n) }));
}

function usageTier(name: string, usage: Usage, merges: number, offReason: string): Row {
  const on = usage.mode !== "off";
  return {
    label: name,
    value: on ? count(merges) : "Off",
    note: on ? `${usage.mode}, ${plural(usage.calls, "call")}` : offReason,
  };
}

function metric(name: string, m: Metric, sideLabel: string): MetricView {
  return {
    name,
    value: percent(m.value),
    meets: m.meets_target,
    target: `Target at least ${percent(m.target)}`,
    context: `Enrollment side ${sideLabel}, shared ids ${m.shared_ids ? "on" : "off (MBI withheld)"}. ${words(m.label)}.`,
  };
}

function runTime(timings: Record<string, number> | null): Row {
  if (timings === null) {
    return { label: "Run time", value: "Not recorded", note: "Fixed-clock demo run, so a rerun is byte for byte the same." };
  }
  const ms = Object.values(timings).reduce((sum, t) => sum + t, 0);
  return { label: "Run time", value: `${(ms / 1000).toFixed(1)} s`, note: "Sum of the engine's stage timings." };
}

export function overview(run: Run) {
  const { scorecard: card, manifest, queue, mergeLog } = run;
  const side = card.enrollment_side_label;
  const tally = (key: "severity" | "suggestion") => {
    const counts: Record<string, number> = {};
    for (const item of queue) counts[item[key]] = (counts[item[key]] ?? 0) + 1;
    return counts;
  };
  const suggestions = tally("suggestion");
  return {
    recordsIn: count(card.records_in),
    bySource: bySource(run),
    unidentifiable: card.unidentifiable,
    people: count(card.people),
    leftSplit: card.people_left_split,
    households: count(card.households),
    tiers: [
      { label: "Rules", value: count(mergeLog.merges.rules ?? 0), note: "Auto-merged only when very sure." },
      usageTier("Jev", manifest.jev, mergeLog.merges.jev ?? 0, OFF_REASONS.jev),
      usageTier("LLM", manifest.llm, mergeLog.merges.llm ?? 0, OFF_REASONS.llm),
      {
        label: "Human review",
        value: count(mergeLog.merges.review ?? 0),
        note: manifest.decisions_applied === 0 ? "No review decisions applied to this run yet." : `${plural(manifest.decisions_applied, "decision")} applied.`,
      },
    ] satisfies Row[],
    queueSize: card.review_queue.size,
    severity: (["high", "medium"] as const).map((s) => ({ severity: s, count: tally("severity")[s] ?? 0 })),
    suggestions: Object.keys({ ...SUGGESTIONS, ...suggestions }).map((key) => ({
      label: SUGGESTIONS[key] ?? words(key),
      value: count(suggestions[key] ?? 0),
    })),
    metrics: [
      metric("Precision of auto-merges", card.metrics.auto_merge_precision, side),
      metric("Recall after review", card.metrics.recall_after_review, side),
      metric("Blocking recall", card.metrics.blocking_recall, side),
    ],
    usage: (["jev", "llm"] as const).map((key) => ({
      label: key === "jev" ? "Jev" : "LLM",
      value: `${formatUsd(manifest[key].cost_usd)}, ${plural(manifest[key].calls, "call")}`,
      note: manifest[key].mode === "off" ? "Off" : words(manifest[key].mode),
    })),
    runTime: runTime(manifest.timings_ms),
    runId: manifest.run_id,
    asOf: manifest.as_of,
    engine: manifest.versions.engine,
  };
}

export type OverviewData = ReturnType<typeof overview>;
