"""Offline second opinions bound to a verified native integration resolution.

This is an additive review artifact, not an input to scoring or human decisions.
"""

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Literal

from bob_resolve.adapters.contract import ContractModel, Packet, Provenance, canonical_json
from bob_resolve.adapters.intake import IntakeResolution, resolve_intake
from bob_resolve.advisory import Compared, Relation, Request, Result, evaluate
from bob_resolve.score.rules import ScoredPair


class Entry(ContractModel):
    request: Request
    result: Result
    citations: tuple[Provenance, ...]


class Sidecar(ContractModel):
    version: Literal["bob-advisory-sidecar-v1"] = "bob-advisory-sidecar-v1"
    label: str = "Offline review aid. Hand-written fixtures only; no model called."
    resolution_sha256: str
    entries: tuple[Entry, ...]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _relation(value: str | None) -> Relation:
    if value is None:
        return "missing"
    if value in {"same", "equal", "exact"}:
        return "agree"
    if value in {"different", "far"}:
        return "conflict"
    return "similar"


def comparisons(pair: ScoredPair) -> dict[Compared, Relation]:
    c = pair.comparison
    names = (_relation(c.first), _relation(c.last))
    name: Relation = (
        "conflict"
        if "conflict" in names
        else "missing"
        if "missing" in names
        else "agree"
        if names == ("agree", "agree")
        else "similar"
    )
    return {
        "name": name,
        "dob": _relation(c.dob),
        "mbi": _relation(c.mbi),
        "phone": _relation(c.phone),
        "email": _relation(c.email),
        "street": _relation(c.street),
        "policy": _relation(c.policy),
    }


def _read_fixture(directory: Path, filename: str) -> bytes:
    """Pin each directory component and refuse symlink/FIFO races at open time.

    Fail closed on platforms without descriptor-relative, no-follow opens. Never
    inspect a path and then trust that it still names the same object when opened.
    """
    if not all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY")):
        raise ValueError("safe local fixture opens unavailable")
    if os.open not in os.supports_dir_fd:
        raise ValueError("descriptor-relative opens unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    directory_flags = flags | os.O_DIRECTORY
    parts = Path(os.path.abspath(directory)).parts
    directory_fd = os.open(parts[0], directory_flags)
    try:
        for part in parts[1:]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fixture_fd = os.open(filename, flags, dir_fd=directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fixture_fd).st_mode):
                raise ValueError("fixture must be a regular local file")
            return os.read(fixture_fd, 8193)
        finally:
            os.close(fixture_fd)
    finally:
        os.close(directory_fd)


def build_sidecar(
    source: Packet,
    resolution_bytes: bytes,
    intake_root: Path,
    *,
    mode: Literal["off", "replay"] = "off",
    responses: Path | None = None,
) -> Sidecar:
    """Recompute native evidence before trusting it; never alter original artifacts.

    In off mode the responses directory is never inspected. Missing, oversized, or
    malformed fixtures stay pending. Only request-key filenames are read, never URLs.
    """
    if mode not in {"off", "replay"}:
        raise ValueError("only off and replay are supported")
    saved = IntakeResolution.model_validate_json(resolution_bytes)
    expected = resolve_intake(
        source,
        intake_root,
        run_id=saved.packet.run_id,
        as_of=saved.as_of,
        shared_ids=saved.shared_ids,
    )
    if canonical_json(saved) != canonical_json(expected):
        raise ValueError("resolution does not match verified deterministic source")
    queue = tuple(p for p in saved.scored_pairs if p.decision == "GRAY")
    queue_hash = digest(_json([p.model_dump(mode="json") for p in queue]))
    run_hash = digest(canonical_json(saved.packet).encode())
    by_id = {c.record_id: c for c in source.clients}
    entries = []
    for pair in queue:
        rails = list(pair.guard_rails)
        request = Request(
            run_hash=run_hash,
            queue_hash=queue_hash,
            pair_hash=digest(_json(sorted((pair.a, pair.b)))),
            comparisons=comparisons(pair),
            guardrails=tuple(rails) + (("IDENTITY_CONFLICT",) if pair.reason else ()),
        )
        raw = None
        if mode == "replay" and responses is not None:
            try:
                raw = _read_fixture(responses, f"{request.key}.json")
            except (OSError, ValueError):
                raw = b""  # Explicitly invalid/unreadable, not an accepted suggestion.
        entries.append(
            Entry(
                request=request,
                result=evaluate(request, mode=mode, response=raw),
                citations=tuple(by_id[r].provenance for r in sorted((pair.a, pair.b))),
            )
        )
    return Sidecar(resolution_sha256=digest(resolution_bytes), entries=tuple(entries))
