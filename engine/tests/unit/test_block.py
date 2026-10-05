"""PR 4 blocking: candidate pairs, recall against the answer key, hard cases, pair hygiene."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from bob_resolve.block import ALL_KEYS, SHARED_ID_KEYS, BlockingReport, candidate_pairs, evaluate
from bob_resolve.block.data import load_normalized
from bob_resolve.cli import app
from bob_resolve.config import TARGET_BLOCKING_RECALL
from bob_resolve.load import read_crm, read_enrollment, to_records
from bob_resolve.normalize.record import normalize_record
from bob_resolve.truth import load_hard_case_key

AS_OF = date(2026, 10, 5)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
SIDES = ["snapshot", "derived"]


@pytest.fixture(scope="module", params=[(s, ids) for s in SIDES for ids in (True, False)])
def report(request: pytest.FixtureRequest) -> tuple[BlockingReport, pl.DataFrame]:
    side, shared_ids = request.param
    records, key = load_normalized(FIXTURES, side, as_of=AS_OF)
    pairs = candidate_pairs(records, shared_ids=shared_ids)
    return evaluate(pairs, key, n_records=len(records), shared_ids=shared_ids), pairs


def test_blocking_recall_meets_the_target_on_every_side_and_mode(
    report: tuple[BlockingReport, pl.DataFrame],
) -> None:
    rep, _ = report
    assert rep.true_pairs == 2167
    assert rep.recall >= TARGET_BLOCKING_RECALL, rep.missed_examples


def test_candidate_count_is_far_below_all_pairs(
    report: tuple[BlockingReport, pl.DataFrame],
) -> None:
    rep, pairs = report
    assert rep.candidate_pairs == pairs.height
    assert rep.all_pairs == rep.n_records * (rep.n_records - 1) // 2
    assert rep.reduction_ratio > 0.99


def test_pairs_are_canonical_unique_and_list_their_keys(
    report: tuple[BlockingReport, pl.DataFrame],
) -> None:
    _, pairs = report
    assert pairs.columns == ["a", "b", "keys"]
    assert pairs.filter(pl.col("a") >= pl.col("b")).height == 0  # canonical, no self pairs
    assert pairs.select("a", "b").is_duplicated().sum() == 0
    assert pairs.filter(pl.col("keys").list.len() == 0).height == 0
    used = {k for ks in pairs["keys"].to_list() for k in ks}
    assert used <= set(ALL_KEYS)
    assert pairs["keys"].to_list() == [sorted(set(k)) for k in pairs["keys"].to_list()]


def test_no_shared_ids_mode_never_uses_mbi(report: tuple[BlockingReport, pl.DataFrame]) -> None:
    rep, pairs = report
    used = {k for ks in pairs["keys"].to_list() for k in ks}
    if rep.shared_ids:
        assert SHARED_ID_KEYS <= used
    else:
        assert not used & SHARED_ID_KEYS
        assert set(rep.recall_per_key) == set(ALL_KEYS) - SHARED_ID_KEYS


def _hard_pairs(hard_cases_dir: Path, shared_ids: bool) -> set[tuple[str, str]]:
    crm = to_records(read_crm(hard_cases_dir / "clients.csv", AS_OF), "crm")
    enr = to_records(read_enrollment(hard_cases_dir / "enrollment_export.csv", AS_OF), "enrollment")
    pairs = candidate_pairs([normalize_record(r) for r in crm + enr], shared_ids=shared_ids)
    return set(zip(pairs["a"], pairs["b"], strict=True))


@pytest.mark.parametrize("shared_ids", [True, False])
def test_hard_cases_reach_the_guard_rails(hard_cases_dir: Path, shared_ids: bool) -> None:
    """Twins, Jr and Sr, spouses, and the pasted MBI must all be compared, so PR 5 can rule.

    Without shared ids, example 7 has no signal at all: the conflict is the pasted MBI itself,
    and the two people share nothing else. Their true pairs must still be found.
    """
    found = _hard_pairs(hard_cases_dir, shared_ids)
    key = load_hard_case_key(hard_cases_dir / "expected.json")
    for m in key.must_not_merge:
        if m.example == 7 and not shared_ids:
            assert tuple(sorted((m.a, m.b))) not in found
            continue
        assert tuple(sorted((m.a, m.b))) in found, (m.example, m.reason)
    assert key.pairs <= found


def test_cli_block_prints_count_recall_and_per_key_recall() -> None:
    result = CliRunner().invoke(app, ["block", "--enrollment", "derived", "--no-shared-ids"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "candidate pairs" in out and "blocking recall" in out and "reduction" in out
    assert "shared ids: off" in out and "derived from the answer key" in out
    assert "mbi" not in out.split("recall per key")[1]
    assert "dob_last_initial" in out
