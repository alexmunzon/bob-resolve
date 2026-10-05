"""Polars readers for the CRM clients file and the enrollment export, with lineage on every row."""

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from bob_resolve.config import (
    MAX_PLAUSIBLE_AGE,
    MIN_PLAUSIBLE_AGE,
    PLACEHOLDER_DOBS,
    TWO_DIGIT_YEAR_PIVOT,
)
from bob_resolve.load.records import DobIssue, Lineage, PersonRecord, Source
from bob_resolve.normalize.dob import age_on

ENROLLMENT_COLUMNS = {
    "member_first": "first_name",
    "member_last": "last_name",
    "Birth Dt (mm/dd/yy)": "dob_raw",
    "policy_number": "policy_number",
    "mbi": "mbi",
    "effective": "effective_raw",
}
MDY2 = re.compile(r"^(\d{2})/(\d{2})/(\d{2})$")


def _read_with_lineage(path: Path, separator: str) -> pl.DataFrame:
    """Read every column as text and add source_file, row_number, raw_sha256 per data row."""
    df = pl.read_csv(path, separator=separator, infer_schema=False)
    raw_rows = path.read_text(encoding="utf-8").splitlines()[1:]
    if len(raw_rows) != df.height:
        raise ValueError(f"{path.name}: {len(raw_rows)} raw lines but {df.height} parsed rows")
    return df.with_columns(
        pl.lit(f"{path.parent.name}/{path.name}").alias("source_file"),
        pl.int_range(1, df.height + 1, dtype=pl.Int64).alias("row_number"),
        pl.Series("raw_sha256", [hashlib.sha256(r.encode()).hexdigest() for r in raw_rows]),
    )


def check_dob(d: date, as_of: date) -> tuple[date | None, DobIssue | None]:
    """Future dates and placeholders (1900-01-01) become None. An age under 18 or over 120 at
    as_of keeps the date but is flagged "implausible": it may be a typo, so it is not guessed."""
    if d > as_of:
        return None, "future"
    if d in PLACEHOLDER_DOBS:
        return None, "placeholder"
    if not MIN_PLAUSIBLE_AGE <= age_on(d, as_of) <= MAX_PLAUSIBLE_AGE:
        return d, "implausible"
    return d, None


def parse_two_digit_dob(raw: str | None, as_of: date) -> tuple[date | None, DobIssue | None]:
    """Read mm/dd/yy. Years at or above the pivot's last two digits are 19xx, the rest 20xx.

    With the 1930 pivot, 30 to 99 read as 1930 to 1999 and 00 to 29 as 2000 to 2029. A date after
    `as_of` is a birth date in the future: it is rejected with issue "future", never shifted back.
    """
    if raw is None or not raw.strip():
        return None, "missing"
    m = MDY2.match(raw.strip())
    if m is None:
        return None, "invalid"
    month, day, yy = (int(g) for g in m.groups())
    century = 1900 if yy >= TWO_DIGIT_YEAR_PIVOT % 100 else 2000
    try:
        parsed = date(century + yy, month, day)
    except ValueError:
        return None, "invalid"
    return check_dob(parsed, as_of)


def read_crm(path: Path, as_of: date) -> pl.DataFrame:
    """CRM clients: ISO dates parsed to Date and checked as in check_dob. Notes are dropped."""
    df = _read_with_lineage(path, ",").drop("notes", strict=False)
    parsed = df["dob"].str.to_date("%Y-%m-%d", strict=False)
    checked = [
        (None, "missing" if raw is None else "invalid") if d is None else check_dob(d, as_of)
        for raw, d in zip(df["dob"], parsed, strict=True)
    ]
    return df.with_columns(
        pl.Series("dob", [c[0] for c in checked], dtype=pl.Date),
        pl.Series("dob_issue", [c[1] for c in checked], dtype=pl.String),
    )


def read_enrollment(path: Path, as_of: date) -> pl.DataFrame:
    """Enrollment export: semicolons, two-digit birth years, compact effective dates."""
    df = _read_with_lineage(path, ";").rename(ENROLLMENT_COLUMNS)
    parsed = [parse_two_digit_dob(r, as_of) for r in df["dob_raw"]]
    return df.with_columns(
        pl.Series("dob", [p[0] for p in parsed], dtype=pl.Date),
        pl.Series("dob_issue", [p[1] for p in parsed], dtype=pl.String),
        pl.col("effective_raw").str.to_date("%Y%m%d", strict=False).alias("effective_date"),
    ).drop("dob_raw", "effective_raw")


def to_records(df: pl.DataFrame, source: Source, row_prefix: str = "") -> list[PersonRecord]:
    """Turn a loaded frame into typed records. CRM ids use client_id, enrollment ids the row
    (after `row_prefix`, so a second agency's rows get their own ids, such as enrollment:B-7)."""
    fields = set(PersonRecord.model_fields) - {"record_id", "source", "lineage"}
    out = []
    for row in df.iter_rows(named=True):
        key = row["client_id"] if source == "crm" else f"{row_prefix}{row['row_number']}"
        values: dict[str, Any] = {k: v for k, v in row.items() if k in fields}
        lineage = Lineage(
            source_file=row["source_file"],
            row_number=row["row_number"],
            raw_sha256=row["raw_sha256"],
        )
        out.append(
            PersonRecord(record_id=f"{source}:{key}", source=source, lineage=lineage, **values)
        )
    return out
