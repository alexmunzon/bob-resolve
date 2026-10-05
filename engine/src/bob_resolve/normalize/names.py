"""Name cleanup, generational suffix split, nickname table, and surname phonetic key."""

import csv
import re
import unicodedata
from functools import cache
from pathlib import Path

import jellyfish

from bob_resolve.config import GENERATIONAL_SUFFIXES

NICKNAMES_CSV = Path(__file__).resolve().parents[1] / "data" / "nicknames.csv"
_DROP = re.compile(r"['’.]")
_TO_SPACE = re.compile(r"[^\w\s]|_")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(raw: str | None) -> str | None:
    """Casefold, strip accents, drop apostrophes and periods, other punctuation to spaces."""
    if raw is None:
        return None
    s = _TO_SPACE.sub(" ", _DROP.sub("", strip_accents(raw).casefold()))
    return " ".join(s.split()) or None


def _pop_suffix(name: str | None) -> tuple[str | None, str | None]:
    tokens = (name or "").split()
    if len(tokens) > 1 and tokens[-1] in GENERATIONAL_SUFFIXES:
        return " ".join(tokens[:-1]), tokens[-1]
    return name, None


def split_suffix(first: str | None, last: str | None) -> tuple[str | None, str | None, str | None]:
    """Return (first, last, suffix). The last name's suffix wins; a different one stays in first."""
    last_n, suffix = _pop_suffix(normalize_name(last))
    first_n, first_suffix = _pop_suffix(normalize_name(first))
    if first_suffix is not None and suffix not in (None, first_suffix):
        return normalize_name(first), last_n, suffix
    return first_n, last_n, suffix or first_suffix


@cache
def _nickname_table() -> dict[str, frozenset[str]]:
    table: dict[str, set[str]] = {}
    with NICKNAMES_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            nick, canon = normalize_name(row["nickname"]), normalize_name(row["canonical"])
            if nick and canon:
                table.setdefault(nick, set()).add(canon)
    return {k: frozenset(v) for k, v in table.items()}


def canonical_names(name: str | None) -> frozenset[str]:
    """Every formal name this given name may stand for, itself included."""
    n = normalize_name(name)
    if n is None:
        return frozenset()
    return _nickname_table().get(n, frozenset()) | {n}


def canonical_first_name(name: str | None) -> str | None:
    """One formal name for blocking and display: the alphabetically first canonical, or itself."""
    n = normalize_name(name)
    if n is None:
        return None
    return min(_nickname_table().get(n, {n}))


def names_compatible(a: str | None, b: str | None) -> bool:
    """Equal, nicknames sharing a formal name, or one is the initial of the other."""
    na, nb = normalize_name(a), normalize_name(b)
    if na is None or nb is None:
        return False
    if na == nb or canonical_names(na) & canonical_names(nb):
        return True
    short, long_ = sorted((na, nb), key=len)
    return len(short) == 1 and long_.startswith(short)


def surname_key(last: str | None) -> str | None:
    """Phonetic key of a normalized surname, spaces removed. Metaphone: see docs/pr-3-notes.md."""
    n = normalize_name(last)
    if n is None:
        return None
    return jellyfish.metaphone(n.replace(" ", "")) or None
