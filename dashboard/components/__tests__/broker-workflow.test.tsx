import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BrokerWorkflow } from "../broker-workflow";
import { parseDraft, type WorkflowDraft } from "@/lib/broker-workflow";

const context: WorkflowDraft = { schema_version: "1.0.0", data_kind: "synthetic", agency_id: "agency", intake_run_id: "intake", run_id: "parent", queue_sha256: "a".repeat(64), base_hash: "b".repeat(64), identities: { "case:opaque/001": ["record:opaque / 01"] }, history: [], events: [] };
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function paste(draft: WorkflowDraft) {
  const disclosure = screen.getByText("Paste context or draft JSON");
  if (!disclosure.closest("details")!.open) fireEvent.click(disclosure);
  fireEvent.change(screen.getByLabelText("Workflow JSON"), { target: { value: JSON.stringify(draft) } });
  fireEvent.click(screen.getByRole("button", { name: "Import pasted JSON" }));
}
async function submit(kind: string, fields: Record<string, string>) {
  fireEvent.change(screen.getByLabelText("Action"), { target: { value: kind } });
  fireEvent.change(screen.getByLabelText("Reviewer name (unauthenticated)"), { target: { value: "Synthetic reviewer" } });
  for (const [label, value] of Object.entries(fields)) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  await act(async () => { fireEvent.submit(screen.getByRole("button", { name: "Add action to draft" }).closest("form")!); });
}
function fakeIds() {
  let id = 0;
  vi.spyOn(crypto, "randomUUID").mockImplementation(() => `00000000-0000-4000-8000-${String(++id).padStart(12, "0")}`);
}
const summary = "Reason / requested evidence / response summary";
it("discloses browser-local state and unauthenticated names before any action", () => {
  render(<BrokerWorkflow />);
  expect(screen.getByText(/Browser-local draft in memory/)).toBeVisible();
  expect(screen.getByText(/names are unauthenticated/)).toBeVisible();
  expect(screen.getByText(/Decisions do not merge people/)).toBeVisible();
  expect(screen.queryByText("Add action to draft")).not.toBeInTheDocument();
});
it("keeps invalid and oversized imports out of the editor", async () => {
  render(<BrokerWorkflow />);
  fireEvent.change(screen.getByLabelText("Load CLI context"), { target: { files: [{ size: 5, text: async () => "wrong" }] } });
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.queryByText("Add action to draft")).not.toBeInTheDocument();
  const text = vi.fn();
  fireEvent.change(screen.getByLabelText("Load CLI context"), { target: { files: [{ size: 5_000_001, text }] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("exceeds 5 MB");
  expect(text).not.toHaveBeenCalled();
  const duplicate = JSON.stringify(context).replace('"run_id":"parent"', '"run_id":"parent","run_id":"parent"');
  fireEvent.change(screen.getByLabelText("Load CLI context"), { target: { files: [{ size: duplicate.length, text: async () => duplicate }] } });
  expect(await screen.findByText(/Duplicate JSON object key: run_id/)).toHaveAttribute("role", "alert");
  expect(screen.queryByText("Add action to draft")).not.toBeInTheDocument();
});
it("imports, assigns, requests, records provenance and exports without closing evidence on decision", async () => {
  fakeIds();
  render(<BrokerWorkflow />);
  paste(context);
  expect(screen.getByText(/Source record IDs: record:opaque \/ 01/)).toBeVisible();
  await submit("assign", { "Owner name (unauthenticated)": "Synthetic owner" });
  await submit("request", { [summary]: "Need row evidence" });
  const request = "00000000-0000-4000-8000-000000000002";
  await submit("decision", { [summary]: "Label reviewed", Decision: "same_person" });
  await submit("response", { [summary]: "Fixture evidence received", "Request ID": request, "Source file reference": "synthetic.csv", "Source SHA-256 (declared)": "c".repeat(64), "Source row": "7", "Received at (ISO time with timezone)": "2026-10-07T12:00:00-05:00" });
  expect(screen.getByText(/Evidence: needs_evidence\. Owner: Synthetic owner\. Decision: same_person/)).toBeVisible();
  expect(screen.getByText(/SHA-256 \(declared\):/)).toHaveTextContent("c".repeat(64));
  expect(screen.getByText(/Still open/)).toBeVisible();
  let exported: Blob | undefined;
  vi.stubGlobal("URL", { createObjectURL: vi.fn((blob: Blob) => { exported = blob; return "blob:workflow-test"; }), revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fireEvent.click(screen.getByRole("button", { name: "Export draft" }));
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("broker-workflow-draft.json");
  const json = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsText(exported!); });
  expect(json.endsWith("\n")).toBe(true);
  const saved = parseDraft(json, context);
  expect(saved.identities).toEqual(context.identities);
  expect(saved.events.map(e => e.kind)).toEqual(["assign", "request", "decision", "response"]);
  expect(saved.events[3].provenance).toEqual({ source_file: "synthetic.csv", sha256: "c".repeat(64), row_number: 7, received_at: "2026-10-07T12:00:00-05:00" });
  paste(saved);
  expect(screen.getByText(/4 draft events/)).toBeVisible();
  paste(context);
  expect(screen.getByRole("alert")).toHaveTextContent("preserve existing draft actions");
  expect(screen.getByText(/4 draft events/)).toBeVisible();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await submit("accept", { [summary]: "Evidence reviewed separately", "Request ID": request, "Response ID": saved.events[3].event_id });
  expect(screen.getByText(/Identity: unresolved\. Evidence: evidence_reviewed/)).toBeVisible();
  expect(screen.getByText(/Evidence accepted:/)).toHaveTextContent(saved.events[3].event_id);
  await submit("accept", { [summary]: "Repeated acceptance", "Request ID": request, "Response ID": saved.events[3].event_id });
  expect(screen.getByRole("alert")).toHaveTextContent("already accepted");
  expect(screen.getByText(/5 draft events/)).toBeVisible();
});
it("refuses mismatched and missing response actions without discarding current edits", async () => {
  fakeIds(); render(<BrokerWorkflow />); paste(context);
  await submit("request", { [summary]: "Need evidence" });
  paste({ ...context, run_id: "stale-parent" });
  expect(screen.getByRole("alert")).toHaveTextContent("mismatched");
  await submit("accept", { [summary]: "Invalid reference", "Request ID": "missing", "Response ID": "missing" });
  expect(screen.getByRole("alert")).toHaveTextContent("Missing evidence request");
  expect(screen.getByText(/1 draft events/)).toBeVisible();
});
it("validates a delayed file import against edits made while it was loading", async () => {
  fakeIds(); render(<BrokerWorkflow />); paste(context);
  let finish: (raw: string) => void = () => {};
  const pending = new Promise<string>(resolve => { finish = resolve; });
  fireEvent.change(screen.getByLabelText("Import draft for this context"), { target: { files: [{ size: 100, text: () => pending }] } });
  await submit("request", { [summary]: "Keep this browser action" });
  await act(async () => { finish(JSON.stringify(context)); await pending; });
  expect(screen.getByRole("alert")).toHaveTextContent("preserve existing draft actions");
  expect(screen.getByText(/Keep this browser action/, { selector: "p" })).toBeVisible();
  expect(screen.getByText(/1 draft events/)).toBeVisible();
});
it("refuses context JSON that already contains actions", () => {
  render(<BrokerWorkflow />);
  paste({ ...context, events: [{ event_id: "event", item_id: "case:opaque/001", kind: "assign", actor: "Synthetic", at: "2026-10-07T12:00:00Z", text: "Owner" }] });
  expect(screen.getByRole("alert")).toHaveTextContent("no new events first");
  expect(screen.queryByText("Add action to draft")).not.toBeInTheDocument();
});
it("keeps whitespace in an opaque case ID when selecting and recording actions", async () => {
  fakeIds(); render(<BrokerWorkflow />);
  const opaque = { ...context, identities: { ...context.identities, " case  /002 ": [" record:002 "] } };
  paste(opaque);
  fireEvent.change(screen.getByLabelText("Case"), { target: { value: " case  /002 " } });
  expect(screen.getByLabelText("Case")).toHaveValue(" case  /002 ");
  await submit("request", { [summary]: "Preserve exact case ID" });
  const history = screen.getByText(/"events": \[/, { selector: "pre" });
  expect(JSON.parse(history.textContent!).events[0].item_id).toBe(" case  /002 ");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
it("keeps the first loaded context when a previous file read completes later", async () => {
  render(<BrokerWorkflow />);
  let finish: (raw: string) => void = () => {};
  const pending = new Promise<string>(resolve => { finish = resolve; });
  fireEvent.change(screen.getByLabelText("Load CLI context"), { target: { files: [{ size: 100, text: () => pending }] } });
  paste(context);
  await act(async () => { finish(JSON.stringify({ ...context, run_id: "different-parent" })); await pending; });
  expect(screen.getByRole("alert")).toHaveTextContent("context is already loaded");
  expect(screen.getByText(/Run: parent\./)).toBeVisible();
  expect(screen.getByLabelText("Load CLI context")).toBeDisabled();
});

it("discloses technical integrity metadata while keeping the unresolved state and source IDs visible", () => {
  render(<BrokerWorkflow />);
  paste(context);
  const summary = screen.getByText("Queue integrity reference");
  const details = summary.closest("details")!;
  expect(details).not.toHaveAttribute("open");
  summary.focus();
  expect(summary).toHaveFocus();
  expect(screen.getByText(/Identity: unresolved/)).toBeVisible();
  expect(screen.getByText(/Source record IDs:/)).toBeVisible();
  expect(screen.getByLabelText("Load CLI context")).toBeDisabled();
  fireEvent.click(summary);
  expect(details).toHaveAttribute("open");
  expect(screen.getByText(/Queue SHA-256:/)).toHaveTextContent(context.queue_sha256);
  fireEvent.click(summary);
  expect(details).not.toHaveAttribute("open");
  expect(screen.getByText(/Identity: unresolved/)).toBeVisible();
});
