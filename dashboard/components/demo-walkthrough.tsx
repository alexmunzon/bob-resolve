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
    <nav aria-label="Demo walkthrough" className="walkthrough">
      <span className="walkthrough-label">Walk the evidence:</span>
      {STEPS.map(({ label, href }, i) => (
        <Link key={href} href={href} className="walkthrough-link">
          <span aria-hidden className="walkthrough-number">{i + 1}</span>
          {label}
        </Link>
      ))}
    </nav>
  );
}
