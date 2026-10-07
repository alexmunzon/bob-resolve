import Link from "next/link";

import type { ClusterView } from "@/lib/clusters";

// A household as a small graph: people as nodes, a line from this person to each other member
// labeled with how they are linked. The run has no relationship field yet (Jev's household role
// comes later), so every line says "same household". Plain SVG, no chart library. The list below
// it says the same thing in text, for screen readers and narrow screens.

const LINK = "same household";

export function HouseholdGraph({ household }: { household: ClusterView["household"] }) {
  const nodes = household.members;
  const center = nodes.findIndex((n) => n.current);
  const others = nodes.filter((_, i) => i !== center);
  // This person on the left, the others stacked on the right, so no label sits on a line.
  const W = 460;
  const H = Math.max(110, 80 * others.length + 40);
  const at = (i: number) => ({ x: 320, y: (H / (others.length + 1)) * (i + 1) });
  const me = { x: 70, y: H / 2 };
  const summary =
    others.length === 0
      ? "Only this person is in the household."
      : `This person shares a household with ${others.map((n) => n.label).join(", ")}.`;
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="hh-title hh-desc" className="h-auto w-full max-w-md">
        <title id="hh-title">Household graph</title>
        <desc id="hh-desc">{summary}</desc>
        {others.map((n, i) => {
          const p = at(i);
          return (
            <g key={n.id}>
              <line x1={me.x} y1={me.y} x2={p.x} y2={p.y} className="stroke-[var(--muted)]" strokeWidth={1.5} />
              <text x={me.x + 0.6 * (p.x - me.x)} y={me.y + 0.6 * (p.y - me.y) - 6} textAnchor="middle" className="fill-[var(--muted)] text-[12px]">
                {LINK}
              </text>
            </g>
          );
        })}
        {[{ ...nodes[center], ...me }, ...others.map((n, i) => ({ ...n, ...at(i) }))].map((n) => (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r={10} className={n.current ? "fill-[var(--accent)] stroke-[var(--line)]" : "fill-[var(--muted)]"} />
            <text x={n.current ? n.x : n.x + 16} y={n.current ? n.y + 26 : n.y + 4} textAnchor={n.current ? "middle" : "start"} className="fill-current text-[13px]">
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <figcaption>
        <p className="text-sm">{summary}</p>
        <ul className="mt-1 list-disc pl-5 text-sm">
          {nodes.map((n) => (
            <li key={n.id}>
              {n.href ? <Link className="text-link" href={n.href}>{n.label}</Link> : n.label}
              {n.current ? " (this person)" : `: ${LINK}`}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
