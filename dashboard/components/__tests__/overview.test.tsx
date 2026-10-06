import { readFile } from "node:fs/promises";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Overview } from "@/components/overview";
import { count } from "@/lib/format";
import { overview } from "@/lib/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

async function show() {
  const { container } = render(<Overview data={overview(await loadRunDir(DEMO_RUN_DIR))} />);
  return container;
}

const card = async () => JSON.parse(await readFile(path.join(DEMO_RUN_DIR, "scorecard.json"), "utf8"));
const tile = (label: string) => within(screen.getByRole("group", { name: label }));
const panel = (label: RegExp) => within(screen.getByRole("region", { name: label }));

describe("Overview", () => {
  it("asks the first-screen question and answers it with the scorecard numbers", async () => {
    await show();
    const sc = await card();
    expect(
      screen.getByRole("heading", { level: 1, name: "How many real people are in this book, and how sure are we?" }),
    ).toBeInTheDocument();
    expect(tile("Records in").getByText(count(sc.records_in))).toBeInTheDocument();
    expect(tile("Records in").getByText("CRM 2,040, Enrollment 1,847, including 9 unidentifiable")).toBeInTheDocument();
    expect(tile("People out").getByText(count(sc.people))).toBeInTheDocument();
    expect(tile("Households").getByText(count(sc.households))).toBeInTheDocument();
    expect(tile("Unidentifiable rows").getByText(String(sc.unidentifiable))).toBeInTheDocument();
    expect(tile("Review queue").getByText(String(sc.review_queue.size))).toBeInTheDocument();
  });

  it("labels every accuracy number as synthetic, with the side and the shared-ids mode", async () => {
    await show();
    for (const [name, value] of [["Precision of auto-merges", "100.0%"], ["Automatic recall", "99.6%"], ["Blocking recall", "100.0%"]]) {
      const group = tile(name);
      expect(group.getByText(value)).toBeInTheDocument();
      expect(
        group.getByText(/Enrollment side derived from the answer key, shared ids on\. Measured on synthetic data\./),
      ).toBeInTheDocument();
    }
    expect(tile("Precision of auto-merges").getByText("Meets target")).toBeInTheDocument();
    expect(tile("Blocking recall").getByText("Meets target")).toBeInTheDocument();
    expect(tile("Precision of auto-merges").getByText(/Target at least 99\.0%/)).toBeInTheDocument();
  });

  it("shows automatic recall from the resolution counts, with no target badge", async () => {
    await show();
    const auto = tile("Automatic recall");
    expect(auto.getByText(/2,159 of 2,167 true pairs merged with no reviewer/)).toBeInTheDocument();
    expect(auto.queryByText(/target/i)).toBeNull();
    const maybe = tile("Recall if every same-person suggestion were confirmed");
    expect(maybe.getByText("99.6%")).toBeInTheDocument();
    expect(maybe.getByText(/^Hypothetical\. Counts a same-person suggestion as found even with no reviewer\. Enrollment side/)).toBeInTheDocument();
    expect(maybe.queryByText(/target/i)).toBeNull();
  });

  it("counts reviewer-confirmed merges and links the items awaiting review", async () => {
    await show();
    const status = panel(/Review status/);
    expect(status.getByText("Confirmed by a reviewer").nextSibling).toHaveTextContent("0");
    expect(status.getByRole("link", { name: "Awaiting review" })).toHaveAttribute("href", "/review");
    expect(status.getByText("19")).toBeInTheDocument();
  });

  it("never says after review", async () => {
    expect((await show()).textContent).not.toMatch(/after review/i);
  });

  it("shows Not recorded, never the suggestion figure, when an older run has no resolution counts", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    delete run.scorecard.resolution;
    render(<Overview data={overview(run)} />);
    expect(tile("Automatic recall").getByText("Not recorded")).toBeInTheDocument();
    expect(tile("Automatic recall").queryByText("99.6%")).toBeNull();
    const status = panel(/Review status/);
    expect(status.getAllByText("Not recorded")).toHaveLength(2);
  });

  it("says there were no true pairs, not that counts are missing, when true_pairs is 0", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    run.scorecard.resolution = { ...run.scorecard.resolution!, true_pairs: 0, found_automatically: 0, suggested_same_person: 0 };
    render(<Overview data={overview(run)} />);
    const auto = tile("Automatic recall");
    expect(auto.getByText("Not recorded")).toBeInTheDocument();
    expect(auto.getByText(/^No true pairs in this run\./)).toBeInTheDocument();
    expect(auto.queryByText(/did not record resolution counts/)).toBeNull();
  });

  it("shows merges by tier, with Jev, LLM, and human review off or zero and why", async () => {
    await show();
    const tiers = panel(/Merges by tier/);
    expect(tiers.getByText("2,159")).toBeInTheDocument();
    expect(tiers.getAllByText("Off")).toHaveLength(2);
    expect(tiers.getByText(/needs approval each time/)).toBeInTheDocument();
    expect(tiers.getByText(/Anthropic key and a spend cap/)).toBeInTheDocument();
    expect(tiers.getByText("No review decisions applied to this run yet.")).toBeInTheDocument();
  });

  it("splits the review queue by severity and by suggestion, in words", async () => {
    await show();
    const q = panel(/Review queue: 19 items/);
    expect(q.getByText("High")).toBeInTheDocument();
    expect(q.getByText("Medium")).toBeInTheDocument();
    expect(q.getByText("Suggests same person").nextSibling).toHaveTextContent("0");
    expect(q.getByText("Suggests different people").nextSibling).toHaveTextContent("10");
    expect(q.getByText("Suggests unsure").nextSibling).toHaveTextContent("9");
  });

  it("shows $0 cost with Jev and the LLM off, and why there is no run time", async () => {
    await show();
    const cost = panel(/Cost and run time/);
    expect(cost.getAllByText("$0.00, 0 calls")).toHaveLength(2);
    expect(cost.getByText("Not recorded")).toBeInTheDocument();
  });

  it("never renders an MBI-shaped value or a dash the style guide bans", async () => {
    const text = (await show()).textContent ?? "";
    expect(text).not.toMatch(/\b[0-9A-Z]{4}-?[0-9A-Z]{3}-?[0-9A-Z]{4}\b/);
    expect(text).not.toMatch(/\b(?=[0-9A-Z]*\d)(?=[0-9A-Z]*[A-Z])[0-9A-Z]{11}\b/);
    expect(text).not.toMatch(/[\u2013\u2014]/);
  });
});
