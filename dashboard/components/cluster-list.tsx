import { CARD } from "@/components/tiles";
import { PageHeader } from "@/components/page-header";
import type { clusterList } from "@/lib/clusters";
import { count } from "@/lib/format";
import { cn } from "@/lib/utils";

type Entry = ReturnType<typeof clusterList>[number];

// Plain links, not next/link: about 1,600 of them would each add client props and a prefetch.
// Styles sit on the list, not on each item, to keep the page small.
function Links({ items }: { items: Entry[] }) {
  return (
    <ul className="cluster-links">
      {items.map((c) => (
        <li key={c.personId}>
          <a href={c.href}>{c.name}</a>{" "}
          <span>({c.records} records{c.aliases.length ? `, alias ${c.aliases.join(", ")}` : ""})</span>
        </li>
      ))}
    </ul>
  );
}

export function ClusterList({ items }: { items: Entry[] }) {
  const groups = [
    { title: "Duplicate CRM clients merged into one person", items: items.filter((c) => c.duplicateClient) },
    { title: "Nicknames kept as aliases", items: items.filter((c) => c.aliases.length > 0) },
  ];
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Bob Resolve / Person clusters" title="Why did these records become one person?">
        <p className="page-description">
          {count(items.length)} people are made of two or more records. Open one to see its golden record, the source
          of every field, the member records side by side, its merge log lines, and its household.
        </p>
        <p className="provenance">Synthetic data only; no full MBI is shown.</p>
      </PageHeader>
      {groups.map((g) => (
        <section key={g.title} aria-label={g.title} className={cn(CARD, "table-panel")}>
          <h2 className="section-title">{g.title} ({count(g.items.length)})</h2>
          <Links items={g.items} />
        </section>
      ))}
      <details className={cn(CARD, "table-panel")}>
        <summary className="cursor-pointer section-title">Every person with two or more records ({count(items.length)})</summary>
        <Links items={items} />
      </details>
    </div>
  );
}
