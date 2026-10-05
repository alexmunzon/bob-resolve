import { readFile } from "node:fs/promises";
import path from "node:path";

import { FILE_NAMES, parseRun, type Run, type RunFiles } from "@/lib/run-loader";

// Server only: reads a run folder from disk. Every page calls this at build time for the
// committed demo run. Parsing lives in run-loader, so any run is checked the same way.
export const DEMO_RUN_DIR = path.join(process.cwd(), "public", "demo-run");

async function read(dir: string, name: string): Promise<string> {
  try {
    return await readFile(path.join(dir, name), "utf8");
  } catch {
    throw new Error(`Could not read ${name} in ${dir}`);
  }
}

export async function loadRunDir(dir: string): Promise<Run> {
  const entries = await Promise.all(
    Object.entries(FILE_NAMES).map(async ([key, name]) => [key, await read(dir, name)] as const),
  );
  return parseRun(Object.fromEntries(entries) as RunFiles);
}

// One parse per build worker: every cluster page reads the same demo run, so it is loaded once.
let demo: Promise<Run> | undefined;
export function loadDemoRun(): Promise<Run> {
  demo ??= loadRunDir(DEMO_RUN_DIR);
  return demo;
}
