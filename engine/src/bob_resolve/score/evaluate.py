"""Score every candidate pair and measure the SPEC decision 2 targets against the answer key."""

from collections import Counter
from collections.abc import Collection, Sequence

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.rules import (
    GUARD_RAILS,
    ScoredPair,
    ambiguous_keys,
    identity_key,
    score_pair,
)
from bob_resolve.truth import AnswerKey


def withhold_shared_ids(records: Sequence[NormalizedRecord]) -> list[NormalizedRecord]:
    """No shared ids mode: MBI and the linking policies are removed from the records
    themselves, so no feature can see them."""
    return [r.model_copy(update={"mbi": None, "policy_keys": None}) for r in records]


def score_candidates(
    records: Sequence[NormalizedRecord], pairs: pl.DataFrame, shared_ids: bool
) -> list[ScoredPair]:
    recs = records if shared_ids else withhold_shared_ids(records)
    by_id, ambiguous = {r.record_id: r for r in recs}, ambiguous_keys(recs, shared_ids)

    def on_ambiguous_key(a: NormalizedRecord, b: NormalizedRecord) -> bool:
        k = identity_key(a)
        return k is not None and k == identity_key(b) and k in ambiguous

    out = []
    for a, b in pairs.select("a", "b").iter_rows():
        ra, rb = by_id[a], by_id[b]
        out.append(score_pair(ra, rb, shared_ids, on_ambiguous_key(ra, rb)))
    return out


class ScoreReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    shared_ids: bool
    true_pairs: int
    auto_match: int
    auto_match_true: int
    gray: int
    gray_same_person_true: int
    auto_reject: int
    cut_by_cluster: int = 0
    unresolved_auto_matched: int
    guard_rail_hits: dict[str, int]
    false_merges: tuple[tuple[str, str], ...]
    missed: tuple[tuple[str, str], ...]

    @property
    def auto_merge_precision(self) -> float:
        return self.auto_match_true / self.auto_match if self.auto_match else 1.0

    @property
    def recall_after_review(self) -> float:
        found = self.auto_match_true + self.gray_same_person_true
        return found / self.true_pairs if self.true_pairs else 1.0


def evaluate_scores(
    scored: Sequence[ScoredPair],
    key: AnswerKey,
    shared_ids: bool,
    kept: Collection[tuple[str, str]] | None = None,
) -> ScoreReport:
    """A true pair is found if auto-matched or gray with "same person" (SPEC decision 2).

    Review 2 (F8): pass `kept`, the final merge edges after cluster splits, and precision and
    recall are measured on them. An auto-match cut by a cluster conflict is not a merge, and it
    is not found: its CLUSTER_CONFLICT queue item suggests "different people". Without `kept`
    every auto-match counts (the score stage alone, before clustering).

    Unresolved rows sit in no cluster, so they are in no true pair; any auto-match that touches
    one is a false merge and is also counted on its own."""
    truth = key.pairs
    unresolved = {u.record_id for u in key.unresolved}
    decisions = Counter(p.decision for p in scored)
    auto = [p for p in scored if p.decision == "AUTO_MATCH"]
    final = set(kept) if kept is not None else {(p.a, p.b) for p in auto}
    matched = [p for p in auto if (p.a, p.b) in final]
    found = {(p.a, p.b) for p in matched} | {
        (p.a, p.b) for p in scored if p.decision == "GRAY" and p.suggestion == "same_person"
    }
    rails = Counter(r for p in scored for r in p.guard_rails)
    return ScoreReport(
        shared_ids=shared_ids,
        true_pairs=len(truth),
        auto_match=len(matched),
        auto_match_true=sum((p.a, p.b) in truth for p in matched),
        gray=decisions["GRAY"],
        gray_same_person_true=len((found & truth) - {(p.a, p.b) for p in matched}),
        auto_reject=decisions["AUTO_REJECT"],
        cut_by_cluster=len(auto) - len(matched),
        unresolved_auto_matched=sum(p.a in unresolved or p.b in unresolved for p in matched),
        guard_rail_hits={r: rails[r] for r in GUARD_RAILS},
        false_merges=tuple(sorted((p.a, p.b) for p in matched if (p.a, p.b) not in truth)),
        missed=tuple(sorted(truth - found)),
    )
