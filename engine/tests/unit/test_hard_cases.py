import re
from pathlib import Path

from bob_resolve.load import read_crm, read_enrollment
from bob_resolve.truth import load_hard_case_key

MBI = re.compile(
    r"^[1-9][AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9]\d[AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9]\d[AC-HJKMNP-RT-Y]{2}\d{2}$"
)


def test_hard_cases_load_and_cover_examples_4_to_7(hard_cases_dir: Path) -> None:
    crm = read_crm(hard_cases_dir / "clients.csv")
    enr = read_enrollment(hard_cases_dir / "enrollment_export.csv")
    assert crm.height + enr.height < 30
    assert enr["dob"].null_count() == 0
    key = load_hard_case_key(hard_cases_dir / "expected.json")
    ids = {f"crm:{c}" for c in crm["client_id"]} | {f"enrollment:{n}" for n in enr["row_number"]}
    assert set(key.person_of) == ids
    assert {m.example for m in key.must_not_merge} == {
        4,
        5,
        6,
        7,
        9,
    }  # 9: same name and DOB, PR 5 GR-004
    for m in key.must_not_merge:
        assert key.person_of[m.a] != key.person_of[m.b], m.reason
    assert ("crm:HC-009", "enrollment:9") in key.pairs  # example 3, Dave and David


def test_hard_cases_are_obviously_synthetic(hard_cases_dir: Path) -> None:
    crm = read_crm(hard_cases_dir / "clients.csv")
    enr = read_enrollment(hard_cases_dir / "enrollment_export.csv")
    for mbi in crm["mbi"].to_list() + enr["mbi"].to_list():
        assert MBI.match(mbi) and mbi.startswith("9A"), mbi
    assert all(p.startswith("(555) 555-") for p in crm["phone"])
    assert all(e.endswith("@example.com") for e in crm["email"].drop_nulls())
    assert "ssn" not in " ".join(crm.columns + enr.columns).lower()
