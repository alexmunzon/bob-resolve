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
    expect(tile("Records in").getByText("CRM 2,040, Enrollment 1,838, plus 9 unidentifiable")).toBeInTheDocument();
    expect(tile("People out").getByText(count(sc.people))).toBeInTheDocument();
    expect(tile("Households").getByText(count(sc.households))).toBeInTheDocument();
    expect(tile("Unidentifiable rows").getByText(String(sc.unidentifiable))).toBeInTheDocument();
    expect(tile("Review queue").getByText(String(sc.review_queue.size))).toBeInTheDocument();
  });

  it("labels every accuracy number as synthetic, with the side and the shared-ids mode", async () => {
    await show();
    for (const name of ["Precision of auto-merges", "Recall after review", "Blocking recall"]) {
      const group = tile(name);
      expect(group.getByText("100.0%")).toBeInTheDocument();
      expect(group.getByText("Meets target")).toBeInTheDocument();
      expect(
        group.getByText(/Enrollment side derived from the answer key, shared ids off \(MBI withheld\)\. Measured on synthetic data\./),
      ).toBeInTheDocument();
    }
    expect(tile("Precision of auto-merges").getByText(/Target at least 99\.0%/)).toBeInTheDocument();
  });

  it("shows merges by tier, with Jev, LLM, and human review off or zero and why", async () => {
    await show();
    const tiers = panel(/Merges by tier/);
    expect(tiers.getByText("2,139")).toBeInTheDocument();
    expect(tiers.getAllByText("Off")).toHaveLength(2);
    expect(tiers.getByText(/needs approval each time/)).toBeInTheDocument();
    expect(tiers.getByText(/Anthropic key and a spend cap/)).toBeInTheDocument();
    expect(tiers.getByText("No review decisions applied to this run yet.")).toBeInTheDocument();
  });

  it("splits the review queue by severity and by suggestion, in words", async () => {
    await show();
    const q = panel(/Review queue: 58 items/);
    expect(q.getByText("High")).toBeInTheDocument();
    expect(q.getByText("Medium")).toBeInTheDocument();
    expect(q.getByText("Suggests same person").nextSibling).toHaveTextContent("28");
    expect(q.getByText("Suggests different people").nextSibling).toHaveTextContent("23");
    expect(q.getByText("Suggests unsure").nextSibling).toHaveTextContent("7");
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
