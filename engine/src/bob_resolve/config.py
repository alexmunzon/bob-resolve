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
# at any of these comparison levels conflicts: every auto-match link on any path between them is
# held and the pairs go to review with CLUSTER_CONFLICT. Never resolved by picking.
CLUSTER_CONFLICT_LEVELS: Final[dict[str, frozenset[str]]] = {
    "first": frozenset({"far"}),
    "suffix": frozenset({"different"}),
    "dob": frozenset({"far"}),
}
# Rule id on every merge log line for a rules-arm auto-match (score at or above SCORE_HIGH and
# no guard rail). Split lines carry CLUSTER_CONFLICT.
AUTO_MATCH_RULE_ID: Final[str] = "AUTO-MATCH-HIGH"

# GR-005
# First names incompatible (docs/gr-005-notes.md). A pair never auto-matches unless its first
# names are compatible (equal, a shared formal name, or an initial), within this many
# Damerau-Levenshtein edits (a typo), or one is missing. Jaro-Winkler alone rates Patrick and
# Patricia close; opposite-sex twins would otherwise auto-merge.
FIRST_NAME_TYPO_MAX_EDITS: Final[int] = 1

# PR 7
# Run command. Jev is not built yet, so a run records it as off with zero calls and zero cost,
# and every gray pair goes to the review queue (SPEC example 8). PR 12: the LLM tier is a run
# option (--llm-mode, default off) that only replays saved explanations offline; it never
# changes a decision, so gray pairs still go to the review queue.
RUN_JEV_MODE: Final[Literal["off"]] = "off"
# Rule id on a merge log line for a pair a human decided "same person" (review apply).
REVIEW_RULE_ID: Final[str] = "REVIEW-DECISION"

# Release 0.1.0
# Characters of an MBI left visible wherever it is masked (review queue, public demo).
MBI_VISIBLE_CHARS: Final[int] = 4
# A run written under a folder with one of these names is public (the dashboard serves it), so
# the run refuses to write there unless the MBI is masked (--mask-mbi).
PUBLIC_FOLDER_NAMES: Final[frozenset[str]] = frozenset({"public"})

# Review 2
# False-merge holes closed in review 2 (docs/review-2-score-notes.md). Orchestrator decisions
# F1 to F4 and F8; SPEC decision 2: a false merge is worse than a missed match.
# F1 and F4: one edit between two first names is not a typo when both are known formal given
# names (a formal name in the nickname table, or this curated list), or when either name is
# shorter than FIRST_NAME_TYPO_MIN_LENGTH letters. Mario and Maria are two people, not a typo.
FORMAL_GIVEN_NAMES: Final[frozenset[str]] = frozenset(
    {"mario", "maria", "dan", "dana", "mary", "mark", "jon", "jan", "eric", "erica", "paul",
     "paula", "carl", "carla", "carol", "dean", "diane", "denis", "denise", "louise", "gene",
     "jane", "june", "joan", "jean", "julian", "julia", "julie", "anna", "nina", "tina", "gina",
     # PR 10b: distinct given names one edit apart away from the end, written by hand
     "francis", "frances", "jesse", "jessie", "marion", "marian", "jason", "mason", "larry",
     "harry", "barry", "terry", "jerry", "kerry", "allen", "ellen", "allan", "kevin", "devin",
     "holly", "molly", "polly", "dolly", "cindy", "mindy", "lance", "vance", "bruce", "bryce",
     "karen", "caren", "helen", "helena", "brenda", "brenna"}
)  # fmt: skip
# PR 10b (GR-005, orchestrator): an edit that touches the last letter, where either name ends in
# one of these letters, is a different name, not a typo (Andrew and Andrea, Dan and Dana, Louis
# and Louise, Christian and Christina): opposite-sex look-alikes often differ only at the end.
LOOK_ALIKE_FINAL_LETTERS: Final[frozenset[str]] = frozenset("aeiouy")
FIRST_NAME_TYPO_MIN_LENGTH: Final[int] = 5
# F2: a DOB is "close" only by an adjacent-digit transposition, a month-day swap, or one changed
# digit in the month or day (YYYYMMDD index 4 and up). A changed year digit is "far".
DOB_SUBSTITUTION_MIN_INDEX: Final[int] = 4
# GR-006: a transposition that moves the birth year by more than this many years cannot
# auto-match without independent evidence.
DOB_TRANSPOSITION_MAX_YEARS: Final[int] = 1
# Independent evidence: a field beyond name and DOB whose agreement ties two records together
# (GR-006, GR-007). Only an exact street counts: a "close" street can be a neighbor's house.
# PR 10b (Alex, GR-007): a linking policy (the same policy id or carrier member id) counts too.
# Like MBI it is a shared id, so "no shared ids" mode withholds it (SPEC section 5).
INDEPENDENT_EVIDENCE_LEVELS: Final[dict[str, frozenset[str]]] = {
    "mbi": frozenset({"same"}),
    "phone": frozenset({"same"}),
    "email": frozenset({"same"}),
    "street": frozenset({"same"}),
    "policy": frozenset({"same"}),
}
# PR 21b (GR-008): a street is household context. A home or care facility is shared by many
# people, so street stays independent evidence (GR-006, GR-007) but is not person evidence:
# name and DOB plus a shared street and no person evidence never auto-matches.
HOUSEHOLD_CONTEXT_FIELDS: Final[frozenset[str]] = frozenset({"street"})
PERSON_EVIDENCE_LEVELS: Final[dict[str, frozenset[str]]] = {
    f: levels
    for f, levels in INDEPENDENT_EVIDENCE_LEVELS.items()
    if f not in HOUSEHOLD_CONTEXT_FIELDS
}
# PR 10b (GR-004, orchestrator): a holder tied to a pair record by one of these exact fields is
# that person's own record, so its conflicts with the pair's other own records are not ambiguity
# (a person who moved). MBI ties only when shared ids are on. PR 21c: a shared street no longer
# ties (household context), and a differing MBI (ids on) is never excused by any tie.
OWN_RECORD_TIE_FIELDS: Final[tuple[str, ...]] = ("mbi", "phone", "email")
