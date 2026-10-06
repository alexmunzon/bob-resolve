import { PageHeader } from "@/components/page-header";
import { CARD } from "@/components/tiles";
import { BENCHMARK_LABEL, type BenchmarkReport, type BenchmarkRun, type DatasetStatus, type MetricName } from "@/lib/benchmark-loader";
import { count, percent } from "@/lib/format";

// Automatic figures lead. The suggestion figure is shown apart, as a hypothetical, never as achieved.
const ROWS: { name: MetricName; label: string; hint: string }[] = [
  { name: "automatic_precision", label: "Automatic precision", hint: "Of the merges the engine made on its own, the share that were right." },
  { name: "automatic_recall", label: "Automatic recall", hint: "Of the true same-person pairs, the share the engine merged on its own." },
  { name: "automatic_f1", label: "Automatic F1", hint: "One score that balances the two above." },
  { name: "human_confirmed_merges", label: "Confirmed by a reviewer", hint: "Suggested merges a person has approved." },
  { name: "awaiting_review", label: "Awaiting review", hint: "Items still in the review queue." },
];

const STATUS_WORDS: Record<DatasetStatus, string> = {
  snapshot: "Used while building the rules, so not held out.",
  derived: "Used while building the rules, so not held out.",
  seen: "Seen while building the rules, so not held out.",
  held_out: "Held out: not used while building the rules.",
};

const MUTED = "muted";

function show(run: BenchmarkRun, name: MetricName): string {
  const value = run.metrics[name];
  if (value === null) return "Not recorded";
  return name === "human_confirmed_merges" || name === "awaiting_review" ? count(value) : percent(value);
}

function RunResults({ run, index }: { run: BenchmarkRun; index: number }) {
  const shared = run.shared_ids === null ? "not recorded" : run.shared_ids ? "on" : "off";
  const tiers = run.model_tiers_used.length ? run.model_tiers_used.map((t) => (t === "jev" ? "Jev" : "LLM")).join(", ") : "none (rules only)";
  return (
    <section aria-labelledby={`run-${index}`} className={CARD}>
      <div className="benchmark-header space-y-2">
        <h2 id={`run-${index}`} className="text-lg font-semibold break-words">Run {run.run_id}</h2>
        <p className="text-sm">Data: {run.dataset.label}. {STATUS_WORDS[run.dataset.status]}</p>
        <p className={`text-sm ${MUTED}`}>
          Model tiers used: {tiers}. Shared IDs {shared}.{" "}
          {run.candidate_pairs === null ? "Candidate pairs not recorded." : `${count(run.candidate_pairs)} candidate pairs.`}
        </p>
        {run.shared_ids !== null && (
          <p className={`text-sm ${MUTED}`}>
            {run.shared_ids
              ? "MBI and linking policy IDs were available to the matcher. Display masking does not remove that matching signal."
              : "MBI and linking policy IDs were withheld from matching."}
          </p>
        )}
        {run.dataset.status !== "held_out" && (
          <p role="note" className="benchmark-note">
            This data is not held out, so these figures are not accuracy on data the engine has never seen.
          </p>
        )}
      </div>
      <div className="table-scroll" role="region" aria-label={`Results for run ${run.run_id}`} tabIndex={0}>
        <table className="data-table benchmark-table text-left">
          <caption className="sr-only">Results for run {run.run_id}, {BENCHMARK_LABEL}</caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col" className="text-right">Result</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(({ name, label, hint }) => (
              <tr key={name}>
                <th scope="row">
                  {label}
                  <span className={`block font-normal ${MUTED}`}>{hint}</span>
                </th>
                <td className="text-right whitespace-nowrap tabular-nums">{show(run, name)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="benchmark-hypothesis">
        <span className="font-medium">Hypothetical, not achieved.</span> Recall if every same-person suggestion were confirmed:{" "}
        {show(run, "recall_if_suggestions_confirmed")}. So far {show(run, "human_confirmed_merges")} confirmed by a reviewer.
      </p>
    </section>
  );
}

export function Benchmark({ report }: { report: BenchmarkReport }) {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Bob Resolve / Synthetic benchmark" title="How well does the engine match people on its own?">
        <p className="page-description muted">
          All figures are {report.label}. Automatic figures count only merges the engine made without a person. Not recorded
          means the run did not measure it.
        </p>
      </PageHeader>
      {report.runs.length === 0 ? <p className="text-sm">No benchmark runs are recorded.</p> : report.runs.map((run, i) => <RunResults key={run.run_id} run={run} index={i} />)}
    </div>
  );
}
