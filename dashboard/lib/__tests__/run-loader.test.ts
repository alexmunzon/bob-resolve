import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { formatUsd, percent } from "@/lib/format";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import { FILE_NAMES, parseRun, splitCsvLine, type RunFiles } from "@/lib/run-loader";

async function demoFiles(): Promise<RunFiles> {
  const entries = await Promise.all(
    Object.entries(FILE_NAMES).map(async ([key, name]) => [key, await readFile(path.join(DEMO_RUN_DIR, name), "utf8")]),
  );
  return Object.fromEntries(entries) as RunFiles;
}

describe("loadRunDir", () => {
  it("loads the committed demo run and agrees with its scorecard", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    expect(run.manifest.run_id).toBe("demo-run");
    expect(run.people).toHaveLength(run.scorecard.people);
    expect(run.queue).toHaveLength(run.scorecard.review_queue.size);
    expect(run.mergeLog.merges.rules).toBe(run.scorecard.merges.auto);
    const records = run.people.reduce((n, p) => n + p.recordIds.length, 0);
    expect(records + run.scorecard.unidentifiable).toBe(run.scorecard.records_in);
  });

  it("names the file it could not read", async () => {
    await expect(loadRunDir(path.join(DEMO_RUN_DIR, "no-such-run"))).rejects.toThrow(/Could not read [a-z_]+\.(json|jsonl|csv) in /);
  });
});

describe("parseRun", () => {
  it("refuses a full MBI in people.csv or the queue", async () => {
    const files = await demoFiles();
    const people = files.people.replace("*******UD29", "1EG4TE5MK73");
    expect(() => parseRun({ ...files, people })).toThrow(/people\.csv row 1: MBI is not masked/);
    const queue = files.queue.replace(/"mbi_masked":"\*{7}([A-Z0-9]{4})"/, '"mbi_masked":"1EG4TE5$1"');
    expect(() => parseRun({ ...files, queue })).toThrow(/review_queue\.jsonl line 9: MBI is not masked/);
    const members = files.members.replace(/"mbi_masked": "\*{7}([A-Z0-9]{4})"/, '"mbi_masked": "1EG4TE5$1"');
    expect(() => parseRun({ ...files, members })).toThrow(/members\.jsonl line 1: MBI is not masked/);
    const full = files.members.replace('"person_id"', '"mbi": "1EG4TE5MK73", "person_id"');
    expect(() => parseRun({ ...files, members: full })).toThrow(/members\.jsonl line 1: a full MBI field/);
  });

  it("lists every unidentifiable record with its source file and row", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    expect(run.scorecard.unidentifiable_records).toHaveLength(run.scorecard.unidentifiable);
    expect(run.scorecard.unidentifiable_records![0]).toMatchObject({ source_file: expect.stringMatching(/\.csv$/), row_number: expect.any(Number) });
  });

  it("refuses a scorecard without the synthetic label, and files from different runs", async () => {
    const files = await demoFiles();
    const card = JSON.parse(files.scorecard);
    expect(() => parseRun({ ...files, scorecard: JSON.stringify({ ...card, label: "real" }) })).toThrow(/synthetic/);
    expect(() => parseRun({ ...files, scorecard: JSON.stringify({ ...card, people: 1 }) })).toThrow(/scorecard says 1/);
  });

  it("accepts a scorecard without resolution counts and refuses bad ones", async () => {
    const files = await demoFiles();
    const card = JSON.parse(files.scorecard);
    expect(parseRun(files).scorecard.resolution).toMatchObject({ true_pairs: 2167, found_automatically: 2159 });
    const { resolution, ...older } = card;
    expect(parseRun({ ...files, scorecard: JSON.stringify(older) }).scorecard.resolution).toBeUndefined();
    for (const bad of [{ true_pairs: "2167" }, { awaiting_review: -1 }, { found_automatically: 1.5 }, { human_confirmed_merges: null }]) {
      const scorecard = JSON.stringify({ ...card, resolution: { ...resolution, ...bad } });
      expect(() => parseRun({ ...files, scorecard })).toThrow(/scorecard\.json resolution: .* must be a whole number, 0 or more/);
    }
    const tooMany = JSON.stringify({ ...card, resolution: { ...resolution, found_automatically: 9999 } });
    expect(() => parseRun({ ...files, scorecard: tooMany })).toThrow(/more pairs found than true pairs/);
    const overSuggested = JSON.stringify({ ...card, resolution: { ...resolution, suggested_same_person: resolution.true_pairs - resolution.found_automatically + 1 } });
    expect(() => parseRun({ ...files, scorecard: overSuggested })).toThrow(/found plus suggested pairs exceed true pairs/);
    expect(() => parseRun({ ...files, scorecard: JSON.stringify({ ...card, resolution: [] }) })).toThrow(/resolution: expected an object/);
  });

  it("refuses an unknown severity and broken JSON, naming the line", async () => {
    const files = await demoFiles();
    const queue = files.queue.replace('"severity":"medium"', '"severity":"urgent"');
    expect(() => parseRun({ ...files, queue })).toThrow(/line 1: unknown severity urgent/);
    expect(() => parseRun({ ...files, mergeLog: "{oops\n" })).toThrow(/merge_log\.jsonl line 1: not valid JSON/);
  });

  it("refuses a negative or missing cost", async () => {
    const files = await demoFiles();
    const manifest = JSON.parse(files.manifest);
    manifest.jev.cost_usd = -1;
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/jev: cost_usd/);
  });
});

describe("helpers", () => {
  it("splits quoted CSV fields", () => {
    expect(splitCsvLine('a,"b, c","say ""hi""",')).toEqual(["a", "b, c", 'say "hi"', ""]);
  });

  it("formats rates and costs", () => {
    expect(percent(1)).toBe("100.0%");
    expect(percent(0.9)).toBe("90.0%");
    expect(formatUsd(0)).toBe("$0.00");
    expect(() => formatUsd(-1)).toThrow(/Not a cost/);
  });
});
