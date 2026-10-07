import { describe, expect, it } from "vitest";

import { LLM_REPLAY_NOTE, usageTier } from "@/lib/overview";

describe("LLM tier tile", () => {
  it("says saved explanations replayed offline, never live AI, in replay mode", () => {
    const row = usageTier("LLM", { mode: "replay", calls: 0, cost_usd: 0 }, 0, "off reason", LLM_REPLAY_NOTE);
    expect(row.value).toBe("Advisory only");
    expect(row.note).toBe(LLM_REPLAY_NOTE);
    expect(row.note).toMatch(/saved explanations replayed offline/i);
    expect(row.note).toMatch(/no live calls/i);
    expect(`${row.value} ${row.note}`).not.toMatch(/live ai|ai explains/i);
  });

  it("keeps the off wording unchanged", () => {
    const row = usageTier("LLM", { mode: "off", calls: 0, cost_usd: 0 }, 0, "off reason", LLM_REPLAY_NOTE);
    expect(row).toEqual({ label: "LLM", value: "Off", note: "off reason" });
  });
});
