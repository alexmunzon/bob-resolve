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

# PR 5
# Rules arm scoring (SPEC 6 step 3). Hand-tuned, not learned: tuned on the snapshot and the
# derived side, never on the hard cases (docs/pr-5-notes.md). Each comparison level adds its
# weight to a log-odds total; the score is the logistic of that total, so it lies in [0, 1].
# A missing value on either side adds nothing. Policy number is never a scoring feature.
NAME_CLOSE_JARO_WINKLER: Final[float] = 0.90
STREET_CLOSE_JARO_WINKLER: Final[float] = 0.90
SCORE_BIAS: Final[float] = -4.0
SCORE_WEIGHTS: Final[dict[str, dict[str, float]]] = {
    "first": {"equal": 3.0, "nickname": 2.5, "close": 1.5, "far": -3.0},
    "last": {"equal": 3.0, "close": 2.0, "far": -3.0},
    "suffix": {"same": 0.0, "one_missing": 0.0, "different": -3.0},
    "dob": {
        "exact": 4.0,
        "transposition": 2.5,
        "month_day_swap": 2.5,
        "one_edit": 2.0,
        "far": -5.0,
    },
    "mbi": {"same": 4.0, "different": -6.0},
    "zip5": {"same": 0.5, "different": -0.5},
    "street": {"same": 1.0, "close": 0.5, "different": -0.5},
    "phone": {"same": 1.0, "different": -0.25},
    "email": {"same": 1.0, "different": -0.25},
}
# At or above HIGH: auto-match (unless a guard rail stops it). Below LOW: auto-reject.
SCORE_HIGH: Final[float] = 0.99
SCORE_LOW: Final[float] = 0.10
# A gray pair is suggested "same person" for review when its score is at least this line and no
# guard rail fired. Recall after review counts those plus auto-matches (SPEC decision 2).
GRAY_SAME_PERSON_MIN: Final[float] = (SCORE_HIGH + SCORE_LOW) / 2

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

# PR 6
# Survivorship (SPEC decision 4). Identity fields (legal first and last name, suffix, DOB, MBI)
# come from the most authoritative source: lower rank wins. Contact fields (address, phone,
# email) come from the most recent record (docs/pr-6-notes.md defines "most recent").
SOURCE_AUTHORITY: Final[dict[str, int]] = {"enrollment": 0, "crm": 1}
# Only these sources count as authoritative: if two of their records in one cluster disagree on
# DOB or MBI, the field is left empty and the person goes to review with IDENTITY_CONFLICT.
AUTHORITATIVE_SOURCES: Final[frozenset[str]] = frozenset({"enrollment"})
# Every record pair inside one cluster is re-checked (nickname chains are not transitive). A pair
# at any of these comparison levels conflicts: the cluster is split at its weakest auto-match
# links and the pairs go to review with CLUSTER_CONFLICT. Never resolved by picking.
CLUSTER_CONFLICT_LEVELS: Final[dict[str, frozenset[str]]] = {
    "first": frozenset({"far"}),
    "suffix": frozenset({"different"}),
    "dob": frozenset({"far"}),
}
# Rule id on every merge log line for a rules-arm auto-match (score at or above SCORE_HIGH and
# no guard rail). Split lines carry CLUSTER_CONFLICT.
AUTO_MATCH_RULE_ID: Final[str] = "AUTO-MATCH-HIGH"

# PR 7
# Run command. Jev and the LLM arm are not built yet, so a run records them as off with zero
# calls and zero cost, and every gray pair goes to the review queue (SPEC example 8).
RUN_JEV_MODE: Final[Literal["off"]] = "off"
RUN_LLM_MODE: Final[Literal["off"]] = "off"
# Rule id on a merge log line for a pair a human decided "same person" (review apply).
REVIEW_RULE_ID: Final[str] = "REVIEW-DECISION"
