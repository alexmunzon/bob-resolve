"""Review 1 fixes: block size cap, placeholder stop lists, first name plus DOB key, frozen key
list, exact duplicate rows, implausible DOBs, more suffixes, unresolved rows as a set."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from bob_resolve.block import ALL_KEYS, candidate_pairs, dropped_blocks
from bob_resolve.config import DEFAULT_AS_OF, MAX_BLOCK_SIZE
from bob_resolve.load import parse_two_digit_dob, read_crm
from bob_resolve.normalize.dob import dob_key
from bob_resolve.normalize.email import normalize_email
from bob_resolve.normalize.names import split_suffix
from bob_resolve.normalize.phone import normalize_phone
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.truth import AnswerKey, build_snapshot_answer_key

AS_OF = date(2026, 10, 1)


def _rec(i: int, **kw: Any) -> NormalizedRecord:
    base: dict[str, Any] = {f: None for f in NormalizedRecord.model_fields}
    base.update(record_id=f"crm:T-{i:04d}", source="crm")
    base.update(kw)
    return NormalizedRecord(**base)


def test_block_explosion_is_capped_and_reported() -> None:
    # 60 people share one agency phone; two of them also share a real email.
    recs = [_rec(i, phone="3105550123", last_name=f"p{i}") for i in range(MAX_BLOCK_SIZE + 10)]
    recs[0] = _rec(0, phone="3105550123", email="a@b.org")
    recs[1] = _rec(1, phone="3105550123", email="a@b.org")
    pairs = candidate_pairs(recs, shared_ids=True)
    assert pairs.height == 1
    assert pairs.row(0) == ("crm:T-0000", "crm:T-0001", ["email"])
    dropped = dropped_blocks(recs, shared_ids=True)
    assert len(dropped) == 1
    d = dropped[0]
    assert (d.key, d.size) == ("phone", MAX_BLOCK_SIZE + 10)
    assert "3105550123" not in d.value_masked and len(d.value_masked) == 12


def test_block_at_the_cap_is_kept() -> None:
    recs = [_rec(i, phone="3105550123") for i in range(MAX_BLOCK_SIZE)]
    assert candidate_pairs(recs).height == MAX_BLOCK_SIZE * (MAX_BLOCK_SIZE - 1) // 2
    assert dropped_blocks(recs) == ()


@pytest.mark.parametrize(
    "raw",
    [
        "000-000-0000",
        "(111) 111-1111",
        "555 555 5555",
        "9999999999",
        "1-222-222-2222",
        "1234567890",
    ],
)
def test_placeholder_phones_become_none(raw: str) -> None:
    assert normalize_phone(raw) is None


def test_real_phone_survives_the_stop_list() -> None:
    assert normalize_phone("(310) 555-0123") == "3105550123"


@pytest.mark.parametrize("raw", ["none@x.com", "NoEmail@gmail.com", "na@agency.org", "test@t.io"])
def test_placeholder_emails_become_none(raw: str) -> None:
    assert normalize_email(raw) is None


def test_real_email_survives_the_stop_list() -> None:
    assert normalize_email("nancy@x.com") == "nancy@x.com"


@pytest.mark.parametrize("d", [date(1900, 1, 1), date(1901, 1, 1)])
def test_placeholder_dobs_become_none(d: date, tmp_path: Path) -> None:
    assert dob_key(d) is None
    csv = tmp_path / "clients.csv"
    csv.write_text(f"client_id,first_name,last_name,dob,mbi\nC-1,Ann,Lee,{d.isoformat()},\n")
    df = read_crm(csv, AS_OF)
    assert df["dob"].to_list() == [None]
    assert df["dob_issue"].to_list() == ["placeholder"]


def test_first_name_dob_key_pairs_a_hyphenated_surname() -> None:
    dob = date(1950, 3, 14)
    a = _rec(1, first_name="mary", last_name="smith jones", dob=dob, dob_key=dob_key(dob))
    b = _rec(2, first_name="mary", last_name="smith", dob=dob, dob_key=dob_key(dob))
    pairs = candidate_pairs([a, b])
    assert pairs.height == 1
    assert "first_name_dob" in pairs["keys"][0]


def test_first_name_dob_key_uses_the_whole_nickname_set() -> None:
    dob = date(1950, 3, 14)
    a = _rec(1, first_name="bill", last_name="ortiz", dob=dob, dob_key=dob_key(dob))
    b = _rec(2, first_name="william", last_name="king", dob=dob, dob_key=dob_key(dob))
    assert "first_name_dob" in candidate_pairs([a, b])["keys"][0]


def test_blocking_key_list_is_frozen() -> None:
    """Phase 2 measures this exact blocker. Changing keys needs a new review, not a quick edit."""
    assert ALL_KEYS == (
        "mbi",
        "email",
        "phone",
        "dob_last_initial",
        "surname_zip3",
        "dob_digits_last_initial",
        "surname_birth_month_day",
        "first_name_dob",
    )


def test_exact_duplicate_rows_are_counted(snapshot_dir: Path) -> None:
    key = build_snapshot_answer_key(snapshot_dir, as_of=AS_OF)
    summary = key.summary()
    assert summary["exact_duplicate_rows"] == key.exact_duplicate_rows
    assert key.exact_duplicate_rows >= 0
    assert summary["unresolved_rows"] == 9


def test_row_hash_is_never_a_matching_feature() -> None:
    assert "raw_sha256" not in NormalizedRecord.model_fields
    assert "lineage" not in NormalizedRecord.model_fields


def test_two_digit_25_is_implausible() -> None:
    assert parse_two_digit_dob("07/04/25", AS_OF) == (date(2025, 7, 4), "implausible")


def test_ages_at_the_edges(tmp_path: Path) -> None:
    assert parse_two_digit_dob("10/01/08", AS_OF) == (date(2008, 10, 1), None)  # 18 today
    assert parse_two_digit_dob("10/02/08", AS_OF) == (date(2008, 10, 2), "implausible")
    csv = tmp_path / "clients.csv"
    csv.write_text("client_id,first_name,last_name,dob,mbi\nC-1,Ann,Lee,1905-06-01,\n")
    assert read_crm(csv, AS_OF)["dob_issue"].to_list() == ["implausible"]


def test_cli_as_of_default_is_fixed() -> None:
    assert DEFAULT_AS_OF == date(2026, 10, 1)


@pytest.mark.parametrize(
    ("last", "suffix"),
    [("Hale V", "v"), ("Hale 2nd", "2nd"), ("Hale 3rd.", "3rd"), ("Hale, 2nd.", "2nd")],
)
def test_more_generational_suffixes(last: str, suffix: str) -> None:
    assert split_suffix("Robert", last) == ("robert", "hale", suffix)


def test_unresolved_rows_are_an_explicit_set(snapshot_dir: Path) -> None:
    key: AnswerKey = build_snapshot_answer_key(snapshot_dir, as_of=AS_OF)
    assert len(key.unresolved_ids) == 9
    assert all(r.startswith("enrollment:") for r in key.unresolved_ids)
    person_of = key.person_of
    assert not key.unresolved_ids & set(person_of)
    resolved = [r for r in ["crm:C-00001", *key.unresolved_ids] if r not in key.unresolved_ids]
    assert [person_of[r] for r in resolved]  # no KeyError once unresolved rows are excluded
