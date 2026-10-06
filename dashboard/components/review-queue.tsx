"use client";

import { CircleCheck, CircleDashed, CircleX, type LucideIcon } from "lucide-react";
import { useId, useState } from "react";

import { SeverityBadge } from "@/components/severity-badge";
import { CARD } from "@/components/tiles";
import { applyFilters, filterOptions, type ReviewItemView, type Status } from "@/lib/review";
import { cn } from "@/lib/utils";

const MUTED = "muted";
const TH = "text-left whitespace-nowrap";
const TD = "align-top";
const PAGE_SIZE = 25;

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
    <li aria-label={`Item ${item.position}: ${item.id}`} className={cn(CARD, "review-item")}>
      <div className="review-item-header">
        <div className="review-item-decision">
          <span className="item-position">#{item.position}</span>
          <SeverityBadge tone={item.severity === "high" ? "error" : "warning"} label={item.severity === "high" ? "High" : "Medium"} />
          <span>Suggestion: <strong>{item.suggestionLabel}</strong></span>
        </div>
        <div>
          <p className="review-score">Score {item.score}, {item.nearer}</p>
          <code className="item-id">{item.id}</code>
        </div>
      </div>
      {item.alreadyOnePerson && (
        <p className="already-joined">
          Already joined through other accepted links. This direct pair is still awaiting review.
        </p>
      )}
      <ul className="review-rules space-y-1">
        {item.rules.map((r) => (
          <li key={r.id}><strong>{r.id} {r.name}:</strong> {r.text}</li>
        ))}
      </ul>
      <div className="table-scroll" role="region" aria-label={`Evidence for item ${item.position}`} tabIndex={0}>
        <table className="data-table evidence-table">
          <thead>
            <tr>
              <th className={TH}><span className="sr-only">Field</span></th>
              {item.records.map((r) => <th key={r} scope="col" className={TH}>{r}</th>)}
              <th scope="col" className={TH}>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {item.rows.map((row) => (
              <tr key={row.label}>
                <th scope="row" className={cn(TH, MUTED)}>{row.label}</th>
                {row.values.map((v, i) => <td key={i} className={TD}>{v}</td>)}
                <StatusCell status={row.status} note={row.note} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="decision-line">
        <summary className="cursor-pointer">Decision line for this item</summary>
        <pre tabIndex={0} className="code-sample mt-2">{item.decisionLine}</pre>
      </details>
    </li>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <div className="filter-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="filter-select">
        <option value="">All</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function ReviewQueue({
  items,
  initialPage = 1,
  initialSuggestion = "",
  initialRule = "",
}: {
  items: ReviewItemView[];
  initialPage?: number;
  initialSuggestion?: string;
  initialRule?: string;
}) {
  const [suggestion, setSuggestion] = useState(initialSuggestion);
  const [rule, setRule] = useState(initialRule);
  const [page, setPage] = useState(initialPage);
  const options = filterOptions(items);
  const shown = applyFilters(items, suggestion, rule);
  const pageCount = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const currentPage = Math.min(Math.max(1, page), pageCount);
  const pageLinkStart = Math.max(1, Math.min(currentPage - 2, pageCount - 4));
  const pageLinks = Array.from({ length: Math.min(5, pageCount) }, (_, i) => pageLinkStart + i);
  const first = shown.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const last = Math.min(currentPage * PAGE_SIZE, shown.length);
  const pageItems = shown.slice(first - 1, last);

  function updateFilter(key: "suggestion" | "rule", value: string) {
    if (key === "suggestion") setSuggestion(value);
    else setRule(value);
    setPage(1);
    const params = new URLSearchParams(window.location.search);
    if (value) params.set(key, value);
    else params.delete(key);
    params.set("page", "1");
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }

  function pageHref(targetPage: number) {
    const params = new URLSearchParams();
    if (suggestion) params.set("suggestion", suggestion);
    if (rule) params.set("rule", rule);
    params.set("page", String(targetPage));
    return `/review?${params.toString()}`;
  }

  return (
    <section aria-label="Queue" className="space-y-3">
      <div className={cn(CARD, "queue-toolbar")}>
        <Select label="Suggestion" value={suggestion} onChange={(value) => updateFilter("suggestion", value)} options={options.suggestions} />
        <Select label="Rule" value={rule} onChange={(value) => updateFilter("rule", value)} options={options.rules} />
        <p role="status" className="queue-count">
          {shown.length === 0
            ? suggestion || rule
              ? `No items match these filters (${items.length} total)`
              : "No items to review"
            : suggestion || rule
              ? `Showing ${first}-${last} of ${shown.length} filtered items (${items.length} total)`
              : `Showing ${first}-${last} of ${shown.length} items`}
        </p>
      </div>
      <ol className="space-y-3">
        {pageItems.map((item) => <Item key={item.id} item={item} />)}
      </ol>
      <nav aria-label="Review queue pages" className="queue-pager flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        {currentPage > 1
          ? <a className="underline underline-offset-2" href={pageHref(currentPage - 1)}>Previous page</a>
          : <span className={MUTED}>Previous page</span>}
        <span className="flex flex-wrap items-center gap-3">
          {pageLinks.map((number) => number === currentPage
            ? <span key={number} aria-current="page" aria-label={`Page ${number}`} className="font-semibold tabular-nums">{number}</span>
            : <a key={number} className="underline underline-offset-2 tabular-nums" href={pageHref(number)} aria-label={`Page ${number}`}>{number}</a>)}
          <span className={cn("tabular-nums", MUTED)}>of {pageCount} pages</span>
        </span>
        {currentPage < pageCount
          ? <a className="underline underline-offset-2" href={pageHref(currentPage + 1)}>Next page</a>
          : <span className={MUTED}>Next page</span>}
      </nav>
    </section>
  );
}
