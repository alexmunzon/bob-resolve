"""Typed settings for bob-resolve.

Placeholders only. The scoring cutoffs (auto-match and auto-reject lines) and the guard rails
land in PR 5, with tests. Guard rails always win: no Jev or LLM answer may override them.
"""

from typing import Final, Literal

JevMode = Literal["off", "replay", "live", "record"]

# Jev and LLM default to replay or off. live and record spend money and need Alex's yes each time.
DEFAULT_JEV_MODE: Final[JevMode] = "replay"
LLM_ARM_ENABLED: Final[bool] = False

# Error policy targets from SPEC decision 2: a false merge is worse than a missed match.
TARGET_AUTO_MERGE_PRECISION: Final[float] = 0.99
TARGET_RECALL_AFTER_REVIEW: Final[float] = 0.90
TARGET_BLOCKING_RECALL: Final[float] = 0.98

# Jev recording cap per session, in US dollars (SPEC decision 3).
JEV_RECORD_CAP_USD: Final[float] = 0.50

# Two-digit birth years pivot at 1930, as in agency-intake-kit (SPEC section 5).
TWO_DIGIT_YEAR_PIVOT: Final[int] = 1930
