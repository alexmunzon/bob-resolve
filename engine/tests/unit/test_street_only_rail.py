"""PR 21b: a shared street is household context, not proof of one person (GR-008).

Stress test finding 2: two fictional residents of one care facility share first name, last
name, DOB and street, with different emails and MBIs. With shared ids off the street was the
only extra agreement, so the pair auto-merged. GR-008 sends name plus DOB plus a shared street
only to review with an honest "unsure". PR 21c (cases a, g, j): a shared street no longer ties
two holders as one person's own records in GR-004, and with shared ids on a differing MBI always
conflicts.
All records here are hand-written and fictional.
"""

from datetime import UTC, date, datetime
from itertools import combinations

import pytest

from bob_resolve.block import candidate_pairs
from bob_resolve.golden import resolve
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import NormalizedRecord, normalize_record
from bob_resolve.queue import build_queue
from bob_resolve.score import ScoredPair, score_candidates, score_pair
from bob_resolve.score.rules import ambiguous_keys, identity_key

HOME = "40 sample care way"
ID = {"mbi": None, "phone": None, "email": None, "address_line1": None, "suffix": None}


def rec(rid: str, first: str, last: str, dob: str, **kw: object) -> NormalizedRecord:
    values: dict[str, object] = {
        "record_id": rid,
        "source": "enrollment" if rid.startswith("enrollment:") else "crm",
        "first_name": first,
        "first_name_canonical": first,
        "last_name": last,
        "last_name_key": last.upper()[:4],
        "dob": date(int(dob[:4]), int(dob[4:6]), int(dob[6:])),
        "dob_key": dob,
        "zip5": None,
        "zip3": None,
        **ID,
    }
    return NormalizedRecord.model_validate(values | kw)


def run(recs: list[NormalizedRecord], ids: bool) -> dict[frozenset[str], ScoredPair]:
    scored = score_candidates(recs, candidate_pairs(recs, ids), ids)
    return {frozenset((p.a, p.b)): p for p in scored}


def pair(recs: list[NormalizedRecord], a: str, b: str, ids: bool) -> ScoredPair:
    return run(recs, ids)[frozenset((a, b))]


def residents(n: int, **kw: object) -> list[NormalizedRecord]:
    """n different people named Wren Halloway, born 1938-04-12, living at one street."""
    return [
        rec(f"crm:R-{i}", "wren", "halloway", "19380412", address_line1=HOME,
            email=f"resident{i}@example.com", mbi=f"9WH0WH0WH{i:02d}", **kw)
        for i in range(n)
    ]  # fmt: skip


def exclusive(p: ScoredPair) -> None:
    assert not {"GR-007", "GR-008"} <= set(p.guard_rails)


# a. Two residents, one street, different emails, no phone.


def test_two_residents_ids_off_go_to_review_with_gr_008() -> None:
    a, b = residents(2)
    p = pair([a, b], a.record_id, b.record_id, False)
    assert p.score >= 0.99  # the score alone would have auto-merged them
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-008",)


def test_two_residents_ids_on_with_different_mbis_never_auto_match() -> None:
    a, b = residents(2)
    p = pair([a, b], a.record_id, b.record_id, True)
    assert p.decision == "GRAY" and p.suggestion == "unsure"
    assert set(p.guard_rails) == {"GR-004", "GR-008"}


# b. Three or more residents with one name and DOB at one street.


@pytest.mark.parametrize("ids", [True, False])
@pytest.mark.parametrize("n", [3, 5])
def test_many_residents_never_auto_match(ids: bool, n: int) -> None:
    got = run(residents(n), ids)
    assert len(got) == n * (n - 1) // 2
    for p in got.values():
        assert p.decision != "AUTO_MATCH" and "GR-008" in p.guard_rails
        exclusive(p)


# c. Blank contacts and different contacts at one street.


@pytest.mark.parametrize("ids", [True, False])
def test_blank_contacts_at_one_street_go_to_review(ids: bool) -> None:
    a = rec("crm:B-1", "wren", "halloway", "19380412", address_line1=HOME)
    b = rec("enrollment:B-2", "wren", "halloway", "19380412", address_line1=HOME)
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-008",)


@pytest.mark.parametrize("ids", [True, False])
def test_different_phones_and_emails_at_one_street_go_to_review(ids: bool) -> None:
    a = rec("crm:D-1", "wren", "halloway", "19380412", address_line1=HOME,
            phone="5550100101", email="a@example.com")  # fmt: skip
    b = rec("crm:D-2", "wren", "halloway", "19380412", address_line1=HOME,
            phone="5550100102", email="b@example.com")  # fmt: skip
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-008" in p.guard_rails


# d. One genuine person with only name, DOB and street: an explicit recall cost.


@pytest.mark.parametrize("ids", [True, False])
def test_same_person_with_only_name_dob_and_street_waits_for_a_person(ids: bool) -> None:
    crm = rec("crm:S-1", "ines", "marrow", "19450903", address_line1="7 mock rd")
    enr = rec("enrollment:S-1", "ines", "marrow", "19450903", address_line1="7 mock rd")
    p = pair([crm, enr], crm.record_id, enr.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-008",)


@pytest.mark.parametrize("ids", [True, False])
def test_far_year_transposition_with_only_a_shared_street_gets_gr_008(ids: bool) -> None:
    """Ellen Quarry 1952 and 1925 at one street: street is independent evidence, so GR-006
    stays quiet, and before GR-008 the pair auto-merged. GR-008 now catches it."""
    a = rec("crm:T-1", "ellen", "quarry", "19520203", address_line1="3 stub ln")
    b = rec("crm:T-2", "ellen", "quarry", "19250203", address_line1="3 stub ln")
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.comparison.dob == "transposition" and "GR-006" not in p.guard_rails
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-008",)


# e. Positive controls: a real agreeing contact or MBI still auto-matches.


@pytest.mark.parametrize("ids", [True, False])
@pytest.mark.parametrize("field", ["phone", "email"])
def test_same_person_old_and_new_address_with_a_shared_contact_still_merges(
    ids: bool, field: str
) -> None:
    shared = {field: "5550100200" if field == "phone" else "ines@example.com"}
    old = rec("crm:M-1", "ines", "marrow", "19450903", address_line1="7 mock rd", **shared)
    new = rec("crm:M-2", "ines", "marrow", "19450903", address_line1="88 new st", **shared)
    p = pair([old, new], old.record_id, new.record_id, ids)
    assert p.decision == "AUTO_MATCH" and p.guard_rails == ()


def test_same_person_with_a_matching_mbi_at_a_shared_street_still_merges() -> None:
    a, b = (r.model_copy(update={"mbi": "9WH0WH0WH77"}) for r in residents(2))
    p = pair([a, b], a.record_id, b.record_id, True)
    assert p.decision == "AUTO_MATCH" and p.guard_rails == ()


# f. Different street lines (two apartments) are not GR-008.


@pytest.mark.parametrize("ids", [True, False])
def test_distinct_apartments_are_not_gr_008(ids: bool) -> None:
    a = rec("crm:A-1", "wren", "halloway", "19380412", address_line1="40 sample way apt 1")
    b = rec("crm:A-2", "wren", "halloway", "19380412", address_line1="40 sample way apt 2")
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.comparison.street == "close"
    assert "GR-008" not in p.guard_rails and "GR-007" in p.guard_rails


# g. GR-004 with shared ids on: a differing MBI is never excused.


def keys(recs: list[NormalizedRecord], ids: bool) -> set[tuple[str, str, str]]:
    return ambiguous_keys(recs, ids)


def test_different_mbis_tied_only_by_street_are_ambiguous() -> None:
    a, b = residents(2)
    assert identity_key(a) in keys([a, b], True)


def test_different_mbis_tied_by_a_phone_chain_are_still_ambiguous() -> None:
    a = rec("crm:P-1", "wren", "halloway", "19380412", mbi="9WH0WH0WH01", phone="5550100300")
    mid = rec("crm:P-2", "wren", "halloway", "19380412", phone="5550100300",
              email="w@example.com")  # fmt: skip
    b = rec("crm:P-3", "wren", "halloway", "19380412", mbi="9WH0WH0WH02", email="w@example.com")
    assert identity_key(a) in keys([a, mid, b], True)


def test_a_person_who_moved_with_one_mbi_is_not_ambiguous() -> None:
    old = rec("crm:V-1", "joel", "pike", "19480101", mbi="9JP0JP0JP01", phone="5550100401",
              email="old@example.com", address_line1="1 old rd")  # fmt: skip
    new = rec("crm:V-2", "joel", "pike", "19480101", mbi="9JP0JP0JP01", phone="5550100402",
              email="new@example.com", address_line1="9 new st")  # fmt: skip
    assert keys([old, new], True) == set()
    p = pair([old, new], old.record_id, new.record_id, True)
    assert p.decision == "AUTO_MATCH" and p.guard_rails == ()


# h. Shared ids off: MBI and policy values are never consulted.


@pytest.mark.parametrize(
    "update",
    [{"mbi": None}, {"mbi": "9WH0WH0WH01"}, {"mbi": "9ZZ0ZZ0ZZ99"},
     {"policy_keys": frozenset({"policy:P-9"})}, {"policy_keys": None}],
)  # fmt: skip
def test_ids_off_ignores_mbi_and_policy_values(update: dict[str, object]) -> None:
    a, b = residents(2)
    base = pair([a, b], a.record_id, b.record_id, False)
    b2 = b.model_copy(update=update)
    a2 = a.model_copy(update={"policy_keys": frozenset({"policy:P-9"})})
    got = pair([a2, b2], a.record_id, b.record_id, False)
    assert (got.decision, got.score, got.guard_rails, got.suggestion) == (
        base.decision,
        base.score,
        base.guard_rails,
        base.suggestion,
    )
    assert keys([a2, b2], False) == keys([a, b], False) == set()


# i. Name and DOB plus a non-street contact is unchanged; GR-007 still fires alone.


@pytest.mark.parametrize("ids", [True, False])
def test_name_dob_plus_email_or_phone_unchanged_and_gr_007_alone(ids: bool) -> None:
    for field, value in (("email", "q@example.com"), ("phone", "5550100500")):
        a = rec("crm:Q-1", "ruth", "quill", "19400606", **{field: value})
        b = rec("enrollment:Q-1", "ruth", "quill", "19400606", **{field: value})
        p = pair([a, b], a.record_id, b.record_id, ids)
        assert p.decision == "AUTO_MATCH" and p.guard_rails == (), field
    a = rec("crm:Q-2", "ruth", "quill", "19400606")
    b = rec("enrollment:Q-2", "ruth", "quill", "19400606")
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.guard_rails == ("GR-007",)
    exclusive(p)


# j. A shared household phone (documents behaviour; not a guarantee with ids off).


def test_two_people_sharing_a_phone_with_different_mbis_never_auto_match() -> None:
    a = rec("crm:H-1", "wren", "halloway", "19380412", mbi="9WH0WH0WH01", phone="5550100600")
    b = rec("crm:H-2", "wren", "halloway", "19380412", mbi="9WH0WH0WH02", phone="5550100600")
    p = pair([a, b], a.record_id, b.record_id, True)
    assert p.decision != "AUTO_MATCH" and "GR-004" in p.guard_rails


# End to end: two facility residents become two golden people and one review item.


def person(rid: str, row: int, **fields: object) -> PersonRecord:
    return PersonRecord.model_validate(
        {
            "record_id": rid,
            "source": rid.split(":")[0],
            "first_name": "Wren",
            "last_name": "Halloway",
            "dob": date(1938, 4, 12),
            "address_line1": "40 Sample Care Way",
            "lineage": Lineage(source_file="synthetic.csv", row_number=row, raw_sha256="b" * 64),
            **fields,
        }
    )


@pytest.mark.parametrize("ids", [True, False])
def test_two_facility_residents_stay_two_people_with_a_review_item(ids: bool) -> None:
    raw = [
        person("crm:F-1", 1, email="first@example.com", mbi="9WH0WH0WH01"),
        person("enrollment:F-2", 2, email="second@example.com", mbi="9WH0WH0WH02"),
    ]
    norm = {r.record_id: normalize_record(r) for r in raw}
    recs = list(norm.values())
    scored = score_candidates(recs, candidate_pairs(recs, ids), ids)
    assert [p.decision for p in scored] == ["GRAY"]
    res = resolve(raw, scored, {}, run_id="street", clock=lambda: datetime(2026, 10, 1, tzinfo=UTC),
                  shared_ids=ids)  # fmt: skip
    assert sorted(len(p.record_ids) for p in res.people) == [1, 1]
    queue = build_queue(res, scored, {r.record_id: r for r in raw}, norm, {}, True)
    assert len(queue) == 1 and "GR-008" in queue[0].rule_ids
    assert queue[0].suggestion == "unsure"


def test_gr_007_and_gr_008_never_fire_together() -> None:
    recs = residents(3) + [rec("crm:X", "wren", "halloway", "19380412")]
    for ids in (True, False):
        for a, b in combinations(recs, 2):
            exclusive(score_pair(a, b, ids))
