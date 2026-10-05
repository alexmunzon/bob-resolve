"""Blocking (SPEC 6, step 2): cheap keys that pick which record pairs are worth scoring."""

from bob_resolve.block.candidates import (
    ALL_KEYS,
    SHARED_ID_KEYS,
    BlockingReport,
    candidate_pairs,
    evaluate,
)

__all__ = ["ALL_KEYS", "SHARED_ID_KEYS", "BlockingReport", "candidate_pairs", "evaluate"]
