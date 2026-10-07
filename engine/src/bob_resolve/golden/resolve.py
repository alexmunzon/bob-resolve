"""Scored pairs to golden people: clusters, split on conflict, survivorship, merge log lines.

Only AUTO_MATCH pairs merge here. Gray pairs are carried as pending for the review queue (PR 7).
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bob_resolve.cluster import split_on_conflict
from bob_resolve.config import AUTO_MATCH_RULE_ID, REVIEW_RULE_ID
from bob_resolve.golden.survivorship import GoldenPerson, build_golden
from bob_resolve.load.records import PersonRecord
from bob_resolve.mergelog import MergeLogEntry
from bob_resolve.normalize.record import normalize_record
from bob_resolve.score.rules import ScoredPair


class ReviewItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: Literal["CLUSTER_CONFLICT", "IDENTITY_CONFLICT"]
    severity: Literal["high", "normal"]
    record_ids: tuple[str, ...]
    pairs: tuple[tuple[str, str], ...]
    detail: str


class Resolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    people: tuple[GoldenPerson, ...]
    review: tuple[ReviewItem, ...]
    pending_gray: tuple[ScoredPair, ...]
    unidentifiable: tuple[str, ...]
    log: tuple[MergeLogEntry, ...]


def _identifiable(r: PersonRecord) -> bool:
    return any((r.first_name, r.last_name, r.dob, r.mbi))


def resolve(
    records: Sequence[PersonRecord],
    scored: Sequence[ScoredPair],
    recency: Mapping[str, date],
    *,
    run_id: str,
    clock: Callable[[], datetime],
    review_pairs: frozenset[tuple[str, str]] = frozenset(),
    shared_ids: bool = True,
) -> Resolution:
    """A record with no name, DOB, or MBI is not a person: it is listed as unidentifiable.
    `review_pairs` are matches a human decided (PR 7): their lines and records carry tier
    "review" and rule REVIEW-DECISION instead of the rules arm."""
    seen: set[str] = set()
    for r in records:
        if r.record_id in seen:
            raise ValueError(f"Duplicate record_id: {r.record_id}")
        seen.add(r.record_id)
    people_recs = [r for r in records if _identifiable(r)]
    ids = {r.record_id for r in people_recs}
    matches = [p for p in scored if p.decision == "AUTO_MATCH" and {p.a, p.b} <= ids]
    clusters, kept, splits = split_on_conflict(
        [normalize_record(r) for r in people_recs], matches, shared_ids=shared_ids
    )
    by_id = {r.record_id: r for r in people_recs}
    people, review, log = [], [], []

    def line(p: ScoredPair, action: Literal["merge", "split"], rule: str) -> MergeLogEntry:
        t, by_human = clock().isoformat(), (p.a, p.b) in review_pairs
        if by_human and action == "merge":
            rule = REVIEW_RULE_ID
        return MergeLogEntry(
            action=action,
            a=p.a,
            b=p.b,
            tier="review" if by_human else "rules",
            score=p.score,
            rule_ids=(rule,),
            run_id=run_id,
            time=t,
        )

    for s in splits:
        review.append(
            ReviewItem(
                reason="CLUSTER_CONFLICT",
                severity="normal",
                record_ids=s.records,
                pairs=tuple(sorted(set(s.conflicts) | set(s.cut))),
                detail=(
                    "Automatic matches chained together records that conflict. Every link "
                    "between them is held for a person to review; none was kept automatically."
                ),
            )
        )
    for p in sorted(matches, key=lambda p: (p.a, p.b)):
        log.append(
            line(p, "merge", AUTO_MATCH_RULE_ID)
            if (p.a, p.b) in kept
            else line(p, "split", "CLUSTER_CONFLICT")
        )
    for c in clusters:
        via = {e for e in kept & review_pairs if e[0] in c}
        tier = {r: "single" if len(c) == 1 else "rules" for r in c}
        tier |= {r: "review" for e in via for r in e}
        person = build_golden([by_id[r] for r in c], recency, tier)
        people.append(person)
        if person.review_reasons:
            review.append(
                ReviewItem(
                    reason="IDENTITY_CONFLICT",
                    severity="high",
                    record_ids=c,
                    pairs=(),
                    detail="Authoritative records disagree on DOB or MBI; the field is empty.",
                )
            )
    gray = tuple(p for p in scored if p.decision == "GRAY")
    for p in gray:
        if p.reason == "IDENTITY_CONFLICT":
            review.append(
                ReviewItem(
                    reason="IDENTITY_CONFLICT",
                    severity="high",
                    record_ids=(p.a, p.b),
                    pairs=((p.a, p.b),),
                    detail="Shared MBI with DOBs that are not close (GR-002); not merged.",
                )
            )
    return Resolution(
        people=tuple(people),
        review=tuple(review),
        pending_gray=gray,
        unidentifiable=tuple(sorted(r.record_id for r in records if not _identifiable(r))),
        log=tuple(log),
    )
