import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Benchmark } from "@/components/benchmark";
import { parseBenchmark } from "@/lib/benchmark-loader";
import { benchmarkFixture } from "@/lib/__tests__/benchmark-fixture";

const value = (name: string) => screen.getByRole("row", { name: new RegExp(`^${name}`) }).querySelector("td")?.textContent;

describe("Benchmark", () => {
  it("makes the shared-identifier contribution explicit", () => {
    render(<Benchmark report={parseBenchmark(JSON.stringify(benchmarkFixture()))} />);
    expect(screen.getByText(/MBI and linking policy IDs were available to the matcher/)).toBeInTheDocument();
  });

  it("labels withheld shared identifiers without implying they contributed", () => {
    const report = benchmarkFixture();
    report.runs[0].shared_ids = false;
    render(<Benchmark report={parseBenchmark(JSON.stringify(report))} />);
    expect(screen.getByText(/MBI and linking policy IDs were withheld from matching/)).toBeInTheDocument();
    expect(screen.queryByText(/were available to the matcher/)).toBeNull();
  });

  it("leads with automatic figures and labels the suggestion figure as hypothetical", () => {
    const { container } = render(<Benchmark report={parseBenchmark(JSON.stringify(benchmarkFixture()))} />);
    expect(value("Automatic precision")).toBe("100.0%");
    expect(value("Automatic recall")).toBe("99.6%");
    expect(value("Automatic F1")).toBe("99.8%");
    expect(value("Confirmed by a reviewer")).toBe("0");
    expect(value("Awaiting review")).toBe("19");
    const hypothetical = screen.getByText(/Recall if every same-person suggestion were confirmed/).closest("p");
    expect(hypothetical).toHaveTextContent("Hypothetical, not achieved");
    expect(hypothetical).toHaveTextContent("99.6%");
    expect(screen.getByText(/Model tiers used: none \(rules only\)/)).toBeInTheDocument();
    expect(screen.getByText(/^Data:/)).toHaveTextContent(/^Data: derived from the answer key\. Used while building the rules, so not held out\.$/);
    expect(container.textContent?.match(/answer key/g)).toHaveLength(1);
    expect(screen.getAllByText(/measured on synthetic data/).length).toBeGreaterThan(0);
    expect(screen.getByRole("note")).toHaveTextContent("not accuracy on data the engine has never seen");
    expect(container.textContent).not.toMatch(/[\u2013\u2014]/);
  });

  it("shows null as Not recorded, never 0", () => {
    const report = benchmarkFixture();
    Object.assign(report.runs[0], { model_tiers_used: ["jev"], candidate_pairs: null });
    Object.assign(report.runs[0].metrics, { automatic_f1: null, human_confirmed_merges: null, recall_if_suggestions_confirmed: null });
    render(<Benchmark report={parseBenchmark(JSON.stringify(report))} />);
    expect(value("Automatic F1")).toBe("Not recorded");
    expect(value("Confirmed by a reviewer")).toBe("Not recorded");
    expect(screen.getByText(/Recall if every same-person suggestion/).closest("p")).toHaveTextContent("Not recorded");
    expect(screen.getByText(/Model tiers used: Jev/)).toBeInTheDocument();
    expect(screen.getByText(/Candidate pairs not recorded/)).toBeInTheDocument();
  });

  it("uses the run position, not the raw run id, as the heading id", () => {
    const report = benchmarkFixture();
    report.runs[0].run_id = "odd id\"<>";
    render(<Benchmark report={parseBenchmark(JSON.stringify(report))} />);
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveAttribute("id", "run-0");
    expect(heading).toHaveTextContent('Run odd id"<>');
    expect(screen.getByRole("region", { name: 'Run odd id"<>' })).toHaveAttribute("aria-labelledby", "run-0");
  });
});
