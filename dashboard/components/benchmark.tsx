import { count, percent } from "@/lib/format";
import { BENCHMARK_LABEL, type BenchmarkReport, type BenchmarkRun, type DatasetStatus, type MetricName } from "@/lib/benchmark-loader";

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

const MUTED = "text-slate-600 dark:text-slate-400";

function show(run: BenchmarkRun, name: MetricName): string {
  const value = run.metrics[name];
  if (value === null) return "Not recorded";
  return name === "human_confirmed_merges" || name === "awaiting_review" ? count(value) : percent(value);
}

function RunResults({ run, index }: { run: BenchmarkRun; index: number }) {
  const shared = run.shared_ids === null ? "not recorded" : run.shared_ids ? "on" : "off";
  const tiers = run.model_tiers_used.length ? run.model_tiers_used.map((t) => (t === "jev" ? "Jev" : "LLM")).join(", ") : "none (rules only)";
  return (
    <section aria-labelledby={`run-${index}`} className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="space-y-1 border-b border-slate-200 p-4 dark:border-slate-800">
        <h2 id={`run-${index}`} className="text-lg font-semibold break-words">Run {run.run_id}</h2>
        <p className="text-sm">Data: {run.dataset.label}. {STATUS_WORDS[run.dataset.status]}</p>
        <p className={`text-sm ${MUTED}`}>
          Model tiers used: {tiers}. Shared IDs {shared}.{" "}
          {run.candidate_pairs === null ? "Candidate pairs not recorded." : `${count(run.candidate_pairs)} candidate pairs.`}
        </p>
        {run.dataset.status !== "held_out" && (
          <p role="note" className="text-sm font-medium text-amber-800 dark:text-amber-200">
            This data is not held out, so these figures are not accuracy on data the engine has never seen.
          </p>
        )}
      </div>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Results for run {run.run_id}, {BENCHMARK_LABEL}</caption>
        <thead className={`bg-slate-50 text-xs dark:bg-slate-950 ${MUTED}`}>
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Measure</th>
            <th scope="col" className="px-4 py-2 text-right font-medium">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {ROWS.map(({ name, label, hint }) => (
            <tr key={name}>
              <th scope="row" className="px-4 py-3 align-top font-medium">
                {label}
                <span className={`block text-xs font-normal ${MUTED}`}>{hint}</span>
              </th>
              <td className="px-4 py-3 text-right align-top whitespace-nowrap tabular-nums">{show(run, name)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-slate-200 p-4 text-sm dark:border-slate-800">
        <span className="font-medium">Hypothetical, not achieved.</span> Recall if every same-person suggestion were confirmed:{" "}
        {show(run, "recall_if_suggestions_confirmed")}. So far {show(run, "human_confirmed_merges")} confirmed by a reviewer.
      </p>
    </section>
  );
}

export function Benchmark({ report }: { report: BenchmarkReport }) {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">How well does the engine match people on its own?</h1>
        <p className={`mt-1 text-sm ${MUTED}`}>
          All figures are {report.label}. Automatic figures count only merges the engine made without a person. Not recorded
          means the run did not measure it.
        </p>
      </header>
      {report.runs.length === 0 ? <p className="text-sm">No benchmark runs are recorded.</p> : report.runs.map((run, i) => <RunResults key={run.run_id} run={run} index={i} />)}
    </div>
  );
}
