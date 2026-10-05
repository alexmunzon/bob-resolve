import hashlib
from datetime import date
from pathlib import Path

import pytest

from bob_resolve.load import (
    PersonRecord,
    parse_two_digit_dob,
    read_crm,
    read_enrollment,
    to_records,
)


def test_crm_loads_every_row_with_lineage(snapshot_dir: Path) -> None:
    crm = read_crm(snapshot_dir / "clients.csv")
    assert crm.height == 2040
    assert crm["client_id"].n_unique() == 2040
    assert crm["row_number"].to_list() == list(range(1, 2041))
    lines = (snapshot_dir / "clients.csv").read_text().splitlines()
    first = crm.row(0, named=True)
    assert first["source_file"] == "agency-a-snapshot/clients.csv"
    assert first["raw_sha256"] == hashlib.sha256(lines[1].encode()).hexdigest()
    assert first["dob"] == date(1958, 3, 25)


def test_enrollment_loads_semicolons_and_two_digit_years(snapshot_dir: Path) -> None:
    enr = read_enrollment(snapshot_dir / "enrollment_export.csv")
    assert enr.height == 1847
    first = enr.row(0, named=True)
    assert (first["first_name"], first["dob"], first["policy_number"]) == (
        "Brian",
        date(1958, 3, 25),
        "P-00001",
    )
    assert first["effective_date"] == date(2024, 6, 1)
    # Orphan-policy rows have blank identity fields; they load with nulls, never dropped.
    assert enr["dob"].null_count() == 9
    assert enr["dob_issue"].drop_nulls().to_list() == ["missing"] * 9


def test_records_are_typed_with_source_tags(snapshot_dir: Path) -> None:
    crm = to_records(read_crm(snapshot_dir / "clients.csv"), "crm")
    enr = to_records(read_enrollment(snapshot_dir / "enrollment_export.csv"), "enrollment")
    assert all(isinstance(r, PersonRecord) for r in crm + enr)
    assert crm[10].record_id == "crm:C-00011" and crm[10].first_name == "Dave"
    assert crm[10].lineage.row_number == 11
    assert enr[0].record_id == "enrollment:1" and enr[0].source == "enrollment"
    assert isinstance(enr[0].dob, date)


@pytest.mark.parametrize(
    ("raw", "expected", "issue"),
    [
        ("03/25/58", date(1958, 3, 25), None),
        ("12/31/30", date(1930, 12, 31), None),
        ("01/02/05", date(2005, 1, 2), None),
        ("01/02/29", None, "future"),  # pivot reads 2029: a future DOB is rejected, never guessed
        ("02/30/50", None, "invalid"),
        ("1958-03-25", None, "invalid"),
        (None, None, "missing"),
        ("", None, "missing"),
    ],
)
def test_two_digit_year_pivot(raw: str | None, expected: date | None, issue: str | None) -> None:
    assert parse_two_digit_dob(raw, as_of=date(2026, 10, 5)) == (expected, issue)
