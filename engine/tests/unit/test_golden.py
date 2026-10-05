"""PR 6: clusters, split on conflict, golden records with provenance, IDENTITY_CONFLICT."""

import json
from datetime import UTC, date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest

from bob_resolve.config import SCORE_HIGH
from bob_resolve.golden import GOLDEN_FIELDS, Resolution, build_golden, resolve
from bob_resolve.golden.data import load_people, resolve_side
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import normalize_record
from bob_resolve.score import score_pair
from bob_resolve.truth import build_snapshot_answer_key, load_hard_case_key

AS_OF = date(2026, 10, 1)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def clock() -> datetime:
    return datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _person_of(res: Resolution) -> dict[str, str]:
    return {r: p.person_id for p in res.people for r in p.record_ids}


@pytest.fixture(
    scope="module", params=[(s, ids) for s in ("snapshot", "derived") for ids in (True, False)]
)
def run(request: pytest.FixtureRequest) -> tuple[str, bool, Resolution]:
    side, ids = request.param
    return side, ids, resolve_side(FIXTURES, side, ids, AS_OF, run_id="t", clock=clock)


EXPECTED_PEOPLE = {
    ("snapshot", True): 2000,
    ("snapshot", False): 2000,
    ("derived", True): 2000,
    ("derived", False): 2025,
}


def test_snapshot_people_counts_and_no_false_merge(run: tuple[str, bool, Resolution]) -> None:
    side, ids, res = run
    assert len(res.people) == EXPECTED_PEOPLE[(side, ids)]
    enr = FIXTURES / ("agency-a-derived/enrollment_clean.csv" if side == "derived" else "")
    key = build_snapshot_answer_key(
        FIXTURES / "agency-a-snapshot", enr if side == "derived" else None, as_of=AS_OF
    )
    truth = key.person_of
    assert set(res.unidentifiable) == key.unresolved_ids
    for p in res.people:
        assert len({truth[r] for r in p.record_ids}) == 1, p.record_ids


def test_every_golden_field_has_provenance(run: tuple[str, bool, Resolution]) -> None:
    _, _, res = run
    for p in res.people:
        assert tuple(p.fields) == GOLDEN_FIELDS
        for f in p.fields.values():
            if f.value is None:
                assert f.rule in ("no_value", "identity_conflict")
                continue
            assert f.record_id in p.record_ids and f.source_file and f.row_number >= 1
            assert f.rule in ("authoritative_source", "most_recent")
            assert f.tier == ("single" if len(p.record_ids) == 1 else "rules")


def test_example_2_near_duplicate_with_typo_merges_and_log_names_tier_and_score(
    run: tuple[str, bool, Resolution],
) -> None:
    _, _, res = run
    person = _person_of(res)
    assert person["crm:C-02011"] == person["crm:C-00023"]
    line = next(e for e in res.log if (e.a, e.b) == ("crm:C-00023", "crm:C-02011"))
    assert line.action == "merge" and line.tier == "rules" and line.score is not None
    assert line.score >= SCORE_HIGH and line.run_id == "t" and line.time == clock().isoformat()


def test_example_3_derived_nicknames_keep_the_legal_name_and_the_alias(
    run: tuple[str, bool, Resolution],
) -> None:
    side, _, res = run
    if side != "derived":
        pytest.skip("the snapshot enrollment side repeats the CRM nickname")
    gt = json.loads((FIXTURES / "agency-a-snapshot" / "ground_truth.json").read_text())
    by_record = {r: p for p in res.people for r in p.record_ids}
    checked = 0
    for d in gt["defects"]:
        if d["defect_type"] != "nickname":
            continue
        p = by_record[f"crm:{d['record_key']['client_id']}"]
        if not any(r.startswith("enrollment:") for r in p.record_ids):
            continue
        first = p.fields["first_name"]
        assert first.value == d["injected_values"]["from"]
        assert first.record_id is not None and first.record_id.startswith("enrollment:")
        assert first.rule == "authoritative_source"
        assert d["injected_values"]["to"] in p.aliases
        checked += 1
    assert checked >= 40


@pytest.fixture(scope="module")
def hard() -> Resolution:
    records, recency = load_people(
        FIXTURES / "hard-cases" / "clients.csv",
        FIXTURES / "hard-cases" / "enrollment_export.csv",
        None,
        AS_OF,
    )
    norm = [normalize_record(r) for r in records]
    scored = [score_pair(a, b) for a, b in combinations(norm, 2)]
    return resolve(records, scored, recency, run_id="hard", clock=clock)


def test_example_3_hard_case_dave_is_david_with_an_alias(hard: Resolution) -> None:
    p = next(p for p in hard.people if "crm:HC-009" in p.record_ids)
    assert set(p.record_ids) == {"crm:HC-009", "enrollment:9"}
    first = p.fields["first_name"]
    assert (first.value, first.record_id, first.rule) == (
        "David",
        "enrollment:9",
        "authoritative_source",
    )
    assert first.source_file == "hard-cases/enrollment_export.csv" and first.row_number == 9
    assert p.aliases == ("Dave",)
    assert p.fields["phone"].record_id == "crm:HC-009"  # enrollment carries no contact fields


def test_examples_4_5_6_stay_separate_people_with_no_merge_line(hard: Resolution) -> None:
    key = load_hard_case_key(FIXTURES / "hard-cases" / "expected.json")
    person, merged = _person_of(hard), {(e.a, e.b) for e in hard.log if e.action == "merge"}
    for label in key.must_not_merge:
        if label.example in (4, 5, 6):
            assert person[label.a] != person[label.b]
            assert (label.a, label.b) not in merged
    truth = key.person_of
    for p in hard.people:
        assert len({truth[r] for r in p.record_ids}) == 1


def test_example_7_identity_conflict_goes_to_review_and_is_not_merged(hard: Resolution) -> None:
    person = _person_of(hard)
    assert person["crm:HC-007"] != person["crm:HC-008"]
    item = next(i for i in hard.review if ("crm:HC-007", "crm:HC-008") in i.pairs)
    assert item.reason == "IDENTITY_CONFLICT" and item.severity == "high"
    assert any(p.a == "crm:HC-007" and p.b == "crm:HC-008" for p in hard.pending_gray)


def _rec(rid: str, row: int, **kw: Any) -> PersonRecord:
    source = rid.split(":")[0]
    base: dict[str, Any] = {"first_name": None, "last_name": None, "dob": None, "mbi": None}
    base.update(kw)
    lin = Lineage(source_file=f"synthetic/{source}.csv", row_number=row, raw_sha256="0" * 64)
    return PersonRecord(record_id=rid, source=source, lineage=lin, **base)


def _resolve(records: list[PersonRecord], recency: dict[str, date] | None = None) -> Resolution:
    norm = [normalize_record(r) for r in records]
    scored = [score_pair(a, b) for a, b in combinations(norm, 2)]
    return resolve(records, scored, recency or {}, run_id="syn", clock=clock)


def test_patrick_pat_patricia_chain_is_split_and_sent_to_review() -> None:
    same = {"last_name": "Quill", "dob": date(1950, 3, 4), "phone": "5555550199"}
    recs = [
        _rec("crm:S-1", 1, first_name="Patrick", **same),
        _rec("crm:S-2", 2, first_name="Pat", **same),
        _rec("crm:S-3", 3, first_name="Patricia", **same),
    ]
    res = _resolve(recs)
    person = _person_of(res)
    assert person["crm:S-1"] != person["crm:S-3"]
    item = next(i for i in res.review if i.reason == "CLUSTER_CONFLICT")
    assert set(item.record_ids) == {"crm:S-1", "crm:S-2", "crm:S-3"}
    assert ("crm:S-1", "crm:S-3") in item.pairs
    assert any(e.action == "split" and "CLUSTER_CONFLICT" in e.rule_ids for e in res.log)


def test_two_enrollment_rows_disagreeing_on_dob_leave_the_field_empty() -> None:
    who = {"first_name": "Ada", "last_name": "Vance", "mbi": "9ZZ0ZZ0ZZ01"}
    recs = [
        _rec("enrollment:1", 1, dob=date(1950, 1, 1), **who),
        _rec("enrollment:2", 2, dob=date(1950, 1, 7), **who),
    ]
    res = _resolve(recs)
    assert len(res.people) == 1
    dob = res.people[0].fields["dob"]
    assert dob.value is None and dob.rule == "identity_conflict"
    assert set(dob.candidates) == {("1950-01-01", "enrollment:1"), ("1950-01-07", "enrollment:2")}
    item = next(i for i in res.review if i.reason == "IDENTITY_CONFLICT")
    assert item.severity == "high" and set(item.record_ids) == {"enrollment:1", "enrollment:2"}


def test_mbi_conflict_between_authoritative_records_is_not_guessed() -> None:
    who = {"first_name": "Ada", "last_name": "Vance", "dob": date(1950, 1, 1)}
    recs = [
        _rec("enrollment:1", 1, mbi="9ZZ0ZZ0ZZ01", **who),
        _rec("enrollment:2", 2, mbi="9ZZ0ZZ0ZZ02", **who),
        _rec("crm:S-1", 1, mbi="9ZZ0ZZ0ZZ01", **who),
    ]
    p = build_golden(recs, {}, {r.record_id: "rules" for r in recs})
    assert p.fields["mbi"].value is None and p.fields["mbi"].rule == "identity_conflict"
    assert p.fields["dob"].value == "1950-01-01" and p.review_reasons == ("IDENTITY_CONFLICT",)


def test_contact_fields_come_from_the_most_recent_record() -> None:
    who = {"first_name": "Ada", "last_name": "Vance", "dob": date(1950, 1, 1)}
    recs = [
        _rec("crm:S-1", 1, phone="5555550100", email="old@example.com", **who),
        _rec("crm:S-2", 2, phone="5555550111", **who),
    ]
    recency = {"crm:S-1": date(2023, 1, 1), "crm:S-2": date(2025, 1, 1)}
    p = build_golden(recs, recency, {r.record_id: "rules" for r in recs})
    assert p.fields["phone"].value == "5555550111" and p.fields["phone"].rule == "most_recent"
    assert p.fields["email"].record_id == "crm:S-1"  # newest record has no email: next newest
    assert p.fields["first_name"].record_id == "crm:S-2"  # CRM only: most recent CRM record
