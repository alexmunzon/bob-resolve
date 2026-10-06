"""Review 2: false-merge holes in the scorer (F1 to F4) and metrics on final edges (F8).

See docs/review-2-score-notes.md. A false merge is worse than a missed match (SPEC decision 2).
"""

from datetime import date
from pathlib import Path

import pytest

from bob_resolve.block import candidate_pairs
from bob_resolve.cluster import split_on_conflict
from bob_resolve.load import read_crm, read_enrollment, to_records
from bob_resolve.normalize.names import first_name_typo
from bob_resolve.normalize.record import NormalizedRecord, normalize_record
from bob_resolve.score import ScoredPair, evaluate_scores, score_candidates, score_pair
from bob_resolve.score.compare import dob_level
from bob_resolve.truth import AnswerKey

AS_OF = date(2026, 10, 1)
HC = Path(__file__).resolve().parents[3] / "fixtures" / "hard-cases"


@pytest.fixture(scope="module")
def hard() -> dict[str, NormalizedRecord]:
    crm = to_records(read_crm(HC / "clients.csv", AS_OF), "crm")
    enr = to_records(read_enrollment(HC / "enrollment_export.csv", AS_OF), "enrollment")
    return {r.record_id: normalize_record(r) for r in crm + enr}


def _run(recs: list[NormalizedRecord], ids: bool) -> dict[tuple[str, str], ScoredPair]:
    return {(p.a, p.b): p for p in score_candidates(recs, candidate_pairs(recs, ids), ids)}


def _copy(r: NormalizedRecord, rid: str, **update: object) -> NormalizedRecord:
    return r.model_copy(update={"record_id": rid, **update})


# F1 and F4: two formal names, or a short name, one edit apart are not a typo.


@pytest.mark.parametrize(
    "a,b",
    [("mario", "maria"), ("dan", "dana"), ("mary", "mark"), ("jon", "jan"), ("eric", "erica"),
     ("paul", "paula"), ("denis", "denise"), ("carl", "carla"), ("bea", "beau")],
)  # fmt: skip
def test_formal_or_short_first_names_one_edit_apart_are_not_a_typo(a: str, b: str) -> None:
    assert not first_name_typo(a, b)


@pytest.mark.parametrize(
    "a,b", [("patrick", "patrik"), ("patrick", "patirck"), ("michael", "micheal")]
)
def test_a_real_one_letter_typo_of_a_long_name_is_still_a_typo(a: str, b: str) -> None:
    assert first_name_typo(a, b)


@pytest.mark.parametrize("ids", [True, False])
def test_shared_mbi_never_overrides_two_formal_first_names(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    """Example 11: Denise and Denis Okafor share DOB, address, phone, email, and MBI."""
    p = _run(list(hard.values()), ids)[("crm:HC-006", "crm:HC-014")]
    if ids:
        assert p.comparison.mbi == "same"
    assert p.decision == "GRAY" and p.suggestion == "different_people"
    assert "GR-005" in p.guard_rails
    carla = _run(list(hard.values()), ids)[("crm:HC-007", "crm:HC-015")]
    assert carla.decision != "AUTO_MATCH" and "GR-005" in carla.guard_rails


# F2: a DOB is close only by a transposition, a month-day swap, or a month or day digit.


@pytest.mark.parametrize(
    "a,b,level",
    [
        ("19500101", "19800101", "far"),  # one changed year digit: Robert Hale 1950 and 1980
        ("19410602", "19480602", "far"),
        ("19500101", "19500201", "one_edit"),  # month digit
        ("19500101", "19500109", "one_edit"),  # day digit
        ("19501021", "19500221", "far"),  # two month digits changed, not a swap
        ("19520414", "19250414", "transposition"),  # year transposition, 27 years
        ("19500412", "19501204", "month_day_swap"),
    ],
)
def test_dob_levels(a: str, b: str, level: str) -> None:
    assert dob_level(a, b) == level


@pytest.mark.parametrize("ids", [True, False])
def test_year_digit_change_never_auto_matches(hard: dict[str, NormalizedRecord], ids: bool) -> None:
    """Example 12: Robert Hale born 1948 at Sr's (1941) and Jr's (1968) address and phone."""
    run = _run(list(hard.values()), ids)
    for pair in (("crm:HC-003", "crm:HC-016"), ("crm:HC-004", "crm:HC-016")):
        p = run[pair]
        assert p.comparison.dob == "far" and p.decision != "AUTO_MATCH"
        assert p.suggestion != "same_person"


@pytest.mark.parametrize("ids", [True, False])
def test_gr_006_year_transposition_needs_independent_evidence(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    """Example 12: Ellen Quarry 1952 and Ellen Quarry 1925, same ZIP, nothing else agrees."""
    p = _run(list(hard.values()), ids)[("crm:HC-001", "crm:HC-017")]
    assert p.comparison.dob == "transposition" and p.comparison.dob_years_apart == 27
    assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-006" in p.guard_rails
    with_phone = _copy(hard["crm:HC-017"], "crm:HC-017-phone", phone=hard["crm:HC-001"].phone)
    q = score_pair(hard["crm:HC-001"], with_phone, shared_ids=ids)
    assert "GR-006" not in q.guard_rails  # a matching phone is independent evidence
    x = _copy(hard["crm:HC-017"], "crm:x", dob_key="19501104")
    y = _copy(hard["crm:HC-017"], "crm:y", dob_key="19510104")  # swap moves the year by one
    one_year = score_pair(x, y, shared_ids=ids)
    assert one_year.comparison.dob == "transposition" and "GR-006" not in one_year.guard_rails


# F3: name plus DOB as the only evidence (GR-007).


@pytest.mark.parametrize("ids", [True, False])
def test_gr_007_two_james_smiths_in_different_zips(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    """Example 13: same name and DOB, no MBI or contact data, different ZIP codes."""
    p = _run(list(hard.values()), ids)[("crm:HC-018", "crm:HC-019")]
    assert p.comparison.zip5 == "different"
    assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-007" in p.guard_rails


@pytest.mark.parametrize("ids", [True, False])
def test_name_and_dob_alone_never_auto_matches_even_when_unique(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    """PR 10b (Alex) replaced the review 2 "unique in the book" exception: a lone James Smith
    and an exact copy with nothing else, or with any other holders, never auto-match."""
    run = _run(list(hard.values()), ids)
    dave = run[("crm:HC-009", "enrollment:9")]  # the MBI is the extra fact, ids on only
    assert dave.guard_rails == (() if ids else ("GR-007",))
    james = hard["crm:HC-018"]
    enr = _copy(james, "enrollment:99", source="enrollment", zip5=None, zip3=None, state=None)
    copy, far, twin_row = _copy(james, "crm:x"), hard["crm:HC-019"], _copy(enr, "enrollment:98")
    for recs in ([james, copy], [james, enr], [james, enr, far], [james, enr, twin_row]):
        for p in _run(recs, ids).values():
            assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-007" in p.guard_rails


# F8: precision and recall after review are measured on the final kept edges.


def test_metrics_use_final_edges_after_cluster_splits(hard: dict[str, NormalizedRecord]) -> None:
    """Patrick and Pat auto-match, Pat and Patricia auto-match, Patrick and Patricia conflict:
    the cluster check holds both edges (PR 21a). A held pair is not a merge and is not found."""
    patrick, patricia = hard["crm:HC-012"], hard["crm:HC-013"]
    pat = _copy(patricia, "crm:HC-012-pat", first_name="pat", first_name_canonical="patricia")
    recs = [patrick, patricia, pat]
    scored = list(_run(recs, False).values())
    auto = [p for p in scored if p.decision == "AUTO_MATCH"]
    assert len(auto) == 2
    _, kept, splits = split_on_conflict(recs, auto)
    assert len(splits) == 1 and len(kept) == 0
    key = AnswerKey(clusters={"P1": ("crm:HC-012", "crm:HC-012-pat"), "P2": ("crm:HC-013",)})
    before = evaluate_scores(scored, key, False)
    after = evaluate_scores(scored, key, False, kept=kept)
    assert before.auto_match == 2 and after.auto_match == 0 and after.cut_by_cluster == 2
    for cut in sorted((p.a, p.b) for p in auto):
        assert (cut in key.pairs) == (cut in after.missed)
    assert after.false_merges == () and after.auto_merge_precision == 1.0
