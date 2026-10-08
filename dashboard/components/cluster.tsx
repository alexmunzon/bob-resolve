import { HouseholdGraph } from "@/components/household-graph";
import { PageHeader } from "@/components/page-header";
import { CARD } from "@/components/tiles";
import type { ClusterView } from "@/lib/clusters";
import { ruleName, sourceLabel, tierLabel } from "@/lib/explain";
import { fixed } from "@/lib/format";
import type { Member } from "@/lib/run-loader";
import { cn } from "@/lib/utils";

const MUTED = "muted";
const TH = "text-left whitespace-nowrap";
const TD = "align-top";

const MEMBER_ROWS: [string, (m: Member) => string | null][] = [
  ["First name", (m) => m.first_name],
  ["Last name", (m) => m.last_name],
  ["Birth date", (m) => m.dob],
  ["MBI (last 4 only)", (m) => m.mbi_masked],
  ["Street", (m) => m.address_line1],
  ["City", (m) => m.city],
  ["State", (m) => m.state],
  ["ZIP", (m) => m.zip],
  ["Phone", (m) => m.phone],
  ["Email", (m) => m.email],
  ["Source", (m) => `${m.source_file}, row ${m.row_number}`],
  ["Active policy", (m) => (m.active_policy ? "Yes" : "No")],
];

function Section({ title, children, table = true }: { title: string; children: React.ReactNode; table?: boolean }) {
  return (
    <section aria-label={title} className={cn(CARD, "table-panel")}>
      <h2 className="section-title">{title}</h2>
      {table
        ? <div className="table-scroll" role="region" aria-label={`${title} table`} tabIndex={0}>{children}</div>
        : children}
    </section>
  );
}

export function Cluster({ view: v }: { view: ClusterView }) {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Bob Resolve / Record provenance" title="Why did these records become one person?">
        <p className="page-description break-words">
          <strong>{v.name}</strong> is {v.recordIds.length} records: {v.recordIds.join(", ")}.
        </p>
        <p className="provenance">
          Aliases: {v.aliases.length ? v.aliases.join(", ") : "none"}.
        </p>
        <p className="provenance">Candidate identity group. A deterministic match does not confirm a person.</p>
      </PageHeader>

      <Section title="Golden record">
        <table className="data-table provenance-table">
          <thead className={MUTED}>
            <tr><th className={TH}>Field</th><th className={TH}>Value</th><th className={TH}>Taken from</th><th className={TH}>Why</th><th className={TH}>Deciding tier</th></tr>
          </thead>
          <tbody>
            {v.golden.map((g) => (
              <tr key={g.field}>
                <th scope="row" className={TH}>{g.field}</th>
                <td className={TD}>{g.value}</td>
                <td className={TD}>{g.from}<span className={cn("block text-xs", MUTED)}>{g.where}</span></td>
                <td className={TD}>{g.why}</td>
                <td className={TD}>{g.tier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Member records side by side">
        <table className="data-table member-table">
          <thead>
            <tr>
              <th className={TH}><span className="sr-only">Field</span></th>
              {v.members.map((m) => <th key={m.record_id} scope="col" className={TH}>{sourceLabel(m.source)} {m.record_id}</th>)}
            </tr>
          </thead>
          <tbody>
            {MEMBER_ROWS.map(([label, get]) => (
              <tr key={label}>
                <th scope="row" className={cn(TH, MUTED)}>{label}</th>
                {v.members.map((m) => <td key={m.record_id} className={TD}>{get(m) ?? "Missing"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Merge log lines for this person">
        <table className="data-table provenance-table">
          <thead className={MUTED}>
            <tr><th className={TH}>Line</th><th className={TH}>Action</th><th className={TH}>Pair</th><th className={TH}>Tier</th><th className={TH}>Score</th><th className={TH}>Rule</th></tr>
          </thead>
          <tbody>
            {v.lines.map((e) => (
              <tr key={e.line} className="tabular-nums">
                <td className={TD}>{e.line}</td>
                <td className={TD}>{e.action === "merge" ? "Merged" : "Split"}</td>
                <td className={TD}>{e.a} and {e.b}</td>
                <td className={TD}>{tierLabel(e.tier)}</td>
                <td className={TD}>{fixed(e.score, 4)}</td>
                <td className={TD}>{e.rule_ids.map((r) => `${r} (${ruleName(r)})`).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Household" table={false}>
        <HouseholdGraph household={v.household} />
      </Section>
    </div>
  );
}
