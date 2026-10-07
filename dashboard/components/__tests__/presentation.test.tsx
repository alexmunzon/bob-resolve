import { readFile } from "node:fs/promises";
import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";
import { Benchmark } from "@/components/benchmark";
import { Cluster } from "@/components/cluster";
import { ClusterList } from "@/components/cluster-list";
import { HowToDecide } from "@/components/how-to-decide";
import { Overview } from "@/components/overview";
import { ReviewQueue } from "@/components/review-queue";
import { benchmarkFixture } from "@/lib/__tests__/benchmark-fixture";
import { parseBenchmark } from "@/lib/benchmark-loader";
import { clusterList, clusterView } from "@/lib/clusters";
import { overview } from "@/lib/overview";
import { reviewItems } from "@/lib/review";
import { loadDemoRun } from "@/lib/run-dir";

vi.mock("next/navigation", () => ({ usePathname: () => "/review" }));

describe("Executive presentation and access", () => {
  it("provides a keyboard skip link to a named, focusable main surface", () => {
    const doc = new DOMParser().parseFromString(renderToStaticMarkup(
      <RootLayout params={Promise.resolve({})}>page</RootLayout>,
    ), "text/html");
    expect(doc.querySelector(".skip-link")?.getAttribute("href")).toBe("#main-content");
    expect(doc.querySelector("main")?.getAttribute("id")).toBe("main-content");
    expect(doc.querySelector("main")?.getAttribute("tabindex")).toBe("-1");
    expect(doc.querySelector("aside")?.classList).toContain("app-sidebar");
    expect(doc.querySelector("main")?.classList).toContain("app-main");
    expect(doc.querySelector(".sidebar-note")?.textContent).toBe("Separate synthetic identity evidence. Review decisions require human evidence.");
    expect(doc.querySelector(".sidebar-note")?.className).not.toMatch(/hidden/);
  });

  it("uses a consistent page hierarchy without dropping provenance", async () => {
    const run = await loadDemoRun();
    const pages = [
      <Overview key="overview" data={overview(run)} />,
      <ClusterList key="clusters" items={clusterList(run)} />,
      <Cluster key="person" view={clusterView(run, "person:crm:C-00023")!} />,
      <Benchmark key="benchmark" report={parseBenchmark(JSON.stringify(benchmarkFixture()))} />,
    ];
    for (const page of pages) {
      const view = render(page);
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(view.container.querySelector(".page-header .eyebrow")).not.toBeNull();
      expect(view.container.textContent).toMatch(/synthetic/i);
      view.unmount();
    }
  });

  it("keeps all decision instructions and the read-only caveat visible", () => {
    const view = render(<HowToDecide />);
    const help = screen.getByRole("region", { name: "How to decide" });
    expect(help.querySelector("details")).toBeNull();
    expect(within(help).getByRole("heading", { name: "How to decide" })).toBeVisible();
    expect(within(help).getAllByRole("listitem")).toHaveLength(3);
    expect(within(help).getByText(/bob-resolve review apply --run/)).toBeInTheDocument();
    expect(within(help).getByText(/The decision is/)).toHaveTextContent("different_people");
    expect(within(help).getByText(/Nothing here edits data/)).toBeVisible();
    expect(view.container.querySelector(".decision-guide-layout")).not.toBeNull();
  });

  it("makes wide evidence and provenance tables keyboard reachable", async () => {
    const run = await loadDemoRun();
    const view = render(<Cluster view={clusterView(run, "person:crm:C-00023")!} />);
    const table = screen.getByRole("region", { name: "Golden record table" });
    expect(table).toHaveAttribute("tabindex", "0");
    expect(table.classList).toContain("table-scroll");
    expect(within(table).getByRole("columnheader", { name: "Taken from" })).toBeInTheDocument();
    view.unmount();
    render(<ReviewQueue items={reviewItems(run)} />);
    const evidence = screen.getAllByRole("region", { name: /^Evidence for item / })[0];
    expect(evidence).toHaveAttribute("tabindex", "0");
    expect(evidence.classList).toContain("table-scroll");
    expect(within(evidence).getByRole("columnheader", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByLabelText("Rule")).toHaveAccessibleName("Rule");
  });

  it("defines coordinated light and dark tokens, visible focus, and bounded layout", async () => {
    const css = await readFile("app/globals.css", "utf8");
    expect(css).toContain("--paper: #F5F5F4");
    expect(css).toContain("--paper: #1C1917");
    expect(css).toContain("--sidebar: #292524");
    expect(css).toContain("--ink: #292524");
    expect(css).toContain("--accent: #AF0505");
    expect(css).toContain("--accent: #FFB3AA");
    expect(css).toContain("--brand-accent: #FF2727");
    expect(css).toContain("--action: #AF0505");
    expect(css).toContain("--action-ink: #FFFFFF");
    expect(css).toContain("--nav-active: #F5F5F4");
    expect(css).toContain("--nav-active-ink: #292524");
    expect(css).toContain("max-width: 1320px");
    expect(css).toContain(":focus-visible");
    expect(css).toContain("prefers-reduced-motion");
    expect(css).not.toContain("@font-face");
  });

  it("keeps phone touch targets large and long strings inside their surfaces", async () => {
    const css = await readFile("app/globals.css", "utf8");
    const phone = css.match(/@media \(max-width: 639px\) \{([\s\S]*?)\n\}/)![1];
    for (const control of [".nav-item", ".theme-toggle", ".filter-select", ".queue-pager a", ".series-link", ".walkthrough-link"]) {
      expect(phone).toMatch(new RegExp(`${control.replaceAll(".", "\\.")}[^}]*min-height: 44px`));
    }
    expect(css).toMatch(/\.page-header-copy[^}]*overflow-wrap: anywhere/);
    expect(css).toMatch(/\.surface[^}]*min-width: 0/);
    expect(css).toMatch(/\.table-scroll[^}]*overflow-x: auto/);
    expect(css).not.toMatch(/body[^}]*overflow-x: hidden/);
  });

  it("keeps text and semantic household edges readable in both themes", async () => {
    const css = await readFile("app/globals.css", "utf8");
    const tokens = (selector: string) => Object.fromEntries(
      [...css.match(new RegExp(`${selector} \\{([^}]+)\\}`))![1].matchAll(/--([\w-]+): (#[0-9A-F]{6})/g)]
        .map((match) => [match[1], match[2]]),
    );
    const light = tokens(":root");
    const dark = { ...light, ...tokens("\\.dark") };
    const luminance = (hex: string) => {
      const rgb = [1, 3, 5].map((start) => Number.parseInt(hex.slice(start, start + 2), 16) / 255)
        .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    };
    const contrast = (a: string, b: string) => {
      const pair = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (pair[0] + 0.05) / (pair[1] + 0.05);
    };
    for (const theme of [light, dark]) {
      expect(contrast(theme.ink, theme.panel)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.muted, theme.panel)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme.accent, theme.panel)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["action-ink"], theme.action)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["sidebar-muted"], theme.sidebar)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(theme["nav-active-ink"], theme["nav-active"])).toBeGreaterThanOrEqual(4.5);
    }
    const graph = await readFile("components/household-graph.tsx", "utf8");
    expect(graph).toContain("stroke-[var(--muted)]");
  });
});
