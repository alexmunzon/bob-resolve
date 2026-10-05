"""Typed settings for bob-resolve.

Placeholders only. The scoring cutoffs (auto-match and auto-reject lines) and the guard rails
land in PR 5, with tests. Guard rails always win: no Jev or LLM answer may override them.
"""

from datetime import date
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

# PR 3
# Generational suffixes split out of either name field into their own field, never dropped.
GENERATIONAL_SUFFIXES: Final[frozenset[str]] = frozenset(
    {"jr", "sr", "ii", "iii", "iv", "v", "2nd", "3rd"}
)
# A US phone is 10 digits; an 11-digit number starting with the country code 1 is trimmed.
PHONE_DIGITS: Final[int] = 10
US_COUNTRY_CODE: Final[str] = "1"

# PR 4
# Blocking uses MBI only when shared ids are allowed. "No shared ids" mode (SPEC section 5)
# withholds MBI and policy number from blocking and scoring, because they match across files.
SHARED_IDS_DEFAULT: Final[bool] = True

# Review 1
# A blocking key value shared by more records than this is dropped from that key and reported,
# so one shared agency phone or common surname cannot explode the candidate set.
MAX_BLOCK_SIZE: Final[int] = 50
# Placeholder values staff type when the real one is unknown. They become None at normalize time.
PLACEHOLDER_PHONES: Final[frozenset[str]] = frozenset({"1234567890", "0123456789"})
# Any phone made of one digit repeated (0000000000, 5555555555, ...) is also a placeholder.
PLACEHOLDER_EMAIL_LOCALS: Final[frozenset[str]] = frozenset(
    {"none", "noemail", "no-email", "na", "n/a", "test", "unknown", "noreply"}
)
PLACEHOLDER_DOBS: Final[frozenset[date]] = frozenset({date(1900, 1, 1), date(1901, 1, 1)})
# A birth date that makes the person younger or older than this at as_of is flagged implausible.
MIN_PLAUSIBLE_AGE: Final[int] = 18
MAX_PLAUSIBLE_AGE: Final[int] = 120
# Fixed "today" for the CLI, so runs are repeatable. Library code always takes as_of explicitly.
DEFAULT_AS_OF: Final[date] = date(2026, 10, 1)
