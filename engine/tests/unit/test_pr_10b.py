"""PR 10b: three false-merge and recall patterns the held-out world found (docs/pr-10b-notes.md).

1. GR-007 (Alex, 2026-10-05): name plus DOB as the only agreeing evidence never auto-merges.
2. GR-005: opposite-sex look-alikes one edit apart at the end of the name are not a typo.
3. GR-004: a person's own records (tied by MBI, phone, email, or street) are never ambiguous
   with each other, so a person who moved is not ambiguous with themselves.
"""

from datetime import date

import pytest

from bob_resolve.block import candidate_pairs
from bob_resolve.normalize.names import first_name_typo
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score import ScoredPair, score_candidates

ID = {"mbi": None, "phone": None, "email": None, "address_line1": None, "suffix": None}


def rec(rid: str, first: str, last: str, dob: str, **kw: object) -> NormalizedRecord:
    """A hand-written synthetic record. Contact and ids default to missing."""
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


# Decision 2 (GR-005): opposite-sex look-alikes.


@pytest.mark.parametrize(
    "a,b",
    [("andrew", "andrea"), ("robert", "roberta"), ("brian", "briana"),
     ("christian", "christina"), ("mario", "maria"), ("dan", "dana"), ("paul", "paula"),
     ("eric", "erica"), ("louis", "louise"), ("gabriel", "gabriela"), ("antonio", "antonia"),
     ("julian", "julia"), ("francis", "frances"), ("jesse", "jessie"), ("marion", "marian"),
     ("jason", "mason"), ("larry", "harry"), ("terry", "jerry")],
)  # fmt: skip
def test_look_alike_given_names_one_edit_apart_are_not_a_typo(a: str, b: str) -> None:
    assert not first_name_typo(a, b)
    assert not first_name_typo(b, a)


@pytest.mark.parametrize(
    "a,b",
    [("patrick", "patrik"), ("patrick", "patirck"), ("patrick", "patricks"),
     ("michael", "micheal"), ("jonathan", "jonathon"), ("stephen", "stepehn")],
)  # fmt: skip
def test_a_one_letter_typo_inside_a_long_name_is_still_a_typo(a: str, b: str) -> None:
    assert first_name_typo(a, b)


@pytest.mark.parametrize("ids", [True, False])
def test_andrew_and_andrea_holland_never_auto_merge_even_with_a_shared_mbi(ids: bool) -> None:
    """PR 10 pattern 1 (crm:B-C-00582 and crm:B-C-01533): same household, phone, DOB. Here the
    MBI is shared too, which must not override GR-005."""
    home = {"phone": "5550100001", "address_line1": "12 sample ln", "zip5": "43001",
            "mbi": "9ZZ0ZZ0ZZ01"}  # fmt: skip
    andrew = rec("crm:B-C-00582", "andrew", "holland", "19500101", **home)
    andrea = rec("crm:B-C-01533", "andrea", "holland", "19500101", **home)
    p = pair([andrew, andrea], andrew.record_id, andrea.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "different_people"
    assert "GR-005" in p.guard_rails


# Decision 1 (GR-007): name plus DOB alone never auto-merges.


@pytest.mark.parametrize("ids", [True, False])
def test_brian_hawkins_two_enrollment_rows_with_only_name_and_dob_never_merge(ids: bool) -> None:
    """PR 10 pattern 3 (enrollment:1127 and enrollment:B-228): one in each agency, nothing
    but name and DOB, and no other Brian Hawkins in the book. It used to be "unique": now
    it waits for a person with "unsure"."""
    a = rec("enrollment:1127", "brian", "hawkins", "19570317")
    b = rec("enrollment:B-228", "brian", "hawkins", "19570317")
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-007" in p.guard_rails


@pytest.mark.parametrize("ids", [True, False])
def test_one_more_agreeing_fact_lifts_gr_007(ids: bool) -> None:
    crm = rec("crm:C-1", "david", "lindqvist", "19550819", phone="5550100006",
              email="d@example.com", address_line1="5 mock way", zip5="04001")  # fmt: skip
    enr = rec("enrollment:1", "david", "lindqvist", "19550819")
    for field in ("phone", "email", "address_line1"):
        other = enr.model_copy(update={field: getattr(crm, field)})
        p = pair([crm, other], crm.record_id, other.record_id, ids)
        assert p.decision == "AUTO_MATCH" and p.guard_rails == (), field
    with_mbi = [r.model_copy(update={"mbi": "9AF0AF0AF01"}) for r in (crm, enr)]
    p = pair(with_mbi, crm.record_id, enr.record_id, ids)
    assert (p.decision == "AUTO_MATCH") is ids  # MBI counts only when shared ids are on
    assert ("GR-007" in p.guard_rails) is not ids
    bare = pair([crm, enr], crm.record_id, enr.record_id, ids)
    assert bare.decision == "GRAY" and bare.suggestion == "unsure" and "GR-007" in bare.guard_rails


@pytest.mark.parametrize("ids", [True, False])
def test_a_linking_policy_counts_only_with_shared_ids(ids: bool) -> None:
    """The CRM client owns policy P-1 (carrier member id SH-1); the enrollment row is that
    policy. Policy number is a shared id (SPEC section 5), so "no shared ids" withholds it."""
    keys = frozenset({"policy:P-1", "member:Summit:SH-1"})
    crm = rec("crm:C-1", "david", "lindqvist", "19550819", policy_keys=keys)
    enr = rec(
        "enrollment:1", "david", "lindqvist", "19550819", policy_keys=frozenset({"policy:P-1"})
    )
    p = pair([crm, enr], crm.record_id, enr.record_id, ids)
    if ids:
        assert p.comparison.policy == "same" and p.decision == "AUTO_MATCH"
    else:
        assert p.comparison.policy is None and "GR-007" in p.guard_rails
    other = enr.model_copy(update={"policy_keys": frozenset({"policy:P-2"})})
    q = pair([crm, other], crm.record_id, other.record_id, ids)
    assert q.decision == "GRAY" and "GR-007" in q.guard_rails  # a different policy is no link


@pytest.mark.parametrize("ids", [True, False])
def test_identical_name_and_dob_with_nothing_else_never_merges(ids: bool) -> None:
    """The review 2 "unique in the book" exception is gone: two identical James Smith rows
    with no other data are not auto-merged, whether or not anyone else holds the key."""
    a = rec("crm:HC-018", "james", "smith", "19530115", zip5="43001", state="OH")
    b = a.model_copy(update={"record_id": "crm:HC-018-copy"})
    p = pair([a, b], a.record_id, b.record_id, ids)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-007",)


# Decision 3 (GR-004): a person's own records are not conflicting holders.


@pytest.mark.parametrize("ids", [True, False])
def test_joshua_carter_who_moved_is_not_ambiguous_with_himself(ids: bool) -> None:
    """PR 10 pattern 2 (crm:C-00240 and crm:B-C-00154): old and new address and phone. With
    shared ids only the MBI ties them (new email too); without, the email does. Not GR-004."""
    mbi, email = "1AB2CD3EF45", "joshua.carter@example.com"
    old = rec("crm:C-00240", "joshua", "carter", "19490607", mbi=mbi, email=email,
              phone="5550100011", address_line1="1 old rd", zip5="24961")  # fmt: skip
    new_email = "j.carter@example.com" if ids else email
    new = rec("crm:B-C-00154", "joshua", "carter", "19490607", mbi=mbi, email=new_email,
              phone="5550100022", address_line1="9 new st", zip5="25954")  # fmt: skip
    stale = old.model_copy(update={"record_id": "crm:B-C-09999", "mbi": None, "email": None})
    enr = rec("enrollment:240", "joshua", "carter", "19490607", mbi=mbi)
    recs = [old, new, stale, enr]
    p = pair(recs, old.record_id, new.record_id, ids)
    assert "GR-004" not in p.guard_rails and p.decision == "AUTO_MATCH"
    q = pair(recs, new.record_id, stale.record_id, ids)  # stale copy: tied to old by street
    assert "GR-004" not in q.guard_rails


@pytest.mark.parametrize("ids", [True, False])
def test_two_owen_marlowes_with_nothing_in_common_stay_ambiguous(ids: bool) -> None:
    """Example 9 still holds: two holders of one key, tied by nothing, conflict."""
    a = rec("crm:HC-010", "owen", "marlowe", "19470521", phone="5550100007",
            email="owen@example.com", address_line1="19 sample ln", mbi="9AG0AG0AG01")  # fmt: skip
    b = rec("crm:HC-011", "owen", "marlowe", "19470521", phone="5550100008",
            email="o.m@example.com", address_line1="620 stub ave", mbi="9AH0AH0AH01")  # fmt: skip
    copy = a.model_copy(update={"record_id": "crm:HC-010-copy"})
    got = run([a, b, copy], ids)
    assert "GR-004" in got[frozenset((a.record_id, b.record_id))].guard_rails
    # A copy tied to HC-010 is still stopped: the other Owen conflicts with the pair.
    assert "GR-004" in got[frozenset((a.record_id, copy.record_id))].guard_rails
