import Link from "next/link";

// These examples are pinned to the committed synthetic run by the Overview tests.
const STEPS = [
  { label: "Strong match", href: "/clusters/crm-C-00083" },
  { label: "Weak match", href: "/review?rule=GR-007" },
  { label: "Conflicting pair", href: "/review?rule=GR-005" },
  { label: "Honest benchmark", href: "/benchmark" },
];

export function DemoWalkthrough() {
  return (
    <nav aria-label="Demo walkthrough" className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      <span className="font-medium">Walk the evidence:</span>
      {STEPS.map(({ label, href }) => (
        <Link key={href} href={href} className="rounded text-indigo-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-indigo-600 dark:text-indigo-300">
          {label}
        </Link>
      ))}
    </nav>
  );
}
