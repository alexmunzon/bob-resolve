"""PR 3 normalizers: names, suffixes, nicknames, DOB variants, address, phone, email."""

import csv
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bob_resolve.load import read_crm, read_enrollment, to_records
from bob_resolve.normalize.address import normalize_address, zip3, zip5
from bob_resolve.normalize.dob import dob_edit_distance, is_month_day_swap, is_transposition
from bob_resolve.normalize.email import normalize_email
from bob_resolve.normalize.names import (
    NICKNAMES_CSV,
    canonical_first_name,
    canonical_names,
    names_compatible,
    normalize_name,
    split_suffix,
    surname_key,
)
from bob_resolve.normalize.phone import normalize_phone
from bob_resolve.normalize.record import NormalizedRecord, normalize_record

AS_OF = date(2026, 10, 5)
ALL = [normalize_name, normalize_address, normalize_phone, normalize_email, zip5]


@pytest.mark.parametrize("fn", ALL)
@given(s=st.text(max_size=40))
def test_normalization_is_idempotent(fn: Callable[[str], str | None], s: str) -> None:
    once = fn(s)
    assert once is None or fn(once) == once


def _hard(hard_cases_dir: Path, *ids: str) -> list[NormalizedRecord]:
    recs = to_records(read_crm(hard_cases_dir / "clients.csv", AS_OF), "crm")
    return [normalize_record(r) for r in recs if r.client_id in ids]


def test_name_cleanup() -> None:
    assert normalize_name("  José  O'Brien-Smith. ") == "jose obrien smith"
    assert normalize_name("   ") is None and normalize_name(None) is None


def test_suffix_split_keeps_sr_and_jr_distinct(hard_cases_dir: Path) -> None:
    assert split_suffix("Robert", "Hale, Jr.") == ("robert", "hale", "jr")
    assert split_suffix("Robert III", "Hale") == ("robert", "hale", "iii")
    assert split_suffix("Ann", "Iv") == ("ann", "iv", None)
    sr, jr = _hard(hard_cases_dir, "HC-003", "HC-004")
    assert (sr.last_name, sr.suffix, jr.last_name, jr.suffix) == ("hale", "sr", "hale", "jr")


def test_example_4_nicknames() -> None:
    yes = [("Dave", "David"), ("Bill", "William"), ("Peggy", "Margaret"), ("J.", "John")]
    assert all(names_compatible(a, b) for a, b in yes + [("Bill", "Will"), ("dave", "DAVE")])
    no = [("Ellen", "Grace"), ("Dave", "Daniel"), (None, "David")]
    assert not any(names_compatible(a, b) for a, b in no)
    assert canonical_first_name("Liz") == "elizabeth" and canonical_first_name("Bob") == "robert"


def test_every_nickname_maps_to_a_canonical_name(snapshot_dir: Path) -> None:
    with NICKNAMES_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 150
    canonicals = {r["canonical"] for r in rows}
    for r in rows:
        assert r["canonical"].casefold() in canonical_names(r["nickname"])
        assert r["nickname"] not in canonicals
        assert canonical_first_name(r["canonical"]) == r["canonical"].casefold()
    defects = json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]
    nicks = [d["injected_values"] for d in defects if d["defect_type"] == "nickname"]
    assert len(nicks) == 60 and all(names_compatible(v["from"], v["to"]) for v in nicks)


def test_dob_defects_in_snapshot_are_detected(snapshot_dir: Path) -> None:
    defects = json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]

    def pairs(kind: str) -> list[tuple[str, str]]:
        vals = [d["injected_values"] for d in defects if d["defect_type"] == kind]
        return [(v["from"].replace("-", ""), v["to"].replace("-", "")) for v in vals]

    swaps, flips = pairs("dob_transposition"), pairs("dob_month_day_swap")
    assert len(swaps) == 20 and len(flips) == 10
    for a, b in swaps:
        assert is_transposition(a, b) and dob_edit_distance(a, b) == 1
    for a, b in flips:
        assert is_month_day_swap(a, b) and not is_transposition(a, b)
    assert not is_transposition("19500112", "19500113")
    assert not (
        is_transposition("19500101", "19500101") or is_month_day_swap("19500303", "19500303")
    )


def test_example_7_dobs_are_more_than_one_edit_apart(hard_cases_dir: Path) -> None:
    carl, nina = _hard(hard_cases_dir, "HC-007", "HC-008")
    assert carl.mbi == nina.mbi and carl.dob_key and nina.dob_key
    assert dob_edit_distance(carl.dob_key, nina.dob_key) > 1


def test_phone() -> None:
    for raw in ("(555) 555-0101", "+1 555.555.0101", "15555550101"):
        assert normalize_phone(raw) == "5555550101"
    for bad in ("555-0101", "25555550101", "", None):
        assert normalize_phone(bad) is None


def test_email() -> None:
    assert normalize_email("  Jane.Doe@Example.COM ") == "jane.doe@example.com"
    assert normalize_email("j.a.n.e@gmail.com") == "j.a.n.e@gmail.com"
    assert normalize_email("not-an-email") is None and normalize_email("") is None


def test_address_and_zip() -> None:
    assert normalize_address("3419 Amanda Gardens Apt. 764") == "3419 AMANDA GDNS APT 764"
    assert normalize_address("12 Sample Lane, Suite #5") == "12 SAMPLE LN STE 5"
    assert [zip5("04001"), zip5("43001-1234"), zip5("4300")] == ["04001", "43001", None]
    assert (zip3("04001"), zip3(None)) == ("040", None)


def test_surname_key_and_normalized_record(snapshot_dir: Path) -> None:
    assert surname_key("Nolan") == surname_key("Nlan")
    assert surname_key("") is None
    df = read_enrollment(snapshot_dir / "enrollment_export.csv", AS_OF)
    recs = [normalize_record(r) for r in to_records(df, "enrollment")]
    assert len(recs) == df.height
    first = recs[0]
    assert first.zip3 is None and first.dob_key is not None
    with pytest.raises(ValueError):
        first.first_name = "x"  # type: ignore[misc]
