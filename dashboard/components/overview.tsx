import Link from "next/link";

import { DemoWalkthrough } from "@/components/demo-walkthrough";
import { PageHeader } from "@/components/page-header";
import { SeverityBadge } from "@/components/severity-badge";
import { CARD, Tile } from "@/components/tiles";
import { count } from "@/lib/format";
import type { MetricView, OverviewData, Row } from "@/lib/overview";
import { cn } from "@/lib/utils";

function Panel({ title, rows, children, heading: Heading = "h2" }: { title: string; rows: Row[]; children?: React.ReactNode; heading?: "h2" | "h4" }) {
  return (
    <section aria-label={title} className={cn(CARD, "summary-panel")}>
      <Heading className="section-title">{title}</Heading>
      {children}
      <dl className="summary-rows">
        {rows.map((row) => (
          <div key={row.label} className="summary-row">
            <div className="flex justify-between gap-2">
              <dt>{row.href ? <Link href={row.href} className="text-link">{row.label}</Link> : row.label}</dt>
              <dd className="font-medium tabular-nums">{row.value}</dd>
            </div>
            {row.note && <p className="summary-note">{row.note}</p>}
          </div>
        ))}
      </dl>
    </section>
  );
}

function MetricCard({ m }: { m: MetricView }) {
  return (
    <div role="group" aria-label={m.name} className={cn(CARD, "metric-tile")}>
      <div className="metric-label-row">
        <p className="metric-label">{m.name}</p>
        {m.meets !== null && (
          <SeverityBadge tone={m.meets ? "pass" : "error"} label={m.meets ? "Meets target" : "Below target"} />
        )}
      </div>
      <p className="metric-value">{m.value}</p>
      <p className="metric-context">{m.target}. {m.context}</p>
    </div>
  );
}

export function Overview({ data: d }: { data: OverviewData }) {
  const sources = d.bySource.map((s) => `${s.label} ${s.value}`).join(", ");
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Bob Resolve / Book of business" title="Resolve identity questions with source evidence">
        <p className="page-description tabular-nums">
          Compare the source records before deciding whether a pair is the same person. A false merge is worse than a missed match.
        </p>
        <p className="provenance tabular-nums">
          As of {d.asOf}.
        </p>
      </PageHeader>
      <section aria-labelledby="attention-heading" className="space-y-3">
        <h2 id="attention-heading" className="section-heading">Needs attention</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div role="group" aria-label="Unresolved review pairs" className={cn(CARD, "summary-panel")}>
            <h3 className="section-title">Unresolved review pairs</h3>
            <p className="kpi-value">{count(d.queueSize)}</p>
            <p className="kpi-context">Compare each pair side by side. Read the source evidence and guard rails before making a decision.</p>
            <Link href="/review" className="walkthrough-link mt-3">Compare review pairs</Link>
            <p className="mt-3 text-xs leading-relaxed muted">Read-only. Apply review decisions separately to a new run; leave uncertain pairs unresolved.</p>
            <details className="technical-details mt-4">
              <summary>Review breakdown and recorded status</summary>
              <div className="space-y-3 pt-2">
                <Panel heading="h4" title="Suggestions" rows={d.suggestions.map((s) => ({ ...s, label: `Suggests ${s.label.toLowerCase()}` }))}>
                  <p className="mt-2 flex flex-wrap gap-2 text-sm tabular-nums">
                    {d.severity.map((s) => (
                      <span key={s.severity} className="inline-flex items-center gap-1">
                        <SeverityBadge tone={s.severity === "high" ? "error" : "warning"} label={s.severity === "high" ? "High" : "Medium"} />
                        {count(s.count)}
                      </span>
                    ))}
                  </p>
                </Panel>
                <Panel heading="h4" title="Recorded review status" rows={d.reviewStatus}>
                  <p className="mt-2 text-xs leading-relaxed muted">Browser review labels are unauthenticated declarations, not validated resolution evidence or approval.</p>
                </Panel>
              </div>
            </details>
          </div>
          <div role="group" aria-label="Unidentifiable rows" className={cn(CARD, "summary-panel")}>
            <h3 className="section-title">Unidentifiable rows</h3>
            <p className="kpi-value">{count(d.unidentifiable)}</p>
            <p className="kpi-context">No name, birth date, or MBI. Set aside from identity grouping.</p>
            <p className="mt-3 text-sm">Ask the source owner to restore identity fields before rerunning these rows.</p>
          </div>
        </div>
      </section>
      <div className="overview-counts">
        <Tile label="Records in" value={d.recordsIn} context={`${sources}, including ${count(d.unidentifiable)} unidentifiable`} />
        <Tile label="Candidate identity groups" value={d.people} context="Engine output, not a count of human-confirmed identities." />
        <Tile label="Households" value={d.households} context="Linked by the agency's own household ids" />
      </div>
      <p className="text-sm leading-relaxed">
        <Link href="/clusters" className="text-link">Inspect grouped source records</Link> to see where each field came from and why records were combined.
      </p>
      <DemoWalkthrough />
      <section aria-label="Benchmark and limitations" className="space-y-2">
        <details className="technical-details">
          <summary>Benchmark and engine details</summary>
          <div className="space-y-4 pt-2">
            <p className="disclosure-note">These demo fixtures were used while building the rules. They are not held out and do not measure accuracy on real agency files.</p>
            <p className="text-xs leading-relaxed muted">{d.identifierContext}</p>
            <p className="text-xs leading-relaxed muted">Real agency data and production access remain separate gates.</p>
            <p className="text-xs leading-relaxed muted">Run {d.runId}, engine {d.engine}. {count(d.leftSplit)} identities left split, measured on synthetic data.</p>
            <section aria-labelledby="sure-heading" className="space-y-2">
              <h2 id="sure-heading" className="section-heading">How sure are we? Measured on synthetic data</h2>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                {d.metrics.map((m) => <MetricCard key={m.name} m={m} />)}
              </div>
            </section>
            <div className="grid gap-3 md:grid-cols-2">
              <Panel title="Merges by tier" rows={d.tiers} />
              <Panel title="Cost and run time" rows={[...d.usage, d.runTime]} />
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}
