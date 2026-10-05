import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HowToDecide } from "@/components/how-to-decide";
import { ReviewQueue } from "@/components/review-queue";
import { RULES } from "@/lib/explain";
import { applyFilters, reviewItems } from "@/lib/review";
import { loadDemoRun } from "@/lib/run-dir";
import { expectNoMbiOrDash } from "./no-mbi";

async function show() {
  const run = await loadDemoRun();
  const items = reviewItems(run);
  render(<><HowToDecide /><ReviewQueue items={items} /></>);
  return { run, items };
}

const shown = () => within(screen.getByRole("region", { name: "Queue" })).getAllByRole("listitem", { name: /^Item / });

describe("Review queue", () => {
  it("keeps the engine's stable order: severity, then distance from the cutoff", async () => {
    const { run, items } = await show();
    expect(items.map((i) => i.id)).toEqual(run.queue.map((q) => q.item_id));
    const rank = run.queue.map((q) => [q.severity === "high" ? 0 : 1, q.cutoff_distance]);
    expect(rank).toEqual([...rank].sort((a, b) => a[0] - b[0] || a[1] - b[1]));
    expect(shown()[0]).toHaveAccessibleName(`Item 1: ${run.queue[0].item_id}`);
  });

  it("explains a GR-005 item in words: first names do not match", async () => {
    const { items } = await show();
    const gr5 = items.find((i) => i.rules.some((r) => r.id === "GR-005"))!;
    const card = screen.getByRole("listitem", { name: `Item ${gr5.position}: ${gr5.id}` });
    expect(card).toHaveTextContent(/first names do not match/i);
    expect(card).toHaveTextContent("Suggestion: Different people");
    const first = within(card).getByRole("rowheader", { name: "First name" }).closest("tr")!;
    expect(first).toHaveTextContent("Disagree");
    expect(first.querySelector("svg[aria-hidden]")).not.toBeNull();
  });

  it("shows per-field evidence as agree, disagree, or missing, in words", async () => {
    const { items } = await show();
    const card = screen.getByRole("listitem", { name: `Item 1: ${items[0].id}` });
    const row = (name: string) => within(card).getByRole("rowheader", { name }).closest("tr")!;
    expect(row("Last name")).toHaveTextContent("AgreeSame");
    expect(row("Birth date")).toHaveTextContent("Disagree");
    expect(row("Phone")).toHaveTextContent("Missing");
    expect(row("MBI (last 4 only)")).toHaveTextContent("Not compared: MBI withheld in this run");
  });

  it("explains every rule id the engine can write", () => {
    for (const id of ["GR-001", "GR-002", "GR-003", "GR-004", "GR-005", "GR-006", "GR-007", "CLUSTER_CONFLICT", "IDENTITY_CONFLICT"]) {
      expect(RULES[id].text.length).toBeGreaterThan(20);
    }
  });

  it("filters by suggestion and by rule id, in the browser", async () => {
    const { items } = await show();
    expect(shown()).toHaveLength(58);
    fireEvent.change(screen.getByLabelText("Suggestion"), { target: { value: "different_people" } });
    expect(shown()).toHaveLength(23);
    fireEvent.change(screen.getByLabelText("Rule"), { target: { value: "GR-005" } });
    expect(shown()).toHaveLength(22);
    expect(screen.getByRole("status")).toHaveTextContent("Showing 22 of 58 items");
    fireEvent.change(screen.getByLabelText("Suggestion"), { target: { value: "same_person" } });
    expect(screen.queryAllByRole("listitem", { name: /^Item / })).toHaveLength(0);
    expect(applyFilters(items, "", "SCORE-GRAY")).toHaveLength(35);
  });

  it("explains the decisions file and the apply command, and writes nothing", async () => {
    await show();
    const how = within(screen.getByRole("region", { name: "How to decide" }));
    expect(how.getByText(/bob-resolve review apply --run/)).toBeInTheDocument();
    expect(how.getByText(/"decision": "same_person"/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save|apply|merge/i })).not.toBeInTheDocument();
  });

  it("never renders an MBI-shaped value or a banned dash", async () => {
    await show();
    expectNoMbiOrDash(document.body);
  });
});
