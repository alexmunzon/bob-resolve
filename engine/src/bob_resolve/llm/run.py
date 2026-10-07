"""Attach saved explanations, replayed offline, without changing any match decision.

Nothing here can call a model or the network: it only reads saved files from one folder.
Every row still requires a person to decide. Scoring, merges, review routing and guard
rails are computed before this runs and never read its output.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from bob_resolve.llm.replay import Advisory, LlmMode, review_pair
from bob_resolve.load.records import PersonRecord
from bob_resolve.score.rules import ScoredPair

LABEL = (
    "Saved explanation replayed offline. Advisory only; a person still decides. "
    "No model was called."
)
# Record fields mapped to the explanation request's compared field names. Free text and lineage
# are never included. MBI and policy keys are withheld when shared ids are off.
_FIELDS: Mapping[str, str] = {
    "first_name": "first_name",
    "last_name": "last_name",
    "dob": "dob",
    "address_line1": "street",
    "zip": "zip",
    "phone": "phone",
    "email": "email",
}
_SHARED_ID_FIELDS: Mapping[str, str] = {"mbi": "mbi", "policy_keys": "policy_keys"}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value) if value else None
    return str(value)


def compared_fields(
    a: PersonRecord, b: PersonRecord, shared_ids: bool
) -> dict[str, tuple[str | None, str | None]]:
    """Only the structured fields the rules compare, never notes or lineage."""
    fields = {**_FIELDS, **(_SHARED_ID_FIELDS if shared_ids else {})}
    da, db = a.model_dump(mode="json"), b.model_dump(mode="json")
    return {name: (_text(da[f]), _text(db[f])) for f, name in fields.items()}


def _off_usage(mode: LlmMode) -> dict[str, Any]:
    return {"mode": mode, "calls": 0, "cost_usd": 0.0}


def evaluate_rationales(
    scored: Sequence[ScoredPair],
    records: Mapping[str, PersonRecord],
    owners: Mapping[str, str],
    *,
    mode: LlmMode,
    cassette_dir: Path,
    shared_ids: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rows of advisory evidence for gray pairs, plus usage. Off returns at once and reads nothing.

    A missing saved explanation is "pending"; an unreadable or invalid one is "invalid". Neither
    stops the run. Jev is not wired into this build, so every gray pair counts as Jev-unsure.
    """
    if mode != "replay":
        return [], _off_usage(mode)
    rows: list[dict[str, Any]] = []
    seen_cost: dict[str, float] = {}
    for pair in scored:
        if pair.decision != "GRAY":
            continue
        # SPEC: Opus only when a merge would move an active policy or a commission line.
        high_stakes = pair.a in owners or pair.b in owners
        model: Literal["sonnet", "opus"] = "opus" if high_stakes else "sonnet"
        rails = tuple(sorted(set(pair.guard_rails)))
        try:
            fields = compared_fields(records[pair.a], records[pair.b], shared_ids)
            advisory = review_pair(
                fields,
                cassette_dir=cassette_dir,
                mode="replay",
                gray_zone=True,
                jev_uncertain=True,
                high_stakes=high_stakes,
                guardrail_ids=rails,
                shared_ids=shared_ids,
            )
            status: str = advisory.status
        except Exception:  # noqa: BLE001 - advisory evidence must never stop a run
            advisory = Advisory("pending", model, "", rails)
            status = "invalid"
        row = asdict(advisory)
        key = row.pop("request_key")  # the hash of compared fields never leaves the run
        row.update({"a": pair.a, "b": pair.b, "status": status, "label": LABEL})
        if status != "replayed":
            row.update({"rationale": None, "provenance": None, "recorded_cost_usd": 0.0})
        else:
            seen_cost[key] = advisory.recorded_cost_usd
        rows.append(row)
    return rows, {
        **_off_usage(mode),
        "label": LABEL,
        "replayed": sum(r["status"] == "replayed" for r in rows),
        "pending": sum(r["status"] == "pending" for r in rows),
        "invalid": sum(r["status"] == "invalid" for r in rows),
        "unique_replayed_requests": len(seen_cost),
        "recorded_cost_usd": sum(seen_cost.values()),
    }
