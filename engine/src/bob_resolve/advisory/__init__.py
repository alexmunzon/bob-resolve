"""Versioned second opinions, separate from the unchanged llm explanation replay.

Only comparison categories cross this boundary, never personal values. No I/O.
"""

import hashlib
import json
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hash = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
Compared = Literal["name", "dob", "mbi", "phone", "email", "street", "policy"]
Relation = Literal["agree", "conflict", "similar", "missing"]
Guard = Literal[
    "GR-001",
    "GR-002",
    "GR-003",
    "GR-004",
    "GR-005",
    "GR-006",
    "GR-007",
    "GR-008",
    "IDENTITY_CONFLICT",
]
Opinion = Literal["same_person", "different_people", "unsure"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Request(Contract):
    version: Literal["bob-second-opinion-v1"] = "bob-second-opinion-v1"
    data_kind: Literal["synthetic"] = "synthetic"
    run_hash: Hash
    queue_hash: Hash
    pair_hash: Hash
    deterministic_decision: Literal["GRAY"] = "GRAY"
    comparisons: Annotated[dict[Compared, Relation], Field(min_length=1, max_length=7)]
    guardrails: tuple[Guard, ...] = ()

    @property
    def key(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class Response(Contract):
    version: Literal["bob-second-opinion-v1"]
    request_key: Hash
    origin: Literal["hand_written_synthetic_fixture"]
    opinion: Opinion
    evidence: Annotated[tuple[Compared, ...], Field(min_length=1, max_length=7)]

    @model_validator(mode="after")
    def unique_evidence(self) -> Self:
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("duplicate evidence")
        return self


class Result(Contract):
    mode: Literal["off", "replay", "live"]
    status: Literal["off", "pending", "replayed", "live_blocked"]
    request_key: Hash
    review_state: Literal["needs_review"] = "needs_review"
    suggestion: Response | None = None
    reason: str
    label: str = "No model called."
    calls: Literal[0] = 0
    cost_usd: Literal[0] = 0


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def evaluate(request: Request, *, mode: str = "off", response: bytes | None = None) -> Result:
    """A valid replay is evidence for review, never permission to merge.

    Live is a visibly blocked mode, not a provider implementation. The caller supplies
    bytes; this module cannot read cassettes, credentials, environment variables or URLs.
    """
    if mode not in {"off", "replay", "live"}:
        raise ValueError("mode must be off, replay or live")
    request = Request.model_validate(request.model_dump())
    key = request.key
    if mode == "off":
        return Result(mode="off", status="off", request_key=key, reason="disabled")
    if mode == "live":
        return Result(
            mode="live",
            status="live_blocked",
            request_key=key,
            reason="requires approved provider/model, secure credentials and spending cap; "
            "live transport is not implemented",
        )
    reason = "missing_response"
    if response is not None:
        try:
            if not isinstance(response, bytes) or len(response) > 8192:
                raise ValueError("invalid response size or type")
            parsed = Response.model_validate(json.loads(response, object_pairs_hook=_unique))
            if parsed.request_key != key:
                raise ValueError("stale request")
            if any(request.comparisons.get(e) in {None, "missing"} for e in parsed.evidence):
                raise ValueError("ungrounded evidence")
            if parsed.opinion == "same_person" and (
                request.guardrails or "conflict" in request.comparisons.values()
            ):
                raise ValueError("contradicts deterministic evidence")
            if parsed.opinion == "same_person" and not any(
                request.comparisons[e] == "agree" for e in parsed.evidence
            ):
                raise ValueError("unsupported by cited comparisons")
            if parsed.opinion == "different_people" and not any(
                request.comparisons[e] == "conflict" for e in parsed.evidence
            ):
                raise ValueError("contradicts cited comparisons")
            return Result(
                mode="replay",
                status="replayed",
                request_key=key,
                suggestion=parsed,
                reason="human_review_required",
                label="Hand-written synthetic fixture; no model called.",
            )
        except (ValueError, UnicodeError, RecursionError):
            reason = "invalid_contradictory_or_ungrounded_response"
    return Result(mode="replay", status="pending", request_key=key, reason=reason)
