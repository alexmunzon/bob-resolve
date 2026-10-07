import { CARD } from "@/components/tiles";
import { cn } from "@/lib/utils";

// The dashboard never changes data (SPEC section 4). It explains how a reviewer records a decision.
const EXAMPLE = `{"item_id": "rq-092f3edba885", "decision": "same_person", "reviewer": "your name", "decided_at": "2026-10-05T15:00:00+00:00", "note": "optional"}`;
const COMMAND = "cd engine && uv run bob-resolve review apply --run ../runs/<id> --decisions decisions.jsonl --out ../runs --run-id <new id>";

export function HowToDecide() {
  return (
    <section aria-label="How to decide" className={cn(CARD, "decision-guide")}>
      <h2 className="section-title">How to decide</h2>
      <div className="decision-guide-layout">
        <ol className="list-decimal pl-4">
          <li>Compare the records side by side. Read the evidence and the rule for each item.</li>
          <li>
            Write one line per decided item in a file such as <code>decisions.jsonl</code>. The decision is
            <code> same_person</code> or <code>different_people</code>; skip items you are not sure about.
          </li>
          <li>Run the command below. It writes a new run; the old run is never changed.</li>
        </ol>
        <details className="technical-details min-w-0 space-y-2">
          <summary>Decision JSON and apply command</summary>
          <pre tabIndex={0} aria-label="Example decision JSON" className="code-sample">{EXAMPLE}</pre>
          <pre tabIndex={0} aria-label="Review apply command" className="code-sample">{COMMAND}</pre>
        </details>
      </div>
      <p className="mt-3 text-xs leading-relaxed muted">
        A &quot;same person&quot; decision on a pair becomes a merge with tier &quot;Human review&quot;. Other decisions
        are stored as labels. Nothing here edits data: this page only reads the run.
      </p>
    </section>
  );
}
