"""PR 5 scoring: targets on every side and mode, hard-case guard rails, comparison levels."""

import random
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from bob_resolve.block import candidate_pairs
from bob_resolve.block.data import load_normalized
from bob_resolve.cli import app
from bob_resolve.config import TARGET_AUTO_MERGE_PRECISION, TARGET_RECALL_AFTER_REVIEW
from bob_resolve.load import read_crm, read_enrollment, to_records
from bob_resolve.normalize.record import NormalizedRecord, normalize_record
from bob_resolve.score import (
    GUARD_RAILS,
    Comparison,
    ScoredPair,
    ScoreReport,
    compare,
    evaluate_scores,
    score_candidates,
    score_pair,
    withhold_shared_ids,
)
from bob_resolve.truth import AnswerKey, UnresolvedRow

AS_OF = date(2026, 10, 1)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(
    scope="module", params=[(s, ids) for s in ("snapshot", "derived") for ids in (True, False)]
)
def report(request: pytest.FixtureRequest) -> tuple[ScoreReport, list[ScoredPair]]:
    side, shared_ids = request.param
    records, key = load_normalized(FIXTURES, side, as_of=AS_OF)
    scored = score_candidates(records, candidate_pairs(records, shared_ids), shared_ids)
    return evaluate_scores(scored, key, shared_ids), scored


def test_auto_merge_precision_and_recall_after_review_meet_the_targets(
    report: tuple[ScoreReport, list[ScoredPair]], request: pytest.FixtureRequest
) -> None:
    rep, _ = report
    if not rep.shared_ids:
        request.applymarker(pytest.mark.xfail(strict=True, reason=NO_IDS_RECALL_MISS))
    assert rep.true_pairs == 2167 and rep.auto_match > 0
    assert rep.auto_merge_precision >= TARGET_AUTO_MERGE_PRECISION, rep.false_merges[:10]
    assert rep.recall_after_review >= TARGET_RECALL_AFTER_REVIEW, rep.missed[:10]


# PR 10b measured miss (Alex's GR-007, docs/pr-10b-notes.md). strict=True: if it ever passes,
# the marker must be removed.
NO_IDS_RECALL_MISS = (
    "Measured PR 10b: without shared ids recall after review is 0.0185 on the snapshot and on "
    "the derived side. Enrollment rows carry no phone, email, or street, and MBI and policy are "
    "withheld, so almost every CRM to enrollment pair has only name and DOB: GR-007 sends it to "
    "review as unsure, which SPEC decision 2 does not count as found. Precision stays 1.0."
)


def test_no_shared_ids_precision_still_meets_the_target(
    report: tuple[ScoreReport, list[ScoredPair]],
) -> None:
    """The xfail above covers recall only; precision is still a hard target in both modes."""
    rep, _ = report
    assert rep.true_pairs == 2167 and rep.auto_match > 0
    assert rep.auto_merge_precision >= TARGET_AUTO_MERGE_PRECISION, rep.false_merges[:10]


def test_every_guard_rail_hit_records_its_rule_id_and_never_auto_matches(
    report: tuple[ScoreReport, list[ScoredPair]],
) -> None:
    _, scored = report
    for p in scored:
        assert set(p.guard_rails) <= set(GUARD_RAILS)
        if p.guard_rails:
            assert p.decision != "AUTO_MATCH" and p.suggestion != "same_person"
        assert (p.reason == "IDENTITY_CONFLICT") == ("GR-002" in p.guard_rails)
        assert 0.0 <= p.score <= 1.0


@pytest.fixture(scope="module")
def hard() -> dict[str, NormalizedRecord]:
    d = FIXTURES / "hard-cases"
    crm = to_records(read_crm(d / "clients.csv", AS_OF), "crm")
    enr = to_records(read_enrollment(d / "enrollment_export.csv", AS_OF), "enrollment")
    return {r.record_id: normalize_record(r) for r in crm + enr}


def _score(hard: dict[str, NormalizedRecord], a: str, b: str, ids: bool = True) -> ScoredPair:
    return score_pair(hard[a], hard[b], shared_ids=ids)


@pytest.mark.parametrize("ids", [True, False])
def test_example_4_twins_never_auto_match(hard: dict[str, NormalizedRecord], ids: bool) -> None:
    for a, b in [("crm:HC-001", "crm:HC-002"), ("enrollment:1", "enrollment:2")]:
        assert _score(hard, a, b, ids).decision != "AUTO_MATCH"


@pytest.mark.parametrize("ids", [True, False])
def test_example_5_jr_and_sr_never_auto_match(hard: dict[str, NormalizedRecord], ids: bool) -> None:
    p = _score(hard, "crm:HC-003", "crm:HC-004", ids)
    assert p.decision != "AUTO_MATCH" and "GR-001" in p.guard_rails
    assert _score(hard, "crm:HC-003", "enrollment:4", ids).decision != "AUTO_MATCH"


@pytest.mark.parametrize("ids", [True, False])
def test_example_6_spouses_never_auto_match(hard: dict[str, NormalizedRecord], ids: bool) -> None:
    p = _score(hard, "crm:HC-005", "crm:HC-006", ids)
    assert p.decision != "AUTO_MATCH" and "GR-003" in p.guard_rails


def test_example_7_identity_conflict_goes_to_review(hard: dict[str, NormalizedRecord]) -> None:
    for a, b in [("crm:HC-007", "crm:HC-008"), ("crm:HC-008", "enrollment:7")]:
        p = _score(hard, a, b)
        assert p.decision == "GRAY" and p.reason == "IDENTITY_CONFLICT"
        assert "GR-002" in p.guard_rails


def test_same_person_hard_cases_are_found_or_reviewed(hard: dict[str, NormalizedRecord]) -> None:
    p = _score(hard, "crm:HC-009", "enrollment:9", True)  # example 3, Dave and David
    assert p.decision == "AUTO_MATCH" or p.suggestion == "same_person", p
    # Without shared ids only name and DOB agree: GR-007 (PR 10b) sends it to review, unsure.
    p = _score(hard, "crm:HC-009", "enrollment:9", False)
    assert p.decision == "GRAY" and p.suggestion == "unsure" and p.guard_rails == ("GR-007",)
    # Nina's CRM row carries a pasted MBI, so her two rows disagree on MBI: review, not a guess.
    assert _score(hard, "crm:HC-008", "enrollment:8").decision == "GRAY"
    p = _score(hard, "crm:HC-008", "enrollment:8", ids=False)  # name and DOB only (GR-007)
    assert p.decision == "GRAY" and p.guard_rails == ("GR-007",)


def test_month_day_swap_with_same_mbi_is_scored_not_blocked(
    hard: dict[str, NormalizedRecord],
) -> None:
    dave = hard["crm:HC-009"].model_copy(update={"dob_key": "19550408"})
    david = hard["enrollment:9"].model_copy(update={"dob_key": "19550804"})
    p = score_pair(dave, david)
    assert p.comparison.dob == "month_day_swap" and p.comparison.mbi == "same"
    assert p.guard_rails == () and p.reason is None
    assert p.decision == "AUTO_MATCH" or p.suggestion == "same_person"


def test_compare_levels_and_no_shared_ids_ignores_mbi(hard: dict[str, NormalizedRecord]) -> None:
    c = compare(hard["crm:HC-009"], hard["enrollment:9"])
    assert (c.first, c.last, c.dob, c.mbi, c.suffix) == ("nickname", "equal", "exact", "same", None)
    assert c.last_metaphone_equal is True and c.first_jw is not None
    assert compare(hard["crm:HC-009"], hard["enrollment:9"], shared_ids=False).mbi is None
    assert compare(hard["crm:HC-003"], hard["crm:HC-004"]).suffix == "different"
    assert compare(hard["crm:HC-003"], hard["enrollment:4"]).suffix == "one_missing"


def test_cli_score_prints_the_targets() -> None:
    result = CliRunner().invoke(app, ["score", "--enrollment", "derived", "--no-shared-ids"])
    assert result.exit_code == 0, result.output
    out = result.output
    for label in ("auto-merge precision", "auto-merge count", "gray count", "reject count"):
        assert label in out
    assert "recall after review" in out and "shared ids: off" in out
    assert "GR-001" in out and "derived from the answer key" in out


def test_no_scoring_feature_can_see_household_id() -> None:
    """In the snapshot exactly the 40 copied clients have a blank household id: a leak."""
    assert "household_id" not in NormalizedRecord.model_fields
    assert not any("household" in f for f in Comparison.model_fields)


def test_no_shared_ids_mode_nulls_mbi_on_the_records_before_scoring() -> None:
    records, _ = load_normalized(FIXTURES, "derived", as_of=AS_OF)
    assert any(r.mbi for r in records)
    assert all(r.mbi is None for r in withhold_shared_ids(records))
    scored = score_candidates(records, candidate_pairs(records, False), shared_ids=False)
    assert all(p.comparison.mbi is None for p in scored)


@pytest.mark.parametrize("shared_ids", [True, False])
def test_decisions_do_not_depend_on_record_ids_or_row_order(shared_ids: bool) -> None:
    """Record ids leak the answer (crm:C-020xx are the copies), so rename and shuffle them."""
    records, key = load_normalized(FIXTURES, "derived", as_of=AS_OF)
    rng = random.Random(5)
    new_ids = {r.record_id: f"r{rng.getrandbits(64):016x}" for r in records}
    old_of = {v: k for k, v in new_ids.items()}
    renamed = [r.model_copy(update={"record_id": new_ids[r.record_id]}) for r in records]
    rng.shuffle(renamed)
    renamed_key = AnswerKey(
        clusters={
            f"p{i}": tuple(new_ids[x] for x in recs) for i, recs in enumerate(key.clusters.values())
        }
    )

    def run(recs: list[NormalizedRecord], k: AnswerKey) -> tuple[ScoreReport, dict[Any, str]]:
        scored = score_candidates(recs, candidate_pairs(recs, shared_ids), shared_ids)
        return evaluate_scores(scored, k, shared_ids), {(p.a, p.b): p.decision for p in scored}

    base, base_dec = run(records, key)
    shuf, shuf_dec = run(renamed, renamed_key)
    mapped = {tuple(sorted((old_of[a], old_of[b]))): d for (a, b), d in shuf_dec.items()}
    assert mapped == base_dec
    assert shuf.auto_merge_precision == base.auto_merge_precision
    assert shuf.recall_after_review == base.recall_after_review
    assert (shuf.auto_match, shuf.gray, shuf.auto_reject) == (
        base.auto_match,
        base.gray,
        base.auto_reject,
    )


def test_unresolved_rows_are_not_true_pairs_and_any_auto_match_to_them_is_false(
    hard: dict[str, NormalizedRecord],
) -> None:
    p = _score(hard, "crm:HC-009", "enrollment:9")
    assert p.decision == "AUTO_MATCH"
    key = AnswerKey(
        clusters={"P1": ("x", "y")},
        unresolved=(
            UnresolvedRow(
                record_id="z", policy_number=None, client_id=None, reason="client_not_in_crm"
            ),
        ),
    )
    scored = [p.model_copy(update={"a": "x", "b": "y"}), p.model_copy(update={"a": "x", "b": "z"})]
    rep = evaluate_scores(scored, key, shared_ids=True)
    assert rep.true_pairs == 1 and rep.auto_match == 2
    assert rep.false_merges == (("x", "z"),) and rep.unresolved_auto_matched == 1
    assert rep.auto_merge_precision == 0.5


def test_real_unresolved_rows_never_auto_match() -> None:
    records, key = load_normalized(FIXTURES, "snapshot", as_of=AS_OF)
    unresolved = {u.record_id for u in key.unresolved}
    assert len(unresolved) == 9
    scored = score_candidates(records, candidate_pairs(records, True), True)
    assert evaluate_scores(scored, key, True).unresolved_auto_matched == 0
    assert not any(
        p.a in unresolved or p.b in unresolved for p in scored if p.decision == "AUTO_MATCH"
    )


def _run_hard(hard: dict[str, NormalizedRecord], ids: bool) -> dict[tuple[str, str], ScoredPair]:
    recs = list(hard.values())
    return {(p.a, p.b): p for p in score_candidates(recs, candidate_pairs(recs, ids), ids)}


@pytest.mark.parametrize("ids", [True, False])
def test_gr_004_same_name_and_dob_with_nothing_in_common_never_auto_match(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    run = _run_hard(hard, ids)
    p = run[("crm:HC-010", "crm:HC-011")]
    assert p.decision == "GRAY" and p.suggestion == "unsure" and "GR-004" in p.guard_rails
    # A true pair with the same name and DOB and no conflicting holder is not GR-004. With
    # shared ids it auto-merges; without, only name and DOB agree, so GR-007 holds it (PR 10b).
    dave = run[("crm:HC-009", "enrollment:9")]
    assert "GR-004" not in dave.guard_rails
    assert dave.guard_rails == (() if ids else ("GR-007",))


def test_gr_004_stops_every_pair_on_a_conflicted_key(hard: dict[str, NormalizedRecord]) -> None:
    """A copy of HC-010 agrees with it fully, but HC-011 holds the same key and conflicts."""
    copy = hard["crm:HC-010"].model_copy(update={"record_id": "crm:HC-010-copy"})
    recs = [hard["crm:HC-010"], hard["crm:HC-011"], copy]
    scored = score_candidates(recs, candidate_pairs(recs, False), False)
    assert len(scored) == 3
    assert all(p.decision == "GRAY" and "GR-004" in p.guard_rails for p in scored)
    alone = score_candidates([recs[0], copy], candidate_pairs([recs[0], copy], False), False)
    assert alone[0].decision == "AUTO_MATCH"


def test_gray_same_person_suggestion_needs_compatible_first_names(
    report: tuple[ScoreReport, list[ScoredPair]],
) -> None:
    """C-00755 Matthew and C-00756 Shannon Hunt share surname, DOB, and address: not one person."""
    _, scored = report
    for p in scored:
        if p.suggestion == "same_person":
            assert p.comparison.first in ("equal", "nickname", "close"), p


@pytest.mark.parametrize("ids", [True, False])
def test_gr_005_patrick_and_patricia_twins_never_auto_match(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    """Example 10: same surname, DOB, address, phone; different MBIs; incompatible first names."""
    p = _run_hard(hard, ids)[("crm:HC-012", "crm:HC-013")]
    assert p.comparison.first == "close"  # Jaro-Winkler alone rates them near
    assert p.decision == "GRAY" and p.suggestion == "different_people"
    assert "GR-005" in p.guard_rails


@pytest.mark.parametrize("ids", [True, False])
def test_gr_005_lets_a_one_letter_typo_and_a_nickname_auto_match(
    hard: dict[str, NormalizedRecord], ids: bool
) -> None:
    pat = hard["crm:HC-012"]
    for typo in ("Patrik", "Patirck", "Patricks"):  # delete, adjacent swap, insert: one edit
        copy = pat.model_copy(update={"record_id": "crm:HC-012-typo", "first_name": typo.lower()})
        p = score_pair(pat, copy, shared_ids=ids)
        assert p.decision == "AUTO_MATCH" and "GR-005" not in p.guard_rails, typo
    dave = _score(hard, "crm:HC-009", "enrollment:9", ids)  # Dave and David: nickname
    assert "GR-005" not in dave.guard_rails
    # With shared ids the MBI agrees; without, name and DOB alone wait in review (GR-007).
    assert dave.guard_rails == (() if ids else ("GR-007",))
    assert (dave.decision == "AUTO_MATCH") is ids
    blank = pat.model_copy(update={"record_id": "crm:HC-012-blank", "first_name": None})
    assert "GR-005" not in score_pair(pat, blank, shared_ids=ids).guard_rails


def test_gr_005_never_fires_on_a_true_pair(report: tuple[ScoreReport, list[ScoredPair]]) -> None:
    rep, scored = report
    assert "GR-005" in rep.guard_rail_hits
    missed = set(rep.missed)  # a true pair GR-005 stopped would be missed (not same person)
    for p in scored:
        if "GR-005" in p.guard_rails:
            assert (p.a, p.b) not in missed
