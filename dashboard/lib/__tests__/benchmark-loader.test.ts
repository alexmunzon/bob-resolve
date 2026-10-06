import { describe, expect, it } from "vitest";

import { parseBenchmark } from "@/lib/benchmark-loader";
import { benchmarkFixture } from "@/lib/__tests__/benchmark-fixture";

const reject = (mutate: (r: ReturnType<typeof benchmarkFixture>) => void, message: RegExp) => {
  const bad = benchmarkFixture();
  mutate(bad);
  expect(() => parseBenchmark(JSON.stringify(bad))).toThrow(message);
};

describe("parseBenchmark", () => {
  it("keeps null as null and zero as zero", () => {
    const good = benchmarkFixture();
    good.runs[0].metrics.automatic_f1 = null;
    good.runs[0].candidate_pairs = null;
    const [run] = parseBenchmark(JSON.stringify(good)).runs;
    expect(run.metrics).toMatchObject({ automatic_precision: 1, automatic_f1: null, human_confirmed_merges: 0, awaiting_review: 19 });
    expect(run).toMatchObject({ candidate_pairs: null, model_tiers_used: [] });
  });

  it("rejects malformed files with a plain message", () => {
    expect(() => parseBenchmark("{")).toThrow(/benchmark.json: not valid JSON/);
    reject((r) => { r.schema_version = 2; }, /unsupported schema_version/);
    reject((r) => { r.label = "real data"; }, /label must say measured on synthetic data/);
    reject((r) => { r.runs[0].dataset.status = "unseen"; }, /dataset.status: unknown dataset status/);
    reject((r) => { r.runs[0].model_tiers_used = ["gpt"]; }, /model_tiers_used: expected jev or llm/);
    reject((r) => { r.runs[0].metrics.automatic_precision = 1.01; }, /automatic_precision: must be a rate from 0 to 1/);
    reject((r) => { r.runs[0].metrics.awaiting_review = 1.5; }, /awaiting_review: must be a whole number/);
    reject((r) => { delete r.runs[0].metrics.automatic_f1; }, /metrics: missing automatic_f1/);
    reject((r) => { r.runs[0].metrics.precision = 1; }, /metrics: unexpected precision/);
    reject((r) => { r.runs[0].metrics.automatic_recall = "99%"; }, /expected a number or null/);
    reject((r) => { r.runs[0].dataset.status = "held_out"; }, /runs\[0\].dataset: run demo-run cannot pair side derived with status held_out/);
    reject((r) => { Object.assign(r.runs[0].dataset, { side: "hard-cases", status: "held_out" }); }, /cannot pair side hard-cases with status held_out/);
    reject((r) => { r.runs.push(structuredClone(r.runs[0])); }, /runs\[1\].run_id: run demo-run appears more than once/);
  });

  it("accepts every side and status pair the engine writes", () => {
    const pairs = [["snapshot", "snapshot"], ["derived", "derived"], ["multi-a-b", "seen"], ["multi-a-b", "held_out"], ["hard-cases", "seen"]];
    const good = benchmarkFixture();
    good.runs = pairs.map(([side, status], i) => ({ ...structuredClone(good.runs[0]), run_id: `r${i}`, dataset: { side, label: side, status } }));
    expect(parseBenchmark(JSON.stringify(good)).runs.map((r) => r.dataset.status)).toEqual(pairs.map(([, status]) => status));
  });
});
