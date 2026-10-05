"""DOB comparison features on YYYYMMDD strings; they feed the "more than one edit" guard rail."""

from datetime import date

import jellyfish


def dob_key(d: date | None) -> str | None:
    return d.strftime("%Y%m%d") if d else None


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
