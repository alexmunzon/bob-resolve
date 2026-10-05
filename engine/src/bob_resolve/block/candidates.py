"""Candidate pairs from blocking keys, built with polars joins (no Python pair loops).

Any shared key value puts a pair in the candidate set. Every pair is (a, b) with a < b as
strings, the same order as the answer key, and lists the keys that produced it.
"""

from collections.abc import Sequence

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.config import SHARED_IDS_DEFAULT
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.truth import AnswerKey

_LAST_INITIAL = pl.col("last_name").str.slice(0, 1)
_DOB = pl.col("dob_key")
_SURNAME = pl.col("last_name_key")

# SPEC keys first, then the birth date variant keys chosen in docs/pr-4-notes.md.
KEY_EXPRESSIONS: dict[str, pl.Expr] = {
    "mbi": pl.col("mbi"),
    "email": pl.col("email"),
    "phone": pl.col("phone"),
    "dob_last_initial": pl.concat_str(_DOB, _LAST_INITIAL, separator="|"),
    "surname_zip3": pl.concat_str(_SURNAME, pl.col("zip3"), separator="|"),
    # Same eight digits in any order: catches a digit transposition and a month-day swap.
    "dob_digits_last_initial": pl.concat_str(
        _DOB.str.split("").list.sort().list.join(""), _LAST_INITIAL, separator="|"
    ),
    # Same surname sound and birth month and day: catches a wrong or mistyped birth year.
    "surname_birth_month_day": pl.concat_str(_SURNAME, _DOB.str.slice(4, 4), separator="|"),
}
ALL_KEYS: tuple[str, ...] = tuple(KEY_EXPRESSIONS)
SHARED_ID_KEYS: frozenset[str] = frozenset({"mbi"})
_FIELDS = ["record_id", "last_name", "last_name_key", "dob_key", "mbi", "phone", "email", "zip3"]


def active_keys(shared_ids: bool) -> tuple[str, ...]:
    return tuple(k for k in ALL_KEYS if shared_ids or k not in SHARED_ID_KEYS)


def candidate_pairs(
    records: Sequence[NormalizedRecord], shared_ids: bool = SHARED_IDS_DEFAULT
) -> pl.DataFrame:
    """Columns a, b, keys (sorted list of key names). Null key values never match."""
    keys = active_keys(shared_ids)
    base = pl.DataFrame(
        [r.model_dump(include=set(_FIELDS)) for r in records],
        schema={f: pl.String for f in _FIELDS},
    )
    long = (
        base.select("record_id", *(KEY_EXPRESSIONS[k].alias(k) for k in keys))
        .unpivot(index="record_id", variable_name="key", value_name="value")
        .drop_nulls("value")
    )
    return (
        long.join(long, on=["key", "value"], suffix="_b")
        .filter(pl.col("record_id") < pl.col("record_id_b"))
        .group_by(a="record_id", b="record_id_b")
        .agg(pl.col("key").unique().sort().alias("keys"))
        .sort("a", "b")
    )


class BlockingReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    shared_ids: bool
    n_records: int
    all_pairs: int
    candidate_pairs: int
    true_pairs: int
    found_pairs: int
    recall_per_key: dict[str, float]
    missed_examples: tuple[tuple[str, str], ...]

    @property
    def recall(self) -> float:
        return self.found_pairs / self.true_pairs if self.true_pairs else 1.0

    @property
    def reduction_ratio(self) -> float:
        """Share of all possible pairs that blocking skips."""
        return 1 - self.candidate_pairs / self.all_pairs if self.all_pairs else 0.0


def evaluate(
    pairs: pl.DataFrame, key: AnswerKey, n_records: int, shared_ids: bool = SHARED_IDS_DEFAULT
) -> BlockingReport:
    """Blocking recall against the pair answer key, overall and per key."""
    truth = pl.DataFrame(sorted(key.pairs), schema=["a", "b"], orient="row")
    hit = truth.join(pairs, on=["a", "b"], how="left")
    found = hit.filter(pl.col("keys").is_not_null())
    per_key = {
        k: found.filter(pl.col("keys").list.contains(k)).height / max(truth.height, 1)
        for k in active_keys(shared_ids)
    }
    missed = hit.filter(pl.col("keys").is_null()).select("a", "b").rows()
    return BlockingReport(
        shared_ids=shared_ids,
        n_records=n_records,
        all_pairs=n_records * (n_records - 1) // 2,
        candidate_pairs=pairs.height,
        true_pairs=truth.height,
        found_pairs=found.height,
        recall_per_key=per_key,
        missed_examples=tuple(missed),
    )
