import { describe, expect, it } from "vitest";
import { parseDraft, workflowCases, type WorkflowDraft, type WorkflowEvent } from "../broker-workflow";

export const context: WorkflowDraft = { schema_version: "1.0.0", data_kind: "synthetic", agency_id: "agency", intake_run_id: "intake", run_id: "parent", queue_sha256: "a".repeat(64), base_hash: "b".repeat(64), identities: { "rq-1": ["opaque-id"] }, history: [], events: [] };
const action = (kind: WorkflowEvent["kind"], extra = {}): WorkflowEvent => ({ event_id: kind, item_id: "rq-1", kind, actor: "Synthetic", at: "2026-10-07T12:00:00Z", text: "Synthetic evidence", ...extra });
const parse = (events: WorkflowEvent[]) => parseDraft(JSON.stringify({ ...context, events }), context);
describe("broker workflow", () => {
  it("keeps evidence open after decisions and responses; acceptance is separate", () => {
    const events = [action("request"), action("decision", { decision: "same_person" }), action("response", { request_id: "request", provenance: { source_file: "fixture.json", sha256: "c".repeat(64), row_number: 1, received_at: "2026-10-07T12:00:00Z" } })];
    expect(workflowCases(parse(events))["rq-1"].status).toBe("needs_evidence");
    events.push(action("accept", { request_id: "request", response_id: "response" }));
    expect(workflowCases(parse(events))["rq-1"].status).toBe("evidence_reviewed");
    expect(() => parse([...events, action("accept", { event_id: "again", request_id: "request", response_id: "response" })])).toThrow(/already accepted/);
  });
  it.each(["run_id", "queue_sha256", "base_hash", "agency_id", "intake_run_id"])("rejects mismatched %s", key => {
    expect(() => parseDraft(JSON.stringify({ ...context, [key]: "c".repeat(64) }), context)).toThrow(/mismatched/);
  });
  it("rejects malformed, unknown, duplicate and missing-evidence actions", () => {
    expect(() => parseDraft("not JSON", context)).toThrow();
    expect(() => parseDraft(JSON.stringify({ ...context, extra: true }), context)).toThrow();
    expect(() => parse([action("assign"), action("assign")])).toThrow(/Duplicate/);
    expect(() => parse([action("assign", { item_id: "other" })])).toThrow();
    expect(() => parse([action("response", { request_id: "absent" })])).toThrow();
    expect(() => parse([action("accept", { request_id: "absent", response_id: "none" })])).toThrow();
    expect(() => parse([action("assign", { actor: " " })])).toThrow();
    expect(() => parse([action("decision", { decision: "merge" })])).toThrow();
  });
  it("retains child history without replaying historical events as new actions", () => {
    const child = { ...context, run_id: "child", identities: {}, history: [{ run_id: "parent", queue_sha256: context.queue_sha256, base_hash: context.base_hash, event: action("request") }] };
    expect(workflowCases(parseDraft(JSON.stringify(child)))["rq-1"].status).toBe("needs_evidence");
    expect(() => parseDraft(JSON.stringify(context), child)).toThrow();
  });
  it("only appends to browser actions and treats a repeated import as idempotent", () => {
    const edited = parse([action("request")]);
    expect(parseDraft(JSON.stringify(edited), edited)).toEqual(edited);
    expect(() => parseDraft(JSON.stringify(context), edited)).toThrow(/existing draft actions/);
    expect(() => parseDraft(JSON.stringify({ ...edited, events: [action("request", { text: "Changed" })] }), edited)).toThrow(/existing draft actions/);
    const appended = { ...edited, events: [...edited.events, action("decision", { decision: "leave_unresolved" })] };
    expect(parseDraft(JSON.stringify(appended), edited).events).toHaveLength(2);
  });
  it("preserves opaque and prototype-like IDs verbatim", () => {
    const opaque = JSON.parse(JSON.stringify(context));
    opaque.identities = JSON.parse('{"__proto__":["record:opaque / 01"],"constructor":["001"]}');
    opaque.events = [action("request", { event_id: "__proto__", item_id: "__proto__" })];
    const parsed = parseDraft(JSON.stringify(opaque));
    expect(parsed.identities["__proto__"]).toEqual(["record:opaque / 01"]);
    expect(workflowCases(parsed)["__proto__"].status).toBe("needs_evidence");
    expect(workflowCases(parsed)["constructor"].status).toBe("open");
  });
  it.each(["2026-02-29T12:00:00Z", "2026-02-31T12:00:00Z", "2026-10-07T24:00:00Z", "2026-10-07T12:00:00", "October 7, 2026T12:00:00Z", 1791374400, null])("rejects invalid calendar or non-contract timestamp %s", at => {
    expect(() => parse([action("assign", { at })])).toThrow(/timestamp/);
  });
  it.each(["2024-02-29T12:00:00Z", "2026-10-07T12:00:00.123456-05:00", "2026-10-07T12:00:00+05:30"])("accepts ISO timestamp %s", at => {
    expect(parse([action("assign", { at })]).events[0].at).toBe(at);
  });
  it.each(["request_id", "response_id", "decision", "provenance"])("rejects explicitly null optional %s", key => {
    expect(() => parse([action("assign", { [key]: null })])).toThrow();
  });
  it("rejects arrays masquerading as action or decision enums", () => {
    expect(() => parse([action("assign", { kind: ["assign"] })])).toThrow(/Unknown action/);
    expect(() => parse([action("decision", { decision: ["same_person"] })])).toThrow(/Invalid decision/);
  });
  it("rejects duplicate top-level JSON keys instead of picking the last value", () => {
    const raw = JSON.stringify(context).replace('"run_id":"parent"', '"run_id":"parent","run_id":"parent"');
    expect(() => parseDraft(raw, context)).toThrow(/Duplicate JSON object key: run_id/);
  });
  it("detects escaped keys that decode to the same name", () => {
    const raw = JSON.stringify(context).replace('"run_id":"parent"', '"run_id":"parent","run\\u005fid":"parent"');
    expect(() => parseDraft(raw, context)).toThrow(/Duplicate JSON object key: run_id/);
  });
  it("rejects duplicate fields in nested event objects", () => {
    const raw = JSON.stringify({ ...context, events: [action("assign")] }).replace('"actor":"Synthetic"', '"actor":"Synthetic","actor":"Synthetic"');
    expect(() => parseDraft(raw, context)).toThrow(/Duplicate JSON object key: actor/);
  });
});

it("accepts the real Python export and reproduces its open-evidence result", async () => {
  const fs = await import("node:fs/promises");
  const base = parseDraft(await fs.readFile("../docs/broker-workflow/context.json", "utf8"));
  const draft = parseDraft(await fs.readFile("../docs/broker-workflow/draft.json", "utf8"), base);
  const cases = workflowCases(draft);
  const expected = JSON.parse(await fs.readFile("../docs/broker-workflow/expected-ledger.json", "utf8"));
  for (const [key, c] of Object.entries(cases)) {
    expect(c.status).toBe(expected.cases[key].status);
    expect(c.owner ?? null).toBe(expected.cases[key].owner);
    expect(c.decision ?? null).toBe(expected.cases[key].decision);
  }
});
