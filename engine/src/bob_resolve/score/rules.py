"""Rules arm: weighted score, two cutoffs, and guard rails that override the score.

A false merge is worse than a missed match (SPEC decision 2). Guard rails never let a pair
auto-match; a pair they stop goes to the gray zone with the rule id recorded on it.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bob_resolve.config import (
    DOB_TRANSPOSITION_MAX_YEARS,
    GRAY_SAME_PERSON_MIN,
    INDEPENDENT_EVIDENCE_LEVELS,
    OWN_RECORD_TIE_FIELDS,
    PERSON_EVIDENCE_LEVELS,
    SCORE_BIAS,
    SCORE_HIGH,
    SCORE_LOW,
    SCORE_WEIGHTS,
)
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.compare import Comparison, compare

Decision = Literal["AUTO_MATCH", "GRAY", "AUTO_REJECT"]
Suggestion = Literal["same_person", "different_people", "unsure"]
RuleId = Literal["GR-001", "GR-002", "GR-003", "GR-004", "GR-005", "GR-006", "GR-007", "GR-008"]
GUARD_RAILS: dict[RuleId, str] = {
    "GR-001": "Different generational suffix (Jr and Sr) never auto-matches.",
    "GR-002": "Shared MBI with a DOB neither within one edit nor a month-day swap: "
    "IDENTITY_CONFLICT, never auto-matches.",
    "GR-003": "Shared phone or email alone (names and DOB not compatible) never auto-matches.",
    "GR-004": "Ambiguous identity key: two or more records share first name, last name, and DOB "
    "and some holder conflicts with another, so no pair on that key auto-matches. Conflicts "
    "between one person's own records (tied by MBI, phone, or email) do not count, but a "
    "different MBI (shared ids on) always counts and a shared street is not a tie.",
    "GR-005": "First names incompatible: not equal, not nicknames or an initial, and more than "
    "one typo apart (Patrick and Patricia), so the pair never auto-matches. Two known formal "
    "names (Mario and Maria), a name under five letters, or a changed ending (Andrew and "
    "Andrea) is never a typo.",
    "GR-006": "Birth year moved by more than one year through a digit transposition, with no "
    "MBI, phone, email, or street agreeing: never auto-matches.",
    "GR-007": "Name and DOB only: the pair agrees on nothing else (no MBI with shared ids, "
    "phone, email, street, or linking policy), so it never auto-matches.",
    "GR-008": "Name and birth date plus a shared street only: a household or care facility "
    "address is shared by many people, so it is not proof of one person; never auto-matches.",
}
# Rails that only stop an auto-match with an honest "unsure": the records may well be one person.
_UNSURE_RAILS: frozenset[RuleId] = frozenset({"GR-006", "GR-007", "GR-008"})
IdentityKey = tuple[str, str, str]
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


def independent_evidence(c: Comparison) -> bool:
    """True when MBI, phone, email, street, or a linking policy agrees."""
    return any(getattr(c, f) in levels for f, levels in INDEPENDENT_EVIDENCE_LEVELS.items())


def _name_dob_agree(c: Comparison) -> bool:
    """Names and DOB agree: equal, nickname, or a typo; close last name; close DOB."""
    first_ok = c.first in ("equal", "nickname") or (c.first == "close" and bool(c.first_typo))
    return first_ok and c.last in ("equal", "close") and c.dob in _CLOSE_DOB


def name_dob_only(c: Comparison) -> bool:
    """Names and DOB agree and nothing else does (GR-007)."""
    return _name_dob_agree(c) and not independent_evidence(c)


def name_dob_street_only(c: Comparison) -> bool:
    """Names and DOB agree, the street is the same, and no person evidence (MBI with shared
    ids, phone, email, linking policy) agrees (GR-008). Never true with name_dob_only."""
    person = any(getattr(c, f) in levels for f, levels in PERSON_EVIDENCE_LEVELS.items())
    return _name_dob_agree(c) and c.street == "same" and not person


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
    if c.first in ("close", "far") and not c.first_typo:
        hits.append("GR-005")  # a missing first name (None) never fires it
    far_year = (c.dob_years_apart or 0) > DOB_TRANSPOSITION_MAX_YEARS
    if c.dob == "transposition" and far_year and not independent_evidence(c):
        hits.append("GR-006")
    if name_dob_only(c):  # GR-007 (Alex, PR 10b): never auto-merges, whatever the book holds
        hits.append("GR-007")
    if name_dob_street_only(c):  # GR-008 (PR 21b): a shared street is household context
        hits.append("GR-008")
    return tuple(hits)


def identity_key(r: NormalizedRecord) -> IdentityKey | None:
    """Canonical first name, last name, DOB; None when any part is missing."""
    if r.first_name_canonical and r.last_name and r.dob_key:
        return (r.first_name_canonical, r.last_name, r.dob_key)
    return None


def _conflict(a: NormalizedRecord, b: NormalizedRecord, shared_ids: bool) -> bool:
    """Different MBI (ids on), different suffix, or different phone AND address AND email."""
    if shared_ids and a.mbi and b.mbi and a.mbi != b.mbi:
        return True
    if a.suffix and b.suffix and a.suffix != b.suffix:
        return True
    contact = [(a.phone, b.phone), (a.address_line1, b.address_line1), (a.email, b.email)]
    return all(x and y and x != y for x, y in contact)


def _mbi_differs(a: NormalizedRecord, b: NormalizedRecord) -> bool:
    """Both MBIs present and different. Only called with shared ids on."""
    return bool(a.mbi and b.mbi and a.mbi != b.mbi)


def _tied(x: NormalizedRecord, y: NormalizedRecord, shared_ids: bool) -> bool:
    """x and y are one person's records: an exact MBI (ids on), phone, or email."""
    return any(
        (f != "mbi" or shared_ids) and getattr(x, f) and getattr(x, f) == getattr(y, f)
        for f in OWN_RECORD_TIE_FIELDS
    )


def _tie_groups(rs: Sequence[NormalizedRecord], shared_ids: bool) -> list[int]:
    """Group label per record: records joined by a chain of ties are one person's records."""
    group = list(range(len(rs)))

    def root(i: int) -> int:
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i

    for i, j in combinations(range(len(rs)), 2):
        if _tied(rs[i], rs[j], shared_ids):
            a, b = root(i), root(j)
            if a != b:
                group[a] = b
    return [root(i) for i in range(len(rs))]


def ambiguous_keys(records: Sequence[NormalizedRecord], shared_ids: bool) -> set[IdentityKey]:
    """GR-004: identity keys held by two or more records where two holders conflict. Two
    holders tied together (directly or through a chain of ties) are one person's own records,
    so their conflict does not count (PR 10b): a person who moved is not ambiguous. With shared
    ids on, two different MBIs always conflict, whatever ties the holders (PR 21b)."""
    holders: dict[IdentityKey, list[NormalizedRecord]] = defaultdict(list)
    for r in records:
        if (k := identity_key(r)) is not None:
            holders[k].append(r)
    out = set()
    for k, rs in holders.items():
        if len(rs) < 2:
            continue
        g = _tie_groups(rs, shared_ids)
        if any(
            (shared_ids and _mbi_differs(rs[i], rs[j]))
            or (g[i] != g[j] and _conflict(rs[i], rs[j], shared_ids))
            for i, j in combinations(range(len(rs)), 2)
        ):
            out.add(k)
    return out


def decide(score: float, rails: tuple[RuleId, ...]) -> tuple[Decision, Suggestion | None]:
    """An identity conflict or an ambiguous key always goes to review. Other rails only stop an
    auto-match; a pair below the low line is still rejected, since rejecting merges no one."""
    if "GR-002" in rails:
        return "GRAY", "different_people"
    if "GR-004" in rails:
        return "GRAY", "unsure"
    if score < SCORE_LOW:
        return "AUTO_REJECT", None
    if score >= SCORE_HIGH and not rails:
        return "AUTO_MATCH", None
    if rails:
        return "GRAY", "unsure" if set(rails) <= _UNSURE_RAILS else "different_people"
    return "GRAY", "same_person" if score >= GRAY_SAME_PERSON_MIN else "unsure"


def score_pair(
    a: NormalizedRecord,
    b: NormalizedRecord,
    shared_ids: bool = True,
    ambiguous_key: bool = False,
) -> ScoredPair:
    """`ambiguous_key` is True when both records hold one GR-004 key (see ambiguous_keys)."""
    c = compare(a, b, shared_ids)
    rails = guard_rails(c) + (("GR-004",) if ambiguous_key else ())
    s = weighted_score(c)
    decision, suggestion = decide(s, rails)
    if suggestion == "same_person" and c.first not in ("equal", "nickname", "close"):
        suggestion = "unsure"  # never suggest one person when first names are incompatible
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
