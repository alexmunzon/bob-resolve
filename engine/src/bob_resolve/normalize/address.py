"""Address cleanup: uppercase, no punctuation, USPS street suffix and unit abbreviations."""

import re

from bob_resolve.normalize.names import strip_accents

# A small subset of USPS Publication 28 (street suffixes, appendix C1; units, appendix C2).
USPS_ABBREVIATIONS: dict[str, str] = {
    "AVENUE": "AVE", "BOULEVARD": "BLVD", "CIRCLE": "CIR", "COURT": "CT", "DRIVE": "DR",
    "EXPRESSWAY": "EXPY", "GARDEN": "GDN", "GARDENS": "GDNS", "HIGHWAY": "HWY", "LANE": "LN",
    "PARKWAY": "PKWY", "PLACE": "PL", "ROAD": "RD", "SQUARE": "SQ", "STREET": "ST",
    "TERRACE": "TER", "TRAIL": "TRL", "APARTMENT": "APT", "BUILDING": "BLDG", "FLOOR": "FL",
    "ROOM": "RM", "SUITE": "STE",
}  # fmt: skip
_PUNCT = re.compile(r"[^\w\s]|_")


def normalize_address(raw: str | None) -> str | None:
    if raw is None:
        return None
    tokens = _PUNCT.sub(" ", strip_accents(raw).upper()).split()
    return " ".join(USPS_ABBREVIATIONS.get(t, t) for t in tokens) or None


def zip5(raw: str | None) -> str | None:
    """First five digits of a 5 or 9 digit ZIP; anything else is None (never padded)."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[:5] if len(digits) in (5, 9) else None


def zip3(raw: str | None) -> str | None:
    z = zip5(raw)
    return z[:3] if z else None
