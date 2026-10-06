import Link from "next/link";

import { DemoWalkthrough } from "@/components/demo-walkthrough";
import { SeverityBadge } from "@/components/severity-badge";
import { CARD, Tile } from "@/components/tiles";
import { count, plural } from "@/lib/format";
import type { MetricView, OverviewData, Row } from "@/lib/overview";
import { cn } from "@/lib/utils";

const MUTED = "text-slate-600 dark:text-slate-400";

function Panel({ title, rows, children }: { title: string; rows: Row[]; children?: React.ReactNode }) {
  return (
    <section aria-label={title} className={cn(CARD, "p-4")}>
      <h2 className="text-sm font-semibold">{title}</h2>
      {children}
      <dl className="mt-2 space-y-1.5 text-sm">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex justify-between gap-2">
              <dt>{row.href ? <Link href={row.href} className="text-indigo-700 underline dark:text-indigo-300">{row.label}</Link> : row.label}</dt>
              <dd className="font-medium tabular-nums">{row.value}</dd>
            </div>
            {row.note && <p className={cn("text-xs", MUTED)}>{row.note}</p>}
          </div>
        ))}
      </dl>
    </section>
  );
}

function MetricCard({ m }: { m: MetricView }) {
  return (
    <div role="group" aria-label={m.name} className={cn(CARD, "p-4")}>
      <div className="flex items-center justify-between gap-2">
        <p className={cn("text-sm", MUTED)}>{m.name}</p>
        {m.meets !== null && (
          <SeverityBadge tone={m.meets ? "pass" : "error"} label={m.meets ? "Meets target" : "Below target"} />
        )}
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{m.value}</p>
      <p className={cn("text-xs tabular-nums", MUTED)}>{m.target}. {m.context}</p>
    </div>
  );
}

export function Overview({ data: d }: { data: OverviewData }) {
  const sources = d.bySource.map((s) => `${s.label} ${s.value}`).join(", ");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">How many real people are in this book, and how sure are we?</h1>
        <p className="mt-1 text-sm tabular-nums">
          {d.recordsIn} records became <strong>{d.people} people</strong> in {d.households} households.
        </p>
        <p className={cn("text-xs tabular-nums", MUTED)}>
          Run {d.runId}, as of {d.asOf}, engine {d.engine}. Synthetic data only; no full MBI is shown.
        </p>
        <p className={cn("text-xs", MUTED)}>{d.identifierContext}</p>
      </header>
      <DemoWalkthrough />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <div className="col-span-2 lg:col-span-1">
          <Tile label="Records in" value={d.recordsIn} context={`${sources}, including ${count(d.unidentifiable)} unidentifiable`} />
        </div>
        <Tile label="People out" value={d.people} context={`${count(d.leftSplit)} may still be split, see the review queue`} />
        <Tile label="Households" value={d.households} context="Linked by the agency's own household ids" />
        <Tile label="Unidentifiable rows" tone="warning" value={count(d.unidentifiable)} context="No name, birth date, or MBI. Set aside." />
        <Tile label="Review queue" tone="info" value={count(d.queueSize)} context="Pairs a person should decide" />
      </div>
      <section aria-labelledby="sure-heading" className="space-y-2">
        <h2 id="sure-heading" className="text-sm font-semibold">How sure are we? Measured on synthetic data</h2>
        <p className={cn("text-xs", MUTED)}>
          These demo fixtures were used while building the rules. They are not held out and do not measure accuracy on real agency files.
        </p>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {d.metrics.map((m) => <MetricCard key={m.name} m={m} />)}
        </div>
      </section>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <Panel title="Review status" rows={d.reviewStatus} />
        <Panel title="Merges by tier" rows={d.tiers} />
        <Panel title={`Review queue: ${plural(d.queueSize, "item")}`} rows={d.suggestions.map((s) => ({ ...s, label: `Suggests ${s.label.toLowerCase()}` }))}>
          <p className="mt-2 flex flex-wrap gap-2 text-sm tabular-nums">
            {d.severity.map((s) => (
              <span key={s.severity} className="inline-flex items-center gap-1">
                <SeverityBadge tone={s.severity === "high" ? "error" : "warning"} label={s.severity === "high" ? "High" : "Medium"} />
                {count(s.count)}
              </span>
            ))}
          </p>
        </Panel>
        <Panel title="Cost and run time" rows={[...d.usage, d.runTime]} />
      </div>
    </div>
  );
}
