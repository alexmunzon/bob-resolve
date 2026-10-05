import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from bob_resolve.load import read_crm, read_enrollment
from bob_resolve.truth import AnswerKey, build_snapshot_answer_key

AS_OF = date(2026, 10, 1)

IDENTITY_DEFECTS = {
    "nickname",
    "name_typo",
    "dob_transposition",
    "dob_month_day_swap",
    "near_duplicate_client",
}


@pytest.fixture(scope="module")
def key() -> AnswerKey:
    snapshot = Path(__file__).resolve().parents[3] / "fixtures" / "agency-a-snapshot"
    return build_snapshot_answer_key(snapshot, as_of=AS_OF)


def test_crm_rows_collapse_to_2000_people(key: AnswerKey) -> None:
    crm_ids = [r for members in key.clusters.values() for r in members if r.startswith("crm:")]
    assert len(crm_ids) == 2040
    assert len(key.clusters) == 2000


def test_every_unscored_identity_defect_is_reachable(snapshot_dir: Path) -> None:
    defects = json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]
    identity = [d for d in defects if d["defect_type"] in IDENTITY_DEFECTS]
    assert len(identity) == 160 and not any(d["scored"] for d in identity)
    ids = set(read_crm(snapshot_dir / "clients.csv", AS_OF)["client_id"])
    assert {d["record_key"]["client_id"] for d in identity} <= ids


def test_copies_pair_with_their_originals(key: AnswerKey, snapshot_dir: Path) -> None:
    defects = json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]
    near = [d for d in defects if d["defect_type"] == "near_duplicate_client"]
    assert len(near) == 30
    for d in near:
        pair = tuple(
            sorted(
                (f"crm:{d['record_key']['client_id']}", "crm:" + d["injected_values"]["copy_of"])
            )
        )
        assert pair in key.pairs
    assert ("crm:C-00023", "crm:C-02011") in key.pairs
    assert key.person_of["crm:C-02011"] == "C-00023"


def test_enrollment_rows_resolve_or_are_reported(key: AnswerKey) -> None:
    enr_ids = [
        r for members in key.clusters.values() for r in members if r.startswith("enrollment:")
    ]
    assert len(enr_ids) + len(key.unresolved) == 1847
    assert len(key.unresolved) == 9
    assert {u.reason for u in key.unresolved} == {"client_not_in_crm"}
    assert [u.policy_number for u in key.unresolved][:2] == ["P-00373", "P-00420"]


def test_dave_has_no_enrollment_row_in_the_snapshot(key: AnswerKey) -> None:
    # SPEC example 3 says C-00011 "Dave" meets "David" in enrollment. In the snapshot his only
    # policy is ACA, which the enrollment export leaves out, so the hard cases carry example 3.
    assert key.clusters["C-00011"] == ("crm:C-00011",)


def test_pair_and_cluster_counts(key: AnswerKey) -> None:
    sizes = [len(m) for m in key.clusters.values()]
    assert len(key.pairs) == sum(n * (n - 1) // 2 for n in sizes)
    assert all(a < b for a, b in key.pairs)
    assert (len(key.pairs), len(key.clusters)) == (2167, 2000)


def test_enrollment_mirrors_crm_identity_defects(key: AnswerKey, snapshot_dir: Path) -> None:
    # The intake kit writes the enrollment export after the identity defects, so the typo
    # "Jhnston" (C-00063, originally "Johnston") shows up on both sides.
    enr = read_enrollment(snapshot_dir / "enrollment_export.csv", AS_OF)
    rows = [int(r.split(":")[1]) for r in key.clusters["C-00063"] if r.startswith("enrollment:")]
    assert rows and set(enr.filter(pl.col("row_number").is_in(rows))["last_name"]) == {"Jhnston"}
