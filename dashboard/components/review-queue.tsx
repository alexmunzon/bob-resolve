"use client";

import { CircleCheck, CircleDashed, CircleX, type LucideIcon } from "lucide-react";
import { useId, useState } from "react";

import { SeverityBadge } from "@/components/severity-badge";
import { CARD } from "@/components/tiles";
import { applyFilters, filterOptions, type ReviewItemView, type Status } from "@/lib/review";
import { cn } from "@/lib/utils";

const MUTED = "text-slate-600 dark:text-slate-400";
const TH = "px-2 py-1.5 text-left font-medium whitespace-nowrap";
const TD = "px-2 py-1.5 align-top";

// Color is never the only signal: every status has an icon and a word.
const STATUS: Record<Status, { word: string; icon: LucideIcon; color: string }> = {
  agree: { word: "Agree", icon: CircleCheck, color: "text-emerald-600 dark:text-emerald-400" },
  disagree: { word: "Disagree", icon: CircleX, color: "text-rose-600 dark:text-rose-400" },
  missing: { word: "Missing", icon: CircleDashed, color: "text-slate-500 dark:text-slate-400" },
};

function StatusCell({ status, note }: { status?: Status; note?: string }) {
  if (!status) return <td className={TD} />;
  const { word, icon: Icon, color } = STATUS[status];
  return (
    <td className={TD}>
      <span className="inline-flex items-center gap-1 font-medium">
        <Icon aria-hidden className={cn("size-4 shrink-0", color)} />
        {word}
      </span>
      {note && <span className={cn("block text-xs", MUTED)}>{note}</span>}
    </td>
  );
}

function Item({ item }: { item: ReviewItemView }) {
  return (
    <li aria-label={`Item ${item.position}: ${item.id}`} className={cn(CARD, "p-4")}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold tabular-nums">#{item.position}</span>
        <SeverityBadge tone={item.severity === "high" ? "error" : "warning"} label={item.severity === "high" ? "High" : "Medium"} />
        <span>Suggestion: <strong>{item.suggestionLabel}</strong></span>
        <span className={cn("tabular-nums", MUTED)}>Score {item.score}, {item.nearer}</span>
        <code className={cn("text-xs", MUTED)}>{item.id}</code>
      </div>
      <ul className="mt-2 space-y-1 text-sm">
        {item.rules.map((r) => (
          <li key={r.id}><strong>{r.id} {r.name}:</strong> {r.text}</li>
        ))}
      </ul>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className={TH}><span className="sr-only">Field</span></th>
              {item.records.map((r) => <th key={r} scope="col" className={TH}>{r}</th>)}
              <th scope="col" className={TH}>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {item.rows.map((row) => (
              <tr key={row.label} className="border-t border-slate-200 dark:border-slate-800">
                <th scope="row" className={cn(TH, MUTED)}>{row.label}</th>
                {row.values.map((v, i) => <td key={i} className={TD}>{v}</td>)}
                <StatusCell status={row.status} note={row.note} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer">Decision line for this item</summary>
        <pre className="mt-1 overflow-x-auto rounded bg-slate-100 p-2 text-xs dark:bg-slate-950">{item.decisionLine}</pre>
      </details>
    </li>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900">
        <option value="">All</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function ReviewQueue({ items }: { items: ReviewItemView[] }) {
  const [suggestion, setSuggestion] = useState("");
  const [rule, setRule] = useState("");
  const options = filterOptions(items);
  const shown = applyFilters(items, suggestion, rule);
  return (
    <section aria-label="Queue" className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <Select label="Suggestion" value={suggestion} onChange={setSuggestion} options={options.suggestions} />
        <Select label="Rule" value={rule} onChange={setRule} options={options.rules} />
        <p role="status" className={cn("text-sm tabular-nums", MUTED)}>Showing {shown.length} of {items.length} items</p>
      </div>
      <ol className="space-y-3">
        {shown.map((item) => <Item key={item.id} item={item} />)}
      </ol>
    </section>
  );
}
