"""PR 10: the FROZEN matcher on the held-out two-agency world (agency-data-commons v0.2.0).

The targets are SPEC decision 2 plus zero false merges on the must-not-merge list. They are
measured, never tuned for: if one misses, it is marked xfail with the reason, not weakened.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from bob_resolve.cli import app
from bob_resolve.load.commons import HELD_OUT_LABEL

NOW = "2026-10-01T12:00:00+00:00"
MNM_TYPES = {
    "shared_household_contact",
    "child_on_parent_policy",
    "father_son_same_name",
    "twin_lookalike",
    "name_dob_lookalike",
}
INJECTORS = {
    "maiden_name",
    "hyphenated_surname",
    "moved_household",
    "shared_household_contact",
    "same_policy_two_member_ids",
}


def run_world(out: Path, ids: bool) -> dict[str, Any]:
    args = ["run", "--world", "multi-a-b", "--shared-ids" if ids else "--no-shared-ids"]
    args += ["--out", str(out), "--run-id", "m", "--as-of", "2026-10-01", "--now", NOW]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert HELD_OUT_LABEL in result.output
    sc: dict[str, Any] = json.loads((out / "m" / "scorecard.json").read_text())
    return sc


@pytest.fixture(scope="module", params=[True, False], ids=["ids-on", "ids-off"])
def held_out(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Any:
    return request.param, run_world(tmp_path_factory.mktemp("runs"), request.param)


def test_scorecard_is_labeled_held_out_and_reports_every_type(held_out: Any) -> None:
    ids, sc = held_out
    assert sc["enrollment_side"] == "multi-a-b" and sc["shared_ids"] == ids
    assert sc["enrollment_side_label"] == HELD_OUT_LABEL
    ho = sc["held_out"]
    assert ho["label"] == HELD_OUT_LABEL
    assert set(ho["must_not_merge"]) == MNM_TYPES
    assert sum(v["pairs"] for v in ho["must_not_merge"].values()) == 164
    assert INJECTORS <= set(ho["recall_by_injector"])
    assert ho["commons_pairs"]["pairs"] == 320
    for v in ho["recall_by_injector"].values():
        assert 0 <= v["found"] <= v["pairs"] and v["recall"] == round(v["found"] / v["pairs"], 6)


TARGETS = [("blocking_recall", 0.98), ("auto_merge_precision", 0.99), ("recall_after_review", 0.90)]


@pytest.mark.parametrize(("name", "target"), TARGETS, ids=[t[0] for t in TARGETS])
def test_decision_2_targets_on_the_held_out_world(held_out: Any, name: str, target: float) -> None:
    _, sc = held_out
    m = sc["metrics"][name]
    assert m["target"] == target
    assert m["value"] >= target and m["meets_target"], f"{name} {m['value']}"


# PR 10 measured misses (matcher frozen, not tuned; a later PR decides the fixes). strict=True:
# a fix that makes one pass turns it into a failure, so the marker must then be removed.
MNM_MISS = (
    "Measured PR 10: twin_lookalike merged (4 pairs with shared ids, 12 without): opposite-sex "
    "twins one letter apart (Andrew and Andrea, Robert and Roberta) count as a first-name typo, "
    "so GR-005 does not stop them; without shared ids 4 name_dob_lookalike pairs also merge "
    "through enrollment rows, which have no ZIP or contact for GR-007 to see a conflict."
)
PAIR_MISS = (
    "Measured PR 10: recall after review on the 320 commons client pairs is 0.8938 with shared "
    "ids and 0.8812 without: moved_household pairs (old and new address) hit GR-004, whose "
    "holders disagree on ZIP and phone, so they go to review as unsure, not same person."
)


@pytest.mark.xfail(strict=True, reason=MNM_MISS)
def test_zero_false_merges_on_the_must_not_merge_list(held_out: Any) -> None:
    _, sc = held_out
    merged = {t: v["merged"] for t, v in sc["held_out"]["must_not_merge"].items()}
    assert sum(merged.values()) == 0, merged


@pytest.mark.xfail(strict=True, reason=PAIR_MISS)
def test_recall_after_review_on_the_commons_client_pairs(held_out: Any) -> None:
    """The overall target counts every record pair, mostly easy CRM-to-enrollment pairs inside
    one agency. This one counts only commons' 320 client pairs (312 across the agencies)."""
    _, sc = held_out
    assert sc["held_out"]["commons_pairs"]["recall"] >= 0.90
