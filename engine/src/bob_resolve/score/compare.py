"""Comparison vector for one record pair (SPEC 6 step 3). Each field gets a level, or None."""

from typing import Literal

import jellyfish
from pydantic import BaseModel, ConfigDict

from bob_resolve.config import (
    FIRST_NAME_TYPO_MAX_EDITS,
    NAME_CLOSE_JARO_WINKLER,
    STREET_CLOSE_JARO_WINKLER,
)
from bob_resolve.normalize.dob import dob_edit_distance, is_month_day_swap, is_transposition
from bob_resolve.normalize.names import names_compatible
from bob_resolve.normalize.record import NormalizedRecord

DobLevel = Literal["exact", "transposition", "month_day_swap", "one_edit", "far"]
Same = Literal["same", "different"]
FirstLevel = Literal["equal", "nickname", "close", "far"]
LastLevel = Literal["equal", "close", "far"]
StreetLevel = Literal["same", "close", "different"]
SuffixLevel = Literal["same", "one_missing", "different"]


class Comparison(BaseModel):
    """Levels per field; None means a value is missing on either side (or MBI is withheld)."""

    model_config = ConfigDict(frozen=True)

    first_jw: float | None
    first: FirstLevel | None
    first_typo: bool | None = None  # within FIRST_NAME_TYPO_MAX_EDITS Damerau-Levenshtein edits
    last_jw: float | None
    last_metaphone_equal: bool | None
    last: LastLevel | None
    suffix: SuffixLevel | None
    dob: DobLevel | None
    mbi: Same | None
    zip5: Same | None
    street: StreetLevel | None
    phone: Same | None
    email: Same | None


def _same(a: str | None, b: str | None) -> Same | None:
    if a is None or b is None:
        return None
    return "same" if a == b else "different"


def dob_level(a: str | None, b: str | None) -> DobLevel | None:
    if a is None or b is None:
        return None
    if a == b:
        return "exact"
    if is_transposition(a, b):
        return "transposition"
    if is_month_day_swap(a, b):
        return "month_day_swap"
    return "one_edit" if dob_edit_distance(a, b) <= 1 else "far"


def compare(a: NormalizedRecord, b: NormalizedRecord, shared_ids: bool = True) -> Comparison:
    first_jw: float | None = None
    last_jw: float | None = None
    metaphone_eq: bool | None = None
    first: FirstLevel | None = None
    first_typo: bool | None = None
    last: LastLevel | None = None
    suffix: SuffixLevel | None = None
    street: StreetLevel | None = None
    if a.first_name and b.first_name:
        first_jw = jellyfish.jaro_winkler_similarity(a.first_name, b.first_name)
        edits = jellyfish.damerau_levenshtein_distance(a.first_name, b.first_name)
        first_typo = edits <= FIRST_NAME_TYPO_MAX_EDITS
        if a.first_name == b.first_name:
            first = "equal"
        elif names_compatible(a.first_name, b.first_name):
            first = "nickname"
        else:
            first = "close" if first_jw >= NAME_CLOSE_JARO_WINKLER else "far"
    if a.last_name and b.last_name:
        last_jw = jellyfish.jaro_winkler_similarity(a.last_name, b.last_name)
        metaphone_eq = a.last_name_key is not None and a.last_name_key == b.last_name_key
        if a.last_name == b.last_name:
            last = "equal"
        else:
            last = "close" if metaphone_eq or last_jw >= NAME_CLOSE_JARO_WINKLER else "far"
    if a.suffix or b.suffix:
        suffix = "one_missing" if not (a.suffix and b.suffix) else _same(a.suffix, b.suffix)
    if a.address_line1 and b.address_line1:
        jw = jellyfish.jaro_winkler_similarity(a.address_line1, b.address_line1)
        same = a.address_line1 == b.address_line1
        street = "same" if same else "close" if jw >= STREET_CLOSE_JARO_WINKLER else "different"
    return Comparison(
        first_jw=first_jw,
        first=first,
        first_typo=first_typo,
        last_jw=last_jw,
        last_metaphone_equal=metaphone_eq,
        last=last,
        suffix=suffix,
        dob=dob_level(a.dob_key, b.dob_key),
        mbi=_same(a.mbi, b.mbi) if shared_ids else None,
        zip5=_same(a.zip5, b.zip5),
        street=street,
        phone=_same(a.phone, b.phone),
        email=_same(a.email, b.email),
    )
