/** Offline declarations only. CLI verification is authoritative; names are unauthenticated. */
export interface WorkflowEvent {
  event_id: string; item_id: string; kind: "assign" | "request" | "response" | "accept" | "decision";
  actor: string; at: string; text: string; request_id?: string; response_id?: string;
  decision?: "same_person" | "different_people" | "leave_unresolved";
  provenance?: { source_file: string; sha256: string; row_number: number; received_at: string };
}
export interface WorkflowDraft {
  schema_version: "1.0.0"; data_kind: "synthetic"; agency_id: string; intake_run_id: string;
  run_id: string; queue_sha256: string; base_hash: string;
  identities: Record<string, string[]>;
  history: { run_id: string; queue_sha256: string; base_hash: string; event: WorkflowEvent }[];
  events: WorkflowEvent[];
}
export interface WorkflowCase {
  owner?: string; decision?: string; status: string;
  requests: Record<string, { text: string; responses: Record<string, WorkflowEvent>; accepted?: string }>;
}
const digest = (x: unknown): x is string => typeof x === "string" && /^[a-f0-9]{64}$/.test(x);
const text = (x: unknown): x is string => typeof x === "string" && x.trim().length > 0;
function date(x: unknown): boolean {
  if (typeof x !== "string") return false;
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/.exec(x);
  if (!parts) return false;
  const [, y, m, d, h, min, sec] = parts.map(Number);
  const zh = Number(parts[7] ?? "0"), zm = Number(parts[8] ?? "0");
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return y > 0 && m >= 1 && m <= 12 && d >= 1 && d <= days[m - 1] && h <= 23 && min <= 59 && sec <= 59 && zh <= 23 && zm <= 59 && Number.isFinite(Date.parse(x));
}
function requireValue(ok: unknown, message: string): asserts ok { if (!ok) throw new Error(message); }
function object(x: unknown): asserts x is Record<string, unknown> {
  requireValue(!!x && typeof x === "object" && !Array.isArray(x), "Expected an object");
}
function keys(x: Record<string, unknown>, allowed: string[]) {
  requireValue(Object.keys(x).every(k => allowed.includes(k)), "Unknown field");
}
function event(x: unknown): asserts x is WorkflowEvent {
  object(x);
  keys(x, ["event_id", "item_id", "kind", "actor", "at", "text", "request_id", "response_id", "decision", "provenance"]);
  for (const k of ["event_id", "item_id", "actor", "text"]) requireValue(text(x[k]), `Missing ${k}`);
  requireValue(date(x.at), "A timezone-aware timestamp is required");
  requireValue(typeof x.kind === "string" && ["assign", "request", "response", "accept", "decision"].includes(x.kind), "Unknown action");
  const allowed: Record<string, string[]> = { response: ["request_id", "provenance"], accept: ["request_id", "response_id"], decision: ["decision"] };
  for (const k of ["request_id", "response_id", "decision", "provenance"]) {
    if (k in x) requireValue(allowed[String(x.kind)]?.includes(k), "Unexpected action field");
  }
  if (x.kind === "response" || x.kind === "accept") requireValue(text(x.request_id), "Missing request");
  if (x.kind === "accept") requireValue(text(x.response_id), "Missing response");
  if (x.kind === "decision") requireValue(typeof x.decision === "string" && ["same_person", "different_people", "leave_unresolved"].includes(x.decision), "Invalid decision");
  if (x.kind === "response") {
    object(x.provenance); keys(x.provenance, ["source_file", "sha256", "row_number", "received_at"]);
    const p = x.provenance;
    requireValue(text(p.source_file) && digest(p.sha256) && Number.isInteger(p.row_number) && Number(p.row_number) > 0 && date(p.received_at), "Response requires source, SHA-256, row and received time");
  }
}
const stable = (x: unknown): string => JSON.stringify(x, (_, v) => v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : v);
/** Scan only after JSON.parse has checked syntax, keeping each object's keys separate. */
function rejectDuplicateKeys(raw: string) {
  const frames: ({ keys: Set<string>; expectsKey: boolean } | null)[] = [];
  for (let i = 0; i < raw.length; i++) {
    const char = raw[i];
    if (char === "{") frames.push({ keys: new Set(), expectsKey: true });
    else if (char === "[") frames.push(null);
    else if (char === "}" || char === "]") frames.pop();
    else if (char === "," || char === ":") {
      const frame = frames.at(-1);
      if (frame) frame.expectsKey = char === ",";
    } else if (char === '"') {
      const start = i;
      while (++i < raw.length && raw[i] !== '"') if (raw[i] === "\\") i++;
      const frame = frames.at(-1);
      if (frame?.expectsKey) {
        const key: string = JSON.parse(raw.slice(start, i + 1));
        requireValue(!frame.keys.has(key), `Duplicate JSON object key: ${key}`);
        frame.keys.add(key);
      }
    }
  }
}
export function parseDraft(raw: string, expected?: WorkflowDraft): WorkflowDraft {
  const x: unknown = JSON.parse(raw); rejectDuplicateKeys(raw); object(x);
  const fields = ["schema_version", "data_kind", "agency_id", "intake_run_id", "run_id", "queue_sha256", "base_hash", "identities", "history", "events"];
  keys(x, fields); requireValue(fields.every(k => k in x), "Missing workflow field");
  requireValue(x.schema_version === "1.0.0" && x.data_kind === "synthetic", "Unsupported version or data kind");
  for (const k of ["agency_id", "intake_run_id", "run_id"]) requireValue(text(x[k]), `Missing ${k}`);
  requireValue(digest(x.queue_sha256) && digest(x.base_hash), "Invalid hash");
  object(x.identities);
  for (const [id, ids] of Object.entries(x.identities)) requireValue(text(id) && Array.isArray(ids) && ids.every(text), "Invalid identity keys");
  requireValue(Array.isArray(x.history) && Array.isArray(x.events), "Invalid event history");
  for (const h of x.history) { object(h); keys(h, ["run_id", "queue_sha256", "base_hash", "event"]); requireValue(text(h.run_id) && digest(h.queue_sha256) && digest(h.base_hash), "Invalid historical binding"); event(h.event); }
  x.events.forEach(event);
  const draft = x as unknown as WorkflowDraft;
  if (expected) for (const k of fields.filter(k => k !== "events") as (keyof WorkflowDraft)[]) requireValue(stable(draft[k]) === stable(expected[k]), "Stale or mismatched workflow binding/history");
  if (expected) requireValue(expected.events.every((e, i) => stable(e) === stable(draft.events[i])), "Import must preserve existing draft actions; load the latest export");
  workflowCases(draft);
  return draft;
}
export function workflowCases(draft: WorkflowDraft): Record<string, WorkflowCase> {
  const cases: Record<string, WorkflowCase> = Object.fromEntries(Object.keys(draft.identities).map(k => [k, { status: "open", requests: Object.create(null) }]));
  for (const h of draft.history) if (!Object.hasOwn(cases, h.event.item_id)) Object.defineProperty(cases, h.event.item_id, { value: { status: "open", requests: Object.create(null) }, enumerable: true });
  requireValue(draft.events.every(e => Object.hasOwn(draft.identities, e.item_id)), "New action names a case outside the current queue");
  const seen = new Set<string>();
  for (const e of [...draft.history.map(h => h.event), ...draft.events]) {
    requireValue(!seen.has(e.event_id) && Object.hasOwn(cases, e.item_id), "Duplicate event or unknown case"); seen.add(e.event_id);
    const c = cases[e.item_id];
    if (e.kind === "assign") c.owner = e.text;
    if (e.kind === "decision") c.decision = e.decision;
    if (e.kind === "request") c.requests[e.event_id] = { text: e.text, responses: Object.create(null) };
    if (e.kind === "response" || e.kind === "accept") {
      requireValue(e.request_id && Object.hasOwn(c.requests, e.request_id), "Missing evidence request");
      const r = c.requests[e.request_id];
      if (e.kind === "response") r.responses[e.event_id] = e;
      else { requireValue(e.response_id && Object.hasOwn(r.responses, e.response_id) && !r.accepted, "Missing response or already accepted"); r.accepted = e.response_id; }
    }
    c.status = Object.values(c.requests).some(r => !r.accepted) ? "needs_evidence" : Object.keys(c.requests).length ? "evidence_reviewed" : "open";
  }
  return cases;
}
