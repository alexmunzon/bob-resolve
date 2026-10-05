"""Score every candidate pair and measure the SPEC decision 2 targets against the answer key."""

from collections import Counter
from collections.abc import Sequence

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.rules import GUARD_RAILS, ScoredPair, score_pair
from bob_resolve.truth import AnswerKey


def withhold_shared_ids(records: Sequence[NormalizedRecord]) -> list[NormalizedRecord]:
    """No shared ids mode: MBI is nulled on the records themselves, so no feature can see it.
    Policy number never reaches a NormalizedRecord, so it needs no withholding."""
    return [r.model_copy(update={"mbi": None}) for r in records]


def score_candidates(
    records: Sequence[NormalizedRecord], pairs: pl.DataFrame, shared_ids: bool
) -> list[ScoredPair]:
    by_id = {r.record_id: r for r in (records if shared_ids else withhold_shared_ids(records))}
    return [
        score_pair(by_id[a], by_id[b], shared_ids) for a, b in pairs.select("a", "b").iter_rows()
    ]


class ScoreReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    shared_ids: bool
    true_pairs: int
    auto_match: int
    auto_match_true: int
    gray: int
    gray_same_person_true: int
    auto_reject: int
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


def evaluate_scores(scored: Sequence[ScoredPair], key: AnswerKey, shared_ids: bool) -> ScoreReport:
    """A true pair is found if auto-matched or gray with "same person" (SPEC decision 2).

    Unresolved rows sit in no cluster, so they are in no true pair; any auto-match that touches
    one is a false merge and is also counted on its own."""
    truth = key.pairs
    unresolved = {u.record_id for u in key.unresolved}
    decisions = Counter(p.decision for p in scored)
    matched = [p for p in scored if p.decision == "AUTO_MATCH"]
    found = {
        (p.a, p.b)
        for p in scored
        if p.decision == "AUTO_MATCH" or (p.decision == "GRAY" and p.suggestion == "same_person")
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
        unresolved_auto_matched=sum(p.a in unresolved or p.b in unresolved for p in matched),
        guard_rail_hits={r: rails[r] for r in GUARD_RAILS},
        false_merges=tuple(sorted((p.a, p.b) for p in matched if (p.a, p.b) not in truth)),
        missed=tuple(sorted(truth - found)),
    )
