"use client";

import { useRef, useState } from "react";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { parseDraft, workflowCases, type WorkflowDraft, type WorkflowEvent } from "@/lib/broker-workflow";

export function BrokerWorkflow() {
  const [draft, setDraft] = useState<WorkflowDraft>();
  const currentDraft = useRef<WorkflowDraft>(undefined);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pasted, setPasted] = useState("");
  const [item, setItem] = useState("");
  const [kind, setKind] = useState<WorkflowEvent["kind"]>("assign");
  const cases = draft ? workflowCases(draft) : {};
  function saveDraft(next: WorkflowDraft) {
    currentDraft.current = next;
    setDraft(next);
  }
  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : "Unable to read workflow");
    setNotice("");
  }
  function importText(raw: string, context: boolean) {
    if (context && currentDraft.current) throw new Error("A context is already loaded; reload to start another context");
    if (!context && !currentDraft.current) throw new Error("Load a CLI context first");
    const parsed = parseDraft(raw, context ? undefined : currentDraft.current);
    if (context && parsed.events.length) throw new Error("Load the CLI context with no new events first");
    saveDraft(parsed); setItem(Object.keys(parsed.identities)[0] ?? ""); setError(""); setNotice("Loaded into browser memory only.");
  }
  async function load(file: File | undefined, context: boolean) {
    if (!file) return;
    try {
      if (file.size > 5_000_000) throw new Error("Workflow file exceeds 5 MB");
      importText(await file.text(), context);
    } catch (e) { fail(e); }
  }
  function record(form: FormData) {
    const latest = currentDraft.current;
    if (!latest) return;
    const at = new Date().toISOString();
    const e: WorkflowEvent = { event_id: crypto.randomUUID(), item_id: item, kind, actor: String(form.get("actor")), at, text: String(form.get("text")) };
    if (kind === "decision") e.decision = String(form.get("decision")) as WorkflowEvent["decision"];
    if (kind === "response" || kind === "accept") e.request_id = String(form.get("request"));
    if (kind === "accept") e.response_id = String(form.get("response"));
    if (kind === "response") e.provenance = { source_file: String(form.get("source")), sha256: String(form.get("hash")), row_number: Number(form.get("row")), received_at: String(form.get("received")) };
    try { saveDraft(parseDraft(JSON.stringify({ ...latest, events: [...latest.events, e] }), latest)); setError(""); setNotice("Action added to the browser draft. Export to keep it."); }
    catch (err) { fail(err); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(currentDraft.current, null, 2) + "\n"], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "broker-workflow-draft.json"; a.click(); URL.revokeObjectURL(url);
  }
  return <section className="page-stack broker-workflow">
    <p>Synthetic data only. Browser-local draft in memory; reload clears it. Nothing is sent to a broker. Reviewer and owner names are unauthenticated declarations.</p>
    <p>Decisions do not merge people or resolve missing evidence. Accepting a response records an evidence review; identity remains unresolved until a separately verified matching run.</p>
    <p>Export a context with <code>uv run python -m bob_resolve.broker_workflow export --help</code>, then load it below. File hashes establish consistency, not authenticity.</p>
    <label>Load CLI context <input type="file" accept=".json" disabled={!!draft} onChange={e => { void load(e.target.files?.[0], true); e.target.value = ""; }} /></label>
    <details><summary>Paste context or draft JSON</summary><label>Workflow JSON <textarea style={{ width: "100%", minHeight: 100 }} value={pasted} onChange={e => setPasted(e.target.value)} /></label><button type="button" onClick={() => { try { importText(pasted, !currentDraft.current); } catch (e) { fail(e); } }}>Import pasted JSON</button></details>
    {draft && <>
      <p style={{ overflowWrap: "anywhere" }}>Agency: {draft.agency_id}. Intake run: {draft.intake_run_id}. Run: {draft.run_id}. {draft.history.length} saved events; {draft.events.length} draft events.</p>
      <details className="technical-details"><summary>Queue integrity reference</summary><p style={{ overflowWrap: "anywhere" }}>Queue SHA-256: {draft.queue_sha256}</p></details>
      <label>Import draft for this context <input type="file" accept=".json" onChange={e => { void load(e.target.files?.[0], false); e.target.value = ""; }} /></label>
      <p>Draft imports must preserve all current actions in order. Reimporting the same draft keeps the existing actions; an older or changed draft is refused.</p>
      <button type="button" onClick={download}>Export draft</button>
      <form action={record} className="page-stack">
        <label>Case <select value={item} onChange={e => setItem(e.target.value)}>{Object.keys(draft.identities).map(id => <option key={id} value={id}>{id}</option>)}</select></label>
        <label>Action <select value={kind} onChange={e => setKind(e.target.value as WorkflowEvent["kind"])}><option value="assign">Assign owner</option><option value="request">Request missing evidence</option><option value="response">Record response</option><option value="accept">Accept evidence response</option><option value="decision">Record decision</option></select></label>
        <label>Reviewer name (unauthenticated) <input name="actor" required /></label>
        <label>{kind === "assign" ? "Owner name (unauthenticated)" : "Reason / requested evidence / response summary"} <input name="text" required /></label>
        {(kind === "response" || kind === "accept") && <label>Request ID <input name="request" required /></label>}
        {kind === "accept" && <label>Response ID <input name="response" required /></label>}
        {kind === "response" && <>
          <label>Source file reference <input name="source" required /></label>
          <label>Source SHA-256 (declared) <input name="hash" required pattern="[a-f0-9]{64}" /></label>
          <label>Source row <input name="row" type="number" min="1" required /></label>
          <label>Received at (ISO time with timezone) <input name="received" placeholder="2026-10-07T12:00:00Z" required /></label>
        </>}
        {kind === "decision" && <label>Decision <select name="decision"><option value="leave_unresolved">Leave unresolved</option><option value="same_person">Same person (label only)</option><option value="different_people">Different people (label only)</option></select></label>}
        <button disabled={!item} type="submit">Add action to draft</button>
      </form>
      {Object.entries(cases).map(([id, c]) => <article key={id} style={{ overflowWrap: "anywhere" }}>
        <h2>{id}</h2><p>Identity: unresolved. Evidence: {c.status}. Owner: {c.owner ?? "Unassigned"}. Decision: {c.decision ?? "Not recorded"}.</p>
        <p>Source record IDs: {draft.identities[id]?.join(", ") ?? "Historical case outside the current queue"}.</p>
        {Object.entries(c.requests).map(([rid, r]) => <div key={rid}><p>Request {rid}: {r.text}. {r.accepted ? `Evidence accepted: ${r.accepted}` : "Still open"}.</p>{Object.entries(r.responses).map(([eid, e]) => <p key={eid}>Response {eid}: {e.text}. Source: {e.provenance?.source_file}, row {e.provenance?.row_number}; SHA-256 (declared): {e.provenance?.sha256}; received {e.provenance?.received_at}; recorded by {e.actor} (unauthenticated).</p>)}</div>)}
      </article>)}
      <details><summary>Bound event history and draft events</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify({ history: draft.history, events: draft.events }, null, 2)}</pre></details>
      <p>Apply the export with <code>uv run python -m bob_resolve.broker_workflow apply --run PARENT --draft FILE --out NEW_CHILD --agency-id AGENCY --intake-run-id INTAKE</code>. The CLI checks the parent and saves an immutable child. No identity changes are applied.</p>
    </>}
    {error && <p role="alert" className="workflow-notice status-error"><TriangleAlert aria-hidden size={18} />Error: {error}</p>}{notice && <p role="status" className="workflow-notice status-pass"><CircleCheck aria-hidden size={18} />Confirmed: {notice}</p>}
  </section>;
}
