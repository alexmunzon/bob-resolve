import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HowToDecide } from "@/components/how-to-decide";
import { ReviewQueue } from "@/components/review-queue";
import { RULES } from "@/lib/explain";
import { applyFilters, reviewItems } from "@/lib/review";
import { loadDemoRun } from "@/lib/run-dir";
import { expectNoMbiOrDash } from "./no-mbi";

async function show() {
  window.history.replaceState(null, "", "/review");
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
    expect(row("Birth date")).toHaveTextContent("AgreeSame");
    expect(row("Phone")).toHaveTextContent("Missing");
    expect(row("MBI (last 4 only)")).toHaveTextContent("Missing on at least one record");
    expect(card).toHaveTextContent(/Name and birth date only/);
  });

  it("explains the above-threshold demo pair without hiding GR-007", async () => {
    const { run } = await show();
    expect(run.queue[0].item_id).toBe("rq-19c565980cb7");
    expect(run.queue[0].pairs[0].score).toBeGreaterThan(run.manifest.thresholds!.score_high);
    const card = screen.getByRole("listitem", { name: `Item 1: ${run.queue[0].item_id}` });
    expect(card).toHaveTextContent("Score 0.998, 0.008 above the auto-match line (0.99)");
    expect(card).toHaveTextContent("Suggestion: Unsure");
    expect(card).toHaveTextContent("GR-007 Name and birth date only");
    expect(card).toHaveTextContent(/Nothing else agrees.*so a person decides/);
  });

  it.each([
    [0.98, "0.010 below the auto-match line (0.99)"],
    [0.99, "at the auto-match line (0.99)"],
    [1, "0.010 above the auto-match line (0.99)"],
    [0.2, "0.100 above the auto-reject line (0.1)"],
    [0.1, "at the auto-reject line (0.1)"],
    [0.03, "0.070 below the auto-reject line (0.1)"],
  ])("describes the displayed score %s relative to the nearest threshold", async (score, expected) => {
    const run = structuredClone(await loadDemoRun());
    run.queue[0].pairs[0].score = score;
    // Ranking distance can describe a different pair in a group. It is not this score's distance.
    run.queue[0].cutoff_distance = 0.007527;
    expect(reviewItems(run)[0].nearer).toBe(expected);
  });

  it("never says 0.000 for a score just off a line, nor 1.000 for a score below 1", async () => {
    const run = structuredClone(await loadDemoRun());
    run.queue[0].pairs[0].score = 0.9904;
    expect(reviewItems(run)[0].nearer).toBe("<0.001 above the auto-match line (0.99)");
    run.queue[0].pairs[0].score = 0.9996;
    expect(reviewItems(run)[0].score).toBe(">0.999");
  });

  it("uses the run's thresholds and retains unscored conflict explanations", async () => {
    const run = structuredClone(await loadDemoRun());
    run.manifest.thresholds = { score_high: 0.8, score_low: 0.2 };
    run.queue[0].pairs[0].score = 0.75;
    expect(reviewItems(run)[0].nearer).toBe("0.050 below the auto-match line (0.8)");
    run.queue[0].pairs = [];
    run.queue[0].rule_ids = ["IDENTITY_CONFLICT"];
    const item = reviewItems(run)[0];
    expect(item.nearer).toBe("No scored pair");
    expect(item.rules[0].text).toContain("The engine never guesses");
  });

  it("explains every rule id the engine can write", () => {
    for (const id of ["GR-001", "GR-002", "GR-003", "GR-004", "GR-005", "GR-006", "GR-007", "CLUSTER_CONFLICT", "IDENTITY_CONFLICT"]) {
      expect(RULES[id].text.length).toBeGreaterThan(20);
    }
  });

  it("filters by suggestion and by rule id, in the browser", async () => {
    const { items } = await show();
    expect(shown()).toHaveLength(19);
    fireEvent.change(screen.getByLabelText("Suggestion"), { target: { value: "different_people" } });
    expect(shown()).toHaveLength(10);
    fireEvent.change(screen.getByLabelText("Rule"), { target: { value: "GR-005" } });
    expect(shown()).toHaveLength(9);
    expect(screen.getByRole("status")).toHaveTextContent("Showing 1-9 of 9 filtered items (19 total)");
    fireEvent.change(screen.getByLabelText("Suggestion"), { target: { value: "unsure" } });
    expect(screen.queryAllByRole("listitem", { name: /^Item / })).toHaveLength(0);
    expect(applyFilters(items, "", "SCORE-GRAY")).toHaveLength(1);
  });

  it("bounds rendered items and keeps paging links bookmarkable", async () => {
    const run = await loadDemoRun();
    const source = reviewItems(run);
    const items = Array.from({ length: 61 }, (_, i) => ({
      ...source[i % source.length],
      id: `item-${i + 1}`,
      position: i + 1,
    }));
    render(<ReviewQueue items={items} />);

    expect(shown()).toHaveLength(25);
    expect(screen.getByRole("status")).toHaveTextContent("Showing 1-25 of 61 items");
    expect(screen.getByRole("link", { name: "Next page" })).toHaveAttribute("href", "/review?page=2");
    expect(screen.getByRole("link", { name: "Page 3" })).toHaveAttribute("href", "/review?page=3");
  });

  it("opens a deep-linked page and resets to page one when a filter changes", async () => {
    const run = await loadDemoRun();
    const source = reviewItems(run);
    const items = Array.from({ length: 61 }, (_, i) => ({
      ...source[i % source.length],
      id: `item-${i + 1}`,
      position: i + 1,
    }));
    window.history.replaceState(null, "", "/review?page=2&suggestion=different_people");
    render(<ReviewQueue items={items} initialPage={2} initialSuggestion="different_people" />);

    const suggestionItems = applyFilters(items, "different_people", "");
    const filteredItems = applyFilters(items, "different_people", "GR-005");
    expect(shown()[0]).toHaveAccessibleName(`Item ${suggestionItems[25].position}: ${suggestionItems[25].id}`);
    expect(screen.getByRole("status")).toHaveTextContent(`Showing 26-${Math.min(50, suggestionItems.length)} of ${suggestionItems.length} filtered items (61 total)`);
    fireEvent.change(screen.getByLabelText("Rule"), { target: { value: "GR-005" } });
    expect(shown()[0]).toHaveAccessibleName(`Item ${filteredItems[0].position}: ${filteredItems[0].id}`);
    expect(screen.getByRole("status")).toHaveTextContent(`Showing 1-${Math.min(25, filteredItems.length)} of ${filteredItems.length} filtered items (61 total)`);
    expect(window.location.search).toContain("page=1");
    expect(window.location.search).toContain("suggestion=different_people");
    expect(window.location.search).toContain("rule=GR-005");
  });

  it("clamps a page past the end, keeps the pager wrappable on phones, and names page links", async () => {
    const run = await loadDemoRun();
    const source = reviewItems(run);
    const items = Array.from({ length: 151 }, (_, i) => ({ ...source[i % source.length], id: `item-${i + 1}`, position: i + 1 }));
    render(<ReviewQueue items={items} initialPage={99} />);

    expect(screen.getByRole("status")).toHaveTextContent("Showing 151-151 of 151 items");
    const pager = screen.getByRole("navigation", { name: "Review queue pages" });
    expect(pager.className).toContain("flex-wrap");
    const current = within(pager).getByText("7");
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current).toHaveAttribute("aria-label", "Page 7");
    expect(within(pager).getByRole("link", { name: "Page 6" })).toHaveTextContent(/^6$/);
    expect(pager.querySelector("[aria-disabled]")).toBeNull();
  });

  it("says there is nothing to review when the run has no items and no filter is set", () => {
    render(<ReviewQueue items={[]} />);

    expect(screen.getByRole("status")).toHaveTextContent("No items to review");
    expect(screen.getByRole("status")).not.toHaveTextContent("filters");
    expect(screen.queryAllByRole("listitem", { name: /^Item / })).toHaveLength(0);
  });

  it("says plainly when the chosen filters match nothing", async () => {
    const { items } = await show();
    const suggestions = [...new Set(items.map((i) => i.suggestion))];
    const rules = [...new Set(items.flatMap((i) => i.rules.map((r) => r.id)))];
    const empty = suggestions.flatMap((s) => rules.map((r) => [s, r])).find(([s, r]) => applyFilters(items, s, r).length === 0);
    expect(empty).toBeDefined();
    fireEvent.change(screen.getByLabelText("Suggestion"), { target: { value: empty![0] } });
    fireEvent.change(screen.getByLabelText("Rule"), { target: { value: empty![1] } });
    expect(screen.queryAllByRole("listitem", { name: /^Item / })).toHaveLength(0);
    expect(screen.getByRole("status")).toHaveTextContent(`No items match these filters (${items.length} total)`);
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
