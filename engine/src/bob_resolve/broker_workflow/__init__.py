"""Offline workflow ledger. Evidence review never mutates identity matching results."""

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from bob_resolve.config import PUBLIC_FOLDER_NAMES
from bob_resolve.run import RunRefused, refuse_parent_overlap, sha256

Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]


def timestamp_text(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise ValueError("A timezone-aware ISO timestamp string is required")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(timestamp_text)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(Strict):
    source_file: Text
    sha256: Digest
    row_number: Annotated[int, Field(strict=True, ge=1)]
    received_at: Timestamp


class Event(Strict):
    event_id: Text
    item_id: Text
    kind: Literal["assign", "request", "response", "accept", "decision"]
    actor: Text
    at: Timestamp
    text: Text
    request_id: Text | None = None
    response_id: Text | None = None
    provenance: Provenance | None = None
    decision: Literal["same_person", "different_people", "leave_unresolved"] | None = None

    @model_validator(mode="before")
    @classmethod
    def action_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            fields = {
                "response": {"request_id", "provenance"},
                "accept": {"request_id", "response_id"},
                "decision": {"decision"},
            }
            kind = value.get("kind")
            allowed = fields.get(kind, set()) if isinstance(kind, str) else set()
            for key in ("request_id", "response_id", "provenance", "decision"):
                if key in value and (key not in allowed or value[key] is None):
                    raise ValueError("Unexpected or null action field")
            if not allowed.issubset(value):
                raise ValueError("Missing required action field")
        return value


class HistoricalEvent(Strict):
    run_id: Text
    queue_sha256: Digest
    base_hash: Digest
    event: Event


class Draft(Strict):
    schema_version: Literal["1.0.0"]
    data_kind: Literal["synthetic"]
    agency_id: Text
    intake_run_id: Text
    run_id: Text
    queue_sha256: Digest
    base_hash: Digest
    history: list[dict[str, Any]]
    events: list[Event]
    identities: dict[Text, list[Text]]

    @field_validator("history")
    @classmethod
    def valid_history(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            HistoricalEvent.model_validate(row)
        return rows


class EvidenceRequest(Strict):
    text: Text
    responses: dict[Text, Event]
    accepted: Text | None


class Case(Strict):
    owner: Text | None
    decision: Literal["same_person", "different_people", "leave_unresolved"] | None
    identity_state: Literal["unresolved"]
    status: Literal["open", "needs_evidence", "evidence_reviewed"]
    requests: dict[Text, EvidenceRequest]


class Ledger(Strict):
    schema_version: Literal["1.0.0"]
    data_kind: Literal["synthetic"]
    agency_id: Text
    intake_run_id: Text
    run_id: Text
    queue_sha256: Digest
    history: list[HistoricalEvent]
    cases: dict[Text, Case]
    reviewer_authentication: Literal["unauthenticated"]
    identity_changes_applied: Annotated[int, Field(strict=True, ge=0, le=0)]


def load_json(raw: str | bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValueError(f"Invalid JSON number: {value}")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def refuse_public_output(path: Path) -> None:
    if PUBLIC_FOLDER_NAMES & set(path.resolve().parts):
        raise RunRefused(
            "Workflow evidence and copied outputs cannot be written to a public folder"
        )


def publish(staged: Path, target: Path) -> None:
    """Atomically publish without replacing even an empty competing directory.

    Fail closed when the platform or filesystem lacks exclusive rename support.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    source, destination = os.fsencode(staged), os.fsencode(target)
    try:
        if sys.platform == "darwin":
            # Apple bsd/sys/stdio.h: renamex_np(..., RENAME_EXCL=0x4).
            rename = libc.renamex_np
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            result = rename(source, destination, 0x4)
        elif sys.platform == "linux":
            # Linux uapi/linux/{fs,fcntl}.h: RENAME_NOREPLACE=1, AT_FDCWD=-100.
            rename = libc.renameat2
            rename.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            rename.restype = ctypes.c_int
            result = rename(-100, source, -100, destination, 1)
        else:
            raise RunRefused("Exclusive workflow publication requires macOS or Linux")
    except AttributeError as exc:
        raise RunRefused("Exclusive workflow publication is unavailable on this platform") from exc
    if result != 0:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise ValueError("Child appeared during application; refusing overwrite")
        if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise RunRefused("Filesystem does not support exclusive workflow publication")
        raise OSError(code, os.strerror(code), target)


def snapshot(run: Path) -> tuple[dict[str, Any], dict[str, bytes], str]:
    path = run / "manifest.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Unsafe or missing manifest")
    raw = path.read_bytes()
    m = load_json(raw)
    if not isinstance(m, dict) or not isinstance(m.get("outputs"), dict):
        raise ValueError("Invalid manifest outputs")
    TypeAdapter(Text).validate_python(m.get("run_id"))
    if "review_queue.jsonl" not in m["outputs"]:
        raise ValueError("Queue hash missing from manifest")
    retained = {}
    for name, digest in m["outputs"].items():
        TypeAdapter(Text).validate_python(name)
        TypeAdapter(Digest).validate_python(digest)
        p = run / name
        if name == "manifest.json" or Path(name).name != name or p.is_symlink() or not p.is_file():
            raise ValueError("Unsafe or missing output")
        if name in ("review_queue.jsonl", "broker_workflow.json"):
            retained[name] = p.read_bytes()
            actual = hashlib.sha256(retained[name]).hexdigest()
        else:
            actual = sha256(p)
        if actual != digest:
            raise ValueError(f"Stale output: {name}")
    base_hash = hashlib.sha256(raw).hexdigest()
    if sha256(path) != base_hash:
        raise ValueError("Parent manifest changed during verification")
    return m, retained, base_hash


def manifest(run: Path) -> dict[str, Any]:
    return snapshot(run)[0]


def initial(run: Path, agency_id: str, intake_run_id: str) -> dict[str, Any]:
    m, retained, base_hash = snapshot(run)
    identities = {}
    for line in retained["review_queue.jsonl"].decode("utf-8").splitlines():
        item = load_json(line)
        if not isinstance(item, dict) or not isinstance(item.get("records"), list):
            raise ValueError("Invalid queue item")
        key = TypeAdapter(Text).validate_python(item.get("item_id"))
        ids = []
        for record in item["records"]:
            if not isinstance(record, dict):
                raise ValueError("Invalid queue record")
            ids.append(TypeAdapter(Text).validate_python(record.get("record_id")))
        if key in identities or len(ids) != len(set(ids)):
            raise ValueError("Duplicate queue item or record ID")
        if not ids:
            raise ValueError("Queue item requires record IDs")
        identities[key] = sorted(ids)
    history = []
    if "broker_workflow.json" in m["outputs"]:
        previous = load_json(retained["broker_workflow.json"])
        Ledger.model_validate(previous)
        if (previous["agency_id"], previous["intake_run_id"]) != (agency_id, intake_run_id):
            raise ValueError("Agency / Intake binding mismatch")
        history = previous["history"]
    draft = dict(
        schema_version="1.0.0",
        data_kind="synthetic",
        agency_id=agency_id,
        intake_run_id=intake_run_id,
        run_id=m["run_id"],
        queue_sha256=m["outputs"]["review_queue.jsonl"],
        base_hash=base_hash,
        identities=identities,
        history=history,
        events=[],
    )
    Draft.model_validate(draft)
    if "broker_workflow.json" in m["outputs"]:
        historical = dict(draft, identities={key: [] for key in previous["cases"]})
        if validate(historical, historical) != previous["cases"]:
            raise ValueError("Saved workflow cases disagree with event history")
    return draft


def validate(draft: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    parsed = Draft.model_validate(draft)
    if any(draft[k] != expected[k] for k in expected if k != "events"):
        raise ValueError("Stale or mismatched workflow binding/history")
    cases: dict[str, Any] = {
        key: dict(
            owner=None, decision=None, identity_state="unresolved", status="open", requests={}
        )
        for key in parsed.identities
    }
    # Historical cases may no longer appear in a later identity review queue.
    # Preserve their unresolved evidence instead of treating queue removal as resolution.
    for h in parsed.history:
        key = h["event"]["item_id"]
        cases.setdefault(
            key,
            dict(
                owner=None, decision=None, identity_state="unresolved", status="open", requests={}
            ),
        )
    if any(e.item_id not in parsed.identities for e in parsed.events):
        raise ValueError("New action names a case outside the current queue")
    seen = set()
    events = [Event.model_validate(h["event"]) for h in parsed.history] + parsed.events
    for e in events:
        if e.event_id in seen or e.item_id not in cases:
            raise ValueError("Duplicate event or unknown case")
        seen.add(e.event_id)
        c = cases[e.item_id]
        requests = c["requests"]
        if e.kind == "assign":
            c["owner"] = e.text
        elif e.kind == "request":
            requests[e.event_id] = dict(text=e.text, responses={}, accepted=None)
        elif e.kind in ("response", "accept"):
            if e.request_id not in requests:
                raise ValueError("Missing evidence request")
            request = requests[e.request_id]
            if e.kind == "response":
                if e.provenance is None:
                    raise ValueError("Response requires provenance")
                request["responses"][e.event_id] = e.model_dump(mode="json", exclude_none=True)
            else:
                if e.response_id not in request["responses"] or request["accepted"]:
                    raise ValueError("Missing response or already accepted")
                request["accepted"] = e.response_id
        elif e.kind == "decision":
            if e.decision is None:
                raise ValueError("Decision label required")
            c["decision"] = e.decision
        allowed = {
            "response": {"request_id", "provenance"},
            "accept": {"request_id", "response_id"},
            "decision": {"decision"},
        }
        for key in ("request_id", "response_id", "provenance", "decision"):
            if getattr(e, key) is not None and key not in allowed.get(e.kind, set()):
                raise ValueError("Unexpected action field")
        c["status"] = (
            "needs_evidence"
            if any(not r["accepted"] for r in requests.values())
            else "evidence_reviewed"
            if requests
            else "open"
        )
    return cases


def apply(
    run: Path, draft: dict[str, Any], target: Path, *, agency_id: str, intake_run_id: str
) -> dict[str, Any]:
    """Copy verified outputs into a new run; append bound events atomically, never merge."""
    parsed = Draft.model_validate(draft)
    expected = initial(run, agency_id, intake_run_id)
    cases = validate(draft, expected)
    if not parsed.events:
        raise ValueError("No new events")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", target.name):
        raise ValueError("Invalid child run ID")
    refuse_public_output(target)
    refuse_parent_overlap(run, target, parsed.run_id, target.name)
    if target.exists() or target.is_symlink():
        raise ValueError("Child run exists; immutable application refuses overwrite")
    m, _, base_hash = snapshot(run)
    if base_hash != parsed.base_hash:
        raise ValueError("Parent manifest changed during application")
    binding = {k: expected[k] for k in ("run_id", "queue_sha256", "base_hash")}
    history = parsed.history + [
        dict(**binding, event=e.model_dump(mode="json", exclude_none=True)) for e in parsed.events
    ]
    ledger = dict(
        schema_version="1.0.0",
        data_kind="synthetic",
        agency_id=parsed.agency_id,
        intake_run_id=parsed.intake_run_id,
        run_id=target.name,
        queue_sha256=parsed.queue_sha256,
        history=history,
        cases=cases,
        reviewer_authentication="unauthenticated",
        identity_changes_applied=0,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / f".{target.name}.workflow-lock"
    try:
        lock.open("x").close()
    except FileExistsError as exc:
        raise ValueError("Application already in progress for this child") from exc
    tmp = None
    try:
        tmp = Path(tempfile.mkdtemp(prefix=".workflow-", dir=target.parent))
        for name in m["outputs"]:
            shutil.copyfile(run / name, tmp / name)
        for name, digest in m["outputs"].items():
            if sha256(tmp / name) != digest:
                raise ValueError("Source changed during application")
        if sha256(run / "manifest.json") != parsed.base_hash:
            raise ValueError("Parent manifest changed during application")
        Ledger.model_validate(ledger)
        (tmp / "broker_workflow.json").write_text(canonical(ledger), encoding="utf-8")
        m.update(
            run_id=target.name,
            parent_run_id=parsed.run_id,
            workflow_parent_manifest_sha256=parsed.base_hash,
            workflow_only=True,
        )
        m["outputs"] = {p.name: sha256(p) for p in sorted(tmp.iterdir())}
        (tmp / "manifest.json").write_text(canonical(m), encoding="utf-8")
        if target.exists() or target.is_symlink():
            raise ValueError("Child appeared during application; refusing overwrite")
        publish(tmp, target)
    finally:
        if tmp is not None and tmp.exists():
            shutil.rmtree(tmp)
        lock.unlink()
    return ledger
