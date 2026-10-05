"""Candidate pairs from blocking keys, built with polars joins (no Python pair loops).

Any shared key value puts a pair in the candidate set. Every pair is (a, b) with a < b as
strings, the same order as the answer key, and lists the keys that produced it. A key value
shared by more than MAX_BLOCK_SIZE records is dropped from that key and reported (Review 1).
"""

import hashlib
from collections.abc import Sequence

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.config import MAX_BLOCK_SIZE, SHARED_IDS_DEFAULT
from bob_resolve.normalize.names import canonical_names
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
# Every formal first name the given name may stand for, plus the full DOB: pairs people whose
# surname changed (maiden, married, hyphenated). Built from a list column, see _long_values.
FIRST_NAME_DOB = "first_name_dob"
# FROZEN after Review 1. Phase 2 measures exactly this blocker; tests/unit/test_review_1.py pins
# the list. Adding or removing a key needs a new review and new recall numbers in the notes.
ALL_KEYS: tuple[str, ...] = (*KEY_EXPRESSIONS, FIRST_NAME_DOB)
SHARED_ID_KEYS: frozenset[str] = frozenset({"mbi"})
_FIELDS = ["record_id", "last_name", "last_name_key", "dob_key", "mbi", "phone", "email", "zip3"]
_FIELDS += ["first_name"]


class DroppedBlock(BaseModel):
    """A key value too common to block on. The value is masked: only a hash prefix is shown."""

    model_config = ConfigDict(frozen=True)

    key: str
    value_masked: str
    size: int


def active_keys(shared_ids: bool) -> tuple[str, ...]:
    return tuple(k for k in ALL_KEYS if shared_ids or k not in SHARED_ID_KEYS)


def _long_values(records: Sequence[NormalizedRecord], shared_ids: bool) -> pl.DataFrame:
    """One row per (record_id, key, value), nulls dropped."""
    keys = [k for k in active_keys(shared_ids) if k != FIRST_NAME_DOB]
    base = pl.DataFrame(
        [r.model_dump(include=set(_FIELDS)) for r in records],
        schema={f: pl.String for f in _FIELDS},
    )
    names = pl.Series(
        "first_names", [sorted(canonical_names(r.first_name)) for r in records], pl.List(pl.String)
    )
    first_dob = (
        base.with_columns(names)
        .explode("first_names", empty_as_null=True)
        .select(
            "record_id",
            pl.lit(FIRST_NAME_DOB).alias("key"),
            pl.concat_str(pl.col("first_names"), _DOB, separator="|").alias("value"),
        )
    )
    scalar = base.select("record_id", *(KEY_EXPRESSIONS[k].alias(k) for k in keys)).unpivot(
        index="record_id", variable_name="key", value_name="value"
    )
    return pl.concat([scalar, first_dob]).drop_nulls("value").unique()


def _block_sizes(long: pl.DataFrame, max_block_size: int) -> pl.DataFrame:
    return long.group_by("key", "value").len("size").filter(pl.col("size") > max_block_size)


def dropped_blocks(
    records: Sequence[NormalizedRecord],
    shared_ids: bool = SHARED_IDS_DEFAULT,
    max_block_size: int = MAX_BLOCK_SIZE,
) -> tuple[DroppedBlock, ...]:
    """Key values left out of blocking because too many records share them, largest first."""
    big = _block_sizes(_long_values(records, shared_ids), max_block_size)
    return tuple(
        DroppedBlock(key=k, value_masked=hashlib.sha256(v.encode()).hexdigest()[:12], size=n)
        for k, v, n in big.sort("size", "key", descending=[True, False]).iter_rows()
    )


def candidate_pairs(
    records: Sequence[NormalizedRecord],
    shared_ids: bool = SHARED_IDS_DEFAULT,
    max_block_size: int = MAX_BLOCK_SIZE,
) -> pl.DataFrame:
    """Columns a, b, keys (sorted list of key names). Null key values never match, and a key
    value shared by more than max_block_size records is skipped (see dropped_blocks)."""
    long = _long_values(records, shared_ids)
    long = long.join(_block_sizes(long, max_block_size), on=["key", "value"], how="anti")
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
    dropped_blocks: tuple[DroppedBlock, ...] = ()

    @property
    def recall(self) -> float:
        return self.found_pairs / self.true_pairs if self.true_pairs else 1.0

    @property
    def reduction_ratio(self) -> float:
        """Share of all possible pairs that blocking skips."""
        return 1 - self.candidate_pairs / self.all_pairs if self.all_pairs else 0.0


def evaluate(
    pairs: pl.DataFrame,
    key: AnswerKey,
    n_records: int,
    shared_ids: bool = SHARED_IDS_DEFAULT,
    dropped: tuple[DroppedBlock, ...] = (),
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
        dropped_blocks=dropped,
    )
