"""Review queue (SPEC 6 step 7): one item per gray pair, cluster conflict, or identity conflict.

Records are minimized for the reviewer: names, DOB, address, phone, email, and the MBI masked to
its last 4. Human decisions are stored as labels in a decisions file; nothing learns from them.
"""

import hashlib
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bob_resolve.config import MBI_VISIBLE_CHARS, SCORE_HIGH, SCORE_LOW
from bob_resolve.golden import Resolution
from bob_resolve.load.records import PersonRecord
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score import compare
from bob_resolve.score.rules import ScoredPair, Suggestion, weighted_score

Kind = Literal["gray_pair", "cluster_conflict", "identity_conflict"]
Reason = Literal["GRAY_ZONE", "CLUSTER_CONFLICT", "IDENTITY_CONFLICT"]
Severity = Literal["high", "medium"]


class Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReviewRecord(Strict):
    record_id: str
    source: str
    source_file: str
    row_number: int
    first_name: str | None
    last_name: str | None
    dob: str | None
    address_line1: str | None
    city: str | None
    state: str | None
    zip: str | None
    phone: str | None
    email: str | None
    mbi_masked: str | None
    active_policy: bool


class PairEvidence(Strict):
    a: str
    b: str
    score: float
    decision: str
    evidence: dict[str, float | str | bool | None]


class QueueItem(Strict):
    item_id: str
    kind: Kind
    reason: Reason
    severity: Severity
    cutoff_distance: float
    deciding_tier: str
    suggestion: Suggestion
    rule_ids: tuple[str, ...]
    already_one_person: bool
    records: tuple[ReviewRecord, ...]
    pairs: tuple[PairEvidence, ...]
    detail: str


class ReviewDecision(Strict):
    """One line of a decisions file (JSONL). A label is stored, never learned from."""

    item_id: str
    decision: Literal["same_person", "different_people"]
    reviewer: str
    decided_at: datetime
    note: str | None = None


def mask_mbi(mbi: str | None) -> str | None:
    clean = "".join(c for c in (mbi or "") if c.isalnum())
    keep = MBI_VISIBLE_CHARS
    return "*" * (len(clean) - keep) + clean[-keep:] if len(clean) > keep else None


def cutoff_distance(scores: Sequence[float]) -> float:
    """How far the item's closest pair score sits from the nearer cutoff (auto-match or
    auto-reject line). Small means a close call. An item with no scored pair counts as 0."""
    return min((min(abs(SCORE_HIGH - s), abs(s - SCORE_LOW)) for s in scores), default=0.0)


def severity(
    reason: Reason, suggestion: Suggestion, ids: Sequence[str], owners: Mapping[str, str]
) -> Severity:
    """High for IDENTITY_CONFLICT, or a "same person" suggestion where two records each hold an
    active policy under different client ids, so a merge would move money or coverage.
    `owners` maps a record with an active policy to the client id that owns the policy."""
    held = {owners[i] for i in ids if i in owners}
    active = sum(i in owners for i in ids)
    if reason == "IDENTITY_CONFLICT" or (suggestion == "same_person" and active >= 2
                                         and len(held) >= 2):  # fmt: skip
        return "high"
    return "medium"


def minimize(r: PersonRecord, active: Collection[str] | Mapping[str, str]) -> ReviewRecord:
    return ReviewRecord(
        record_id=r.record_id,
        source=r.source,
        source_file=r.lineage.source_file,
        row_number=r.lineage.row_number,
        first_name=r.first_name,
        last_name=r.last_name,
        dob=r.dob.isoformat() if r.dob else None,
        address_line1=r.address_line1,
        city=r.city,
        state=r.state,
        zip=r.zip,
        phone=r.phone,
        email=r.email,
        mbi_masked=mask_mbi(r.mbi),
        active_policy=r.record_id in active,
    )


def build_queue(
    res: Resolution,
    scored: Sequence[ScoredPair],
    records: Mapping[str, PersonRecord],
    norm: Mapping[str, NormalizedRecord],
    owners: Mapping[str, str],
    shared_ids: bool,
    skip: Collection[str] = (),
) -> list[QueueItem]:
    """`owners` maps each record with an active policy to its owning client id (see
    `severity`). Items in `skip` (already decided) are left out. Sorted: high first, then the
    closest call (distance from the nearer cutoff), then item id."""
    by_pair = {(p.a, p.b): p for p in scored}
    person = {r: p.person_id for p in res.people for r in p.record_ids}

    def evidence(a: str, b: str) -> PairEvidence:
        p = by_pair.get((a, b))
        c = p.comparison if p else compare(norm[a], norm[b], shared_ids)
        score, decision = (p.score, p.decision) if p else (weighted_score(c), "NOT_SCORED")
        return PairEvidence(a=a, b=b, score=score, decision=decision, evidence=c.model_dump())

    def item(
        kind: Kind, reason: Reason, ids: Sequence[str], pairs: Sequence[tuple[str, str]],
        suggestion: Suggestion, rules: Sequence[str], detail: str,
    ) -> QueueItem:  # fmt: skip
        ids = sorted(ids)
        ev = tuple(evidence(a, b) for a, b in sorted(pairs))
        digest = hashlib.sha256(f"{kind}|{'|'.join(ids)}".encode()).hexdigest()[:12]
        return QueueItem(
            item_id=f"rq-{digest}",
            kind=kind,
            reason=reason,
            severity=severity(reason, suggestion, ids, owners),
            cutoff_distance=round(cutoff_distance([p.score for p in ev]), 6),
            deciding_tier="rules",
            suggestion=suggestion,
            rule_ids=tuple(rules),
            already_one_person=len({person.get(i, i) for i in ids}) == 1,
            records=tuple(minimize(records[i], owners) for i in ids),
            pairs=ev,
            detail=detail,
        )

    items = []
    for p in res.pending_gray:
        conflict = p.reason == "IDENTITY_CONFLICT"
        if conflict:
            detail = "Shared MBI with birth dates that are not close (GR-002); not merged."
        elif p.guard_rails:
            detail = (
                f"Guard rails {', '.join(p.guard_rails)} require human review "
                "regardless of the score."
            )
        else:
            detail = "Score between the auto-reject and auto-match lines; Jev is off."
        items.append(
            item(
                "gray_pair",
                "IDENTITY_CONFLICT" if conflict else "GRAY_ZONE",
                (p.a, p.b),
                [(p.a, p.b)],
                p.suggestion or "unsure",
                p.guard_rails or ("SCORE-GRAY",),
                detail,
            )
        )
    for r in res.review:
        if r.reason == "CLUSTER_CONFLICT":
            items.append(
                item(
                    "cluster_conflict",
                    "CLUSTER_CONFLICT",
                    r.record_ids,
                    r.pairs,
                    "different_people",
                    ("CLUSTER_CONFLICT",),
                    r.detail,
                )  # fmt: skip
            )
        elif not r.pairs:  # authoritative records in one cluster disagree on DOB or MBI
            items.append(
                item(
                    "identity_conflict",
                    "IDENTITY_CONFLICT",
                    r.record_ids,
                    [],
                    "unsure",
                    ("IDENTITY_CONFLICT",),
                    r.detail,
                )  # fmt: skip
            )
    items = [i for i in items if i.item_id not in skip]
    return sorted(
        items,
        key=lambda i: (i.severity != "high", i.cutoff_distance, i.item_id),
    )


def read_decisions(path: Path) -> list[ReviewDecision]:
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = [ReviewDecision.model_validate_json(x) for x in lines]
    if len({d.item_id for d in out}) != len(out):
        raise ValueError(f"{path.name} decides the same item twice")
    return out


__all__ = [
    "PairEvidence",
    "QueueItem",
    "ReviewDecision",
    "ReviewRecord",
    "build_queue",
    "cutoff_distance",
    "mask_mbi",
    "minimize",
    "read_decisions",
    "severity",
]
