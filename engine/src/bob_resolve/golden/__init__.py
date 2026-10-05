"""Golden records (SPEC 6 step 6 and decision 4): survivorship, aliases, per-field provenance."""

from bob_resolve.golden.resolve import Resolution, ReviewItem, resolve
from bob_resolve.golden.survivorship import GOLDEN_FIELDS, FieldSource, GoldenPerson, build_golden

__all__ = [
    "GOLDEN_FIELDS",
    "FieldSource",
    "GoldenPerson",
    "Resolution",
    "ReviewItem",
    "build_golden",
    "resolve",
]
