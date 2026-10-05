import { CARD } from "@/components/tiles";
import type { clusterList } from "@/lib/clusters";
import { count } from "@/lib/format";
import { cn } from "@/lib/utils";

type Entry = ReturnType<typeof clusterList>[number];

// Plain links, not next/link: about 1,600 of them would each add client props and a prefetch.
// Styles sit on the list, not on each item, to keep the page small.
function Links({ items }: { items: Entry[] }) {
  return (
    <ul className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3 [&_a]:text-indigo-700 [&_a]:underline dark:[&_a]:text-indigo-300 [&_span]:text-slate-600 dark:[&_span]:text-slate-400">
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
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Why did these records become one person?</h1>
        <p className="mt-1 text-sm">
          {count(items.length)} people are made of two or more records. Open one to see its golden record, the source
          of every field, the member records side by side, its merge log lines, and its household.
        </p>
      </header>
      {groups.map((g) => (
        <section key={g.title} aria-label={g.title} className={cn(CARD, "p-4")}>
          <h2 className="text-sm font-semibold">{g.title} ({count(g.items.length)})</h2>
          <Links items={g.items} />
        </section>
      ))}
      <details className={cn(CARD, "p-4")}>
        <summary className="cursor-pointer text-sm font-semibold">Every person with two or more records ({count(items.length)})</summary>
        <Links items={items} />
      </details>
    </div>
  );
}
