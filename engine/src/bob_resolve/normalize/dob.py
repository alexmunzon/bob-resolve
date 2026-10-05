"""DOB comparison features on YYYYMMDD strings; they feed the "more than one edit" guard rail."""

from datetime import date

import jellyfish

from bob_resolve.config import PLACEHOLDER_DOBS


def dob_key(d: date | None) -> str | None:
    """YYYYMMDD, or None for a missing or placeholder date (1900-01-01 never blocks or matches)."""
    return d.strftime("%Y%m%d") if d and d not in PLACEHOLDER_DOBS else None


def age_on(d: date, as_of: date) -> int:
    """Whole years from d to as_of."""
    return as_of.year - d.year - ((as_of.month, as_of.day) < (d.month, d.day))


def is_transposition(a: str, b: str) -> bool:
    """True when b is a with exactly two adjacent, different digits swapped."""
    if len(a) != len(b):
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and (a[d[0]], a[d[1]]) == (b[d[1]], b[d[0]])


def is_month_day_swap(a: str, b: str) -> bool:
    """True when the years match and month and day trade places (19511210 and 19511012)."""
    return a != b and a[:4] == b[:4] and a[4:6] == b[6:8] and a[6:8] == b[4:6]


def dob_edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance: an adjacent swap counts as one edit."""
    return jellyfish.damerau_levenshtein_distance(a, b)
