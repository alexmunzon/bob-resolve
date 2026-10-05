"""Rules arm: weighted score, two cutoffs, and guard rails that override the score.

A false merge is worse than a missed match (SPEC decision 2). Guard rails never let a pair
auto-match; a pair they stop goes to the gray zone with the rule id recorded on it.
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bob_resolve.config import (
    GRAY_SAME_PERSON_MIN,
    SCORE_BIAS,
    SCORE_HIGH,
    SCORE_LOW,
    SCORE_WEIGHTS,
)
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.compare import Comparison, compare

Decision = Literal["AUTO_MATCH", "GRAY", "AUTO_REJECT"]
Suggestion = Literal["same_person", "different_people", "unsure"]
RuleId = Literal["GR-001", "GR-002", "GR-003"]
GUARD_RAILS: dict[RuleId, str] = {
    "GR-001": "Different generational suffix (Jr and Sr) never auto-matches.",
    "GR-002": "Shared MBI with a DOB neither within one edit nor a month-day swap: "
    "IDENTITY_CONFLICT, never auto-matches.",
    "GR-003": "Shared phone or email alone (names and DOB not compatible) never auto-matches.",
}
_CLOSE_DOB = frozenset({"exact", "transposition", "month_day_swap", "one_edit"})


class ScoredPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    a: str
    b: str
    comparison: Comparison
    score: float
    decision: Decision
    guard_rails: tuple[RuleId, ...]
    reason: Literal["IDENTITY_CONFLICT"] | None
    suggestion: Suggestion | None


def weighted_score(c: Comparison) -> float:
    """Logistic of the bias plus each present field's level weight: a number in [0, 1]."""
    total = SCORE_BIAS
    for field, weights in SCORE_WEIGHTS.items():
        level = getattr(c, field)
        if level is not None:
            total += weights[level]
    return 1 / (1 + math.exp(-total))


def guard_rails(c: Comparison) -> tuple[RuleId, ...]:
    hits: list[RuleId] = []
    if c.suffix == "different":
        hits.append("GR-001")
    if c.mbi == "same" and c.dob == "far":
        hits.append("GR-002")
    identity_ok = (
        c.first in ("equal", "nickname", "close")
        and c.last in ("equal", "close")
        and c.dob in _CLOSE_DOB
    )
    shared_contact = c.phone == "same" or c.email == "same"
    if shared_contact and c.mbi != "same" and not identity_ok:
        hits.append("GR-003")
    return tuple(hits)


def decide(score: float, rails: tuple[RuleId, ...]) -> tuple[Decision, Suggestion | None]:
    """An identity conflict always goes to review. Other rails only stop an auto-match; a pair
    that scores below the low line is still rejected, since rejecting never merges anyone."""
    if "GR-002" in rails:
        return "GRAY", "different_people"
    if score < SCORE_LOW:
        return "AUTO_REJECT", None
    if score >= SCORE_HIGH and not rails:
        return "AUTO_MATCH", None
    if rails:
        return "GRAY", "different_people"
    return "GRAY", "same_person" if score >= GRAY_SAME_PERSON_MIN else "unsure"


def score_pair(a: NormalizedRecord, b: NormalizedRecord, shared_ids: bool = True) -> ScoredPair:
    c = compare(a, b, shared_ids)
    s, rails = weighted_score(c), guard_rails(c)
    decision, suggestion = decide(s, rails)
    return ScoredPair(
        a=a.record_id,
        b=b.record_id,
        comparison=c,
        score=s,
        decision=decision,
        guard_rails=rails,
        reason="IDENTITY_CONFLICT" if "GR-002" in rails else None,
        suggestion=suggestion,
    )
