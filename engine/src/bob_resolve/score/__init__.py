"""Scoring, the two cutoffs, and the guard rails (SPEC 6 step 3, the rules arm)."""

from bob_resolve.score.compare import Comparison, compare
from bob_resolve.score.evaluate import (
    ScoreReport,
    evaluate_scores,
    score_candidates,
    withhold_shared_ids,
)
from bob_resolve.score.rules import GUARD_RAILS, ScoredPair, decide, guard_rails, score_pair

__all__ = [
    "GUARD_RAILS",
    "Comparison",
    "ScoreReport",
    "ScoredPair",
    "compare",
    "decide",
    "evaluate_scores",
    "guard_rails",
    "score_candidates",
    "score_pair",
    "withhold_shared_ids",
]
