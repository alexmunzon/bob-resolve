"""Read saved explanations from disk, offline, without network access or merge authority."""

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bob_resolve.score.rules import GUARD_RAILS

# off (default) or replay. There is deliberately no live or record mode.
LlmMode = Literal["off", "replay"]

# A saved explanation file larger than this is refused as invalid.
MAX_CASSETTE_BYTES = 8 * 1024

# Only structured fields that the rules compare may enter a request.
COMPARED_FIELDS = frozenset(
    {
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "dob",
        "mbi",
        "phone",
        "email",
        "street",
        "city",
        "state",
        "zip",
        "policy_keys",
    }
)


@dataclass(frozen=True)
class Advisory:
    status: Literal["off", "ineligible", "pending", "replayed"]
    model: Literal["sonnet", "opus"]
    request_key: str
    guardrail_ids: tuple[str, ...]
    rationale: str | None = None
    provenance: str | None = None
    recorded_cost_usd: float = 0.0
    cost_usd: float = 0.0
    requires_human_review: Literal[True] = True


def request_key(
    compared_fields: Mapping[str, tuple[str | None, str | None]],
    *,
    guardrail_ids: tuple[str, ...] = (),
    high_stakes: bool = False,
    shared_ids: bool = True,
) -> str:
    """Stable request identity, including policy version and model tier."""
    if not compared_fields or set(compared_fields) - COMPARED_FIELDS:
        raise ValueError("Only nonempty structured compared fields are allowed")
    for values in compared_fields.values():
        if not isinstance(values, tuple) or len(values) != 2:
            raise ValueError("Each compared field needs exactly two values")
        if any(value is not None and not isinstance(value, str) for value in values):
            raise ValueError("Compared values must be strings or null")
    if any(rail not in GUARD_RAILS for rail in guardrail_ids):
        raise ValueError("Unknown guardrail id")
    payload = {
        "schema": "bob-llm-rationale-v1",
        "model": "opus" if high_stakes else "sonnet",
        "compared_fields": {
            field: values
            for field, values in compared_fields.items()
            if shared_ids or field not in {"mbi", "policy_keys"}
        },
        "shared_ids": shared_ids,
        "guardrail_ids": sorted(set(guardrail_ids)),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def review_pair(
    compared_fields: Mapping[str, tuple[str | None, str | None]],
    *,
    cassette_dir: Path,
    mode: str = "off",
    gray_zone: bool = True,
    jev_uncertain: bool = True,
    high_stakes: bool = False,
    guardrail_ids: tuple[str, ...] = (),
    budget_usd: float = 0.0,
    shared_ids: bool = True,
) -> Advisory:
    """Return advisory evidence; missing recordings still require human review.

    The separate budget is validated but never spent. Live/record modes are deliberately
    unavailable. A recorded rationale cannot change a rule decision or clear a guardrail.
    """
    if mode not in {"off", "replay"}:
        raise ValueError("LLM mode must be off or replay")
    if not math.isfinite(budget_usd) or budget_usd < 0:
        raise ValueError("Budget must be finite and nonnegative")
    key = request_key(
        compared_fields, guardrail_ids=guardrail_ids, high_stakes=high_stakes, shared_ids=shared_ids
    )
    model: Literal["sonnet", "opus"] = "opus" if high_stakes else "sonnet"
    rails = tuple(sorted(set(guardrail_ids)))
    if mode == "off":
        return Advisory("off", model, key, rails)
    if not gray_zone or not jev_uncertain:
        return Advisory("ineligible", model, key, rails)
    path = cassette_dir / f"{key}.json"
    if not path.is_symlink() and not path.exists():
        return Advisory("pending", model, key, rails)
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("A saved explanation must be a regular file, not a link or folder")
        with path.open("rb") as handle:
            raw = handle.read(MAX_CASSETTE_BYTES + 1)
        if len(raw) > MAX_CASSETTE_BYTES:
            raise ValueError("Saved explanation file is too large")
        payload = json.loads(raw.decode("utf-8"))
        expected = {"request_key", "model", "rationale", "provenance", "cost_usd"}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError("Invalid rationale cassette schema")
        if payload["request_key"] != key or payload["model"] != model:
            raise ValueError("Rationale cassette request or model mismatch")
        rationale, provenance, cost = (
            payload["rationale"],
            payload["provenance"],
            payload["cost_usd"],
        )
        if not isinstance(rationale, str) or not plain_text(rationale) or len(rationale) > 2000:
            raise ValueError("Invalid rationale")
        if not isinstance(provenance, str) or not plain_text(provenance) or len(provenance) > 500:
            raise ValueError("Invalid provenance")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise ValueError("Invalid recorded cost")
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Invalid recorded cost")
    except (OSError, UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("Unreadable rationale cassette") from exc
    return Advisory(
        "replayed", model, key, rails, plain_text(rationale), plain_text(provenance), float(cost)
    )


def plain_text(value: str) -> str:
    """Plain text only: control, format and bidi characters become spaces, then trimmed."""
    cleaned = "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} else ch for ch in value
    )
    return " ".join(cleaned.split())
