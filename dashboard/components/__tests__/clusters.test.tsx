import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Cluster } from "@/components/cluster";
import { ClusterList } from "@/components/cluster-list";
import { clusterList, clusterPeople, clusterView, personIdOf, slugOf } from "@/lib/clusters";
import { loadDemoRun } from "@/lib/run-dir";
import { expectNoMbiOrDash, MBI_SHAPES } from "./no-mbi";

const EXAMPLE_2 = "person:crm:C-00023";

describe("Clusters", () => {
  it("builds a page for every person of two or more records, example 2 included", async () => {
    const run = await loadDemoRun();
    const people = clusterPeople(run);
    expect(people).toHaveLength(run.people.filter((p) => p.recordIds.length > 1).length);
    expect(people.map((p) => p.personId)).toContain(EXAMPLE_2);
    expect(slugOf(EXAMPLE_2)).toBe("crm-C-00023");
    expect(personIdOf("enrollment-19")).toBe("person:enrollment:19");
    expect(clusterView(run, "person:crm:nobody")).toBeNull();
  });

  it("example 2: C-02011 and C-00023 are one person, with the merge log line that joined them", async () => {
    render(<Cluster view={clusterView(await loadDemoRun(), EXAMPLE_2)!} />);
    expect(screen.getByRole("heading", { level: 1, name: "Why did these records become one person?" })).toBeInTheDocument();
    const members = within(screen.getByRole("region", { name: "Member records side by side" }));
    expect(members.getByRole("columnheader", { name: "CRM crm:C-00023" })).toBeInTheDocument();
    expect(members.getByRole("columnheader", { name: "CRM crm:C-02011" })).toBeInTheDocument();
    expect(members.getByText("Nlan")).toBeInTheDocument();
    const log = within(screen.getByRole("region", { name: "Merge log lines for this person" }));
    const row = log.getByText("crm:C-00023 and crm:C-02011").closest("tr")!;
    expect(row).toHaveTextContent("Merged");
    expect(row).toHaveTextContent("Rules (automatic)");
    expect(row).toHaveTextContent(">0.9999");
    expect(row).toHaveTextContent("AUTO-MATCH-HIGH (Automatic match)");
  });

  it("shows each golden field with its source file, row, and deciding tier", async () => {
    render(<Cluster view={clusterView(await loadDemoRun(), EXAMPLE_2)!} />);
    const golden = within(screen.getByRole("region", { name: "Golden record" }));
    const first = golden.getByRole("rowheader", { name: "First name" }).closest("tr")!;
    expect(first).toHaveTextContent("Jason");
    expect(first).toHaveTextContent(/agency-a-derived\/enrollment_clean\.csv, row \d+/);
    expect(first).toHaveTextContent("Most trusted source (enrollment over CRM)");
    expect(first).toHaveTextContent("Rules (automatic)");
  });

  it("draws the household as an accessible graph with a text list", async () => {
    const run = await loadDemoRun();
    const shared = clusterPeople(run).find((p) => run.households.some((h) => h.household_id === p.householdId && h.person_ids.length > 1))!;
    render(<Cluster view={clusterView(run, shared.personId)!} />);
    const graph = screen.getByRole("img", { name: /Household graph/ });
    expect(graph.querySelectorAll("circle").length).toBeGreaterThan(1);
    expect(within(graph).getAllByText("same household").length).toBeGreaterThan(0);
    expect(screen.getByText(/This person shares a household with/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/\(this person\)/)).toBeInTheDocument();
  });

  it("lists clusters, and no cluster page or list shows an MBI-shaped value", async () => {
    const run = await loadDemoRun();
    const items = clusterList(run);
    const { unmount } = render(<ClusterList items={items} />);
    expect(screen.getByRole("region", { name: "Duplicate CRM clients merged into one person" })).toHaveTextContent("Jason Nolan");
    expectNoMbiOrDash(document.body);
    unmount();
    for (const p of clusterPeople(run)) {
      const text = JSON.stringify(clusterView(run, p.personId));
      for (const shape of MBI_SHAPES) expect(text).not.toMatch(shape);
    }
    for (const p of clusterPeople(run).filter((p) => p.recordIds.length > 3)) {
      const view = render(<Cluster view={clusterView(run, p.personId)!} />);
      expectNoMbiOrDash(document.body);
      view.unmount();
    }
  });
});
