import { HouseholdGraph } from "@/components/household-graph";
import { CARD } from "@/components/tiles";
import type { ClusterView } from "@/lib/clusters";
import { ruleName, sourceLabel, tierLabel } from "@/lib/explain";
import type { Member } from "@/lib/run-loader";
import { cn } from "@/lib/utils";

const MUTED = "text-slate-600 dark:text-slate-400";
const TH = "px-2 py-1.5 text-left font-medium whitespace-nowrap";
const TD = "px-2 py-1.5 align-top";

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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className={cn(CARD, "p-4")}>
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-2 overflow-x-auto">{children}</div>
    </section>
  );
}

export function Cluster({ view: v }: { view: ClusterView }) {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Why did these records become one person?</h1>
        <p className="mt-1 text-sm">
          <strong>{v.name}</strong> is {v.recordIds.length} records: {v.recordIds.join(", ")}.
        </p>
        <p className={cn("text-xs", MUTED)}>
          Aliases: {v.aliases.length ? v.aliases.join(", ") : "none"}. Synthetic data only; no full MBI is shown.
        </p>
      </header>

      <Section title="Golden record">
        <table className="w-full text-sm">
          <thead className={MUTED}>
            <tr><th className={TH}>Field</th><th className={TH}>Value</th><th className={TH}>Taken from</th><th className={TH}>Why</th><th className={TH}>Deciding tier</th></tr>
          </thead>
          <tbody>
            {v.golden.map((g) => (
              <tr key={g.field} className="border-t border-slate-200 dark:border-slate-800">
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
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className={TH}><span className="sr-only">Field</span></th>
              {v.members.map((m) => <th key={m.record_id} scope="col" className={TH}>{sourceLabel(m.source)} {m.record_id}</th>)}
            </tr>
          </thead>
          <tbody>
            {MEMBER_ROWS.map(([label, get]) => (
              <tr key={label} className="border-t border-slate-200 dark:border-slate-800">
                <th scope="row" className={cn(TH, MUTED)}>{label}</th>
                {v.members.map((m) => <td key={m.record_id} className={TD}>{get(m) ?? "Missing"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Merge log lines for this person">
        <table className="w-full text-sm">
          <thead className={MUTED}>
            <tr><th className={TH}>Line</th><th className={TH}>Action</th><th className={TH}>Pair</th><th className={TH}>Tier</th><th className={TH}>Score</th><th className={TH}>Rule</th></tr>
          </thead>
          <tbody>
            {v.lines.map((e) => (
              <tr key={e.line} className="border-t border-slate-200 tabular-nums dark:border-slate-800">
                <td className={TD}>{e.line}</td>
                <td className={TD}>{e.action === "merge" ? "Merged" : "Split"}</td>
                <td className={TD}>{e.a} and {e.b}</td>
                <td className={TD}>{tierLabel(e.tier)}</td>
                <td className={TD}>{e.score.toFixed(4)}</td>
                <td className={TD}>{e.rule_ids.map((r) => `${r} (${ruleName(r)})`).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Household">
        <HouseholdGraph household={v.household} />
      </Section>
    </div>
  );
}
