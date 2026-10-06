"""PR 10: the FROZEN matcher on the held-out two-agency world (agency-data-commons v0.2.0).

The targets are SPEC decision 2 plus zero false merges on the must-not-merge list. They are
measured, never tuned for: if one misses, it is marked xfail with the reason, not weakened.
"""

import csv
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


def run_world(out: Path, ids: bool) -> tuple[dict[str, Any], Path]:
    args = ["run", "--world", "multi-a-b", "--shared-ids" if ids else "--no-shared-ids"]
    args += ["--out", str(out), "--run-id", "m", "--as-of", "2026-10-01", "--now", NOW]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert HELD_OUT_LABEL in result.output
    sc: dict[str, Any] = json.loads((out / "m" / "scorecard.json").read_text())
    return sc, out / "m"


@pytest.fixture(scope="module", params=[True, False], ids=["ids-on", "ids-off"])
def held_out(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Any:
    return request.param, *run_world(tmp_path_factory.mktemp("runs"), request.param)


def test_scorecard_is_labeled_held_out_and_reports_every_type(held_out: Any) -> None:
    ids, sc, _ = held_out
    assert sc["enrollment_side"] == "multi-a-b" and sc["shared_ids"] == ids
    assert sc["enrollment_side_label"] == HELD_OUT_LABEL
    ho = sc["held_out"]
    assert ho["label"] == HELD_OUT_LABEL
    assert set(ho["must_not_merge"]) == MNM_TYPES
    assert sum(v["pairs"] for v in ho["must_not_merge"].values()) == 164
    assert INJECTORS <= set(ho["recall_by_injector"])
    assert ho["commons_pairs"]["pairs"] == 320
    for v in [ho["commons_pairs"], *ho["recall_by_injector"].values()]:
        auto, sugg, n = v["found_automatically"], v["suggested_same_person"], v["pairs"]
        assert 0 <= auto <= auto + sugg <= n and not {"recall", "found"} & set(v)
        assert v["automatic_recall"] == round(auto / n, 6)
        assert v["recall_if_suggestions_confirmed"] == round((auto + sugg) / n, 6)


TARGETS = [("blocking_recall", 0.98), ("auto_merge_precision", 0.99), ("recall_after_review", 0.90)]


@pytest.mark.parametrize(("name", "target"), TARGETS, ids=[t[0] for t in TARGETS])
def test_decision_2_targets_on_the_held_out_world(
    held_out: Any, name: str, target: float, request: pytest.FixtureRequest
) -> None:
    ids, sc, _ = held_out
    if not ids and name == "recall_after_review":
        request.applymarker(pytest.mark.xfail(strict=True, reason=NO_IDS_RECALL_MISS))
    m = sc["metrics"][name]
    assert m["target"] == target
    assert m["value"] >= target and m["meets_target"], f"{name} {m['value']}"


# PR 10b measured miss (seen world; Alex's GR-007). strict=True: remove the marker when it passes.
NO_IDS_RECALL_MISS = (
    "Measured PR 10b: without shared ids recall after review over all record pairs is 0.0676: "
    "enrollment rows have no contact fields and MBI and policy are withheld, so CRM to "
    "enrollment pairs agree on name and DOB only, and GR-007 queues them as unsure."
)


# PR 10's two strict xfails (look-alike merges, commons pair recall) pass after PR 10b in both
# modes, so the markers are removed. This world is now seen: a regression set, not held out.
def test_zero_false_merges_on_the_must_not_merge_list(held_out: Any) -> None:
    _, sc, _ = held_out
    merged = {t: v["merged"] for t, v in sc["held_out"]["must_not_merge"].items()}
    assert sum(merged.values()) == 0, merged


def test_recall_after_review_on_the_commons_client_pairs(held_out: Any) -> None:
    """The overall target counts every record pair, mostly easy CRM-to-enrollment pairs inside
    one agency. This one counts only commons' 320 client pairs (312 across the agencies).
    PR 18: it counts same-person suggestions as found, so it is the hypothetical figure."""
    _, sc, _ = held_out
    cp = sc["held_out"]["commons_pairs"]
    assert cp["recall_if_suggestions_confirmed"] >= 0.90
    assert cp["automatic_recall"] <= cp["recall_if_suggestions_confirmed"]


def test_pr_10_examples(held_out: Any) -> None:
    """The three PR 10 failure examples, end to end in the seen world (PR 10b)."""
    ids, _, run = held_out
    person = {r: row["person_id"] for row in csv.DictReader((run / "people.csv").open())
              for r in row["record_ids"].split(";")}  # fmt: skip
    queue = [json.loads(x) for x in (run / "review_queue.jsonl").read_text().splitlines()]

    def item(a: str, b: str) -> dict[str, Any]:
        return next(i for i in queue if {a, b} <= {r["record_id"] for r in i["records"]})

    andrew, andrea = "crm:B-C-00582", "crm:B-C-01533"  # opposite-sex twins: GR-005
    assert person[andrew] != person[andrea]
    assert item(andrew, andrea)["rule_ids"] == ["GR-005"]
    assert item(andrew, andrea)["suggestion"] == "different_people"
    hawkins = ("enrollment:1127", "enrollment:B-228")  # name and DOB only: GR-007
    assert person[hawkins[0]] != person[hawkins[1]]
    assert "GR-007" in item(*hawkins)["rule_ids"] and item(*hawkins)["suggestion"] == "unsure"
    carter = ("crm:C-00240", "crm:B-C-00154")  # moved; with shared ids the MBI ties him
    if ids:
        assert person[carter[0]] == person[carter[1]]
    else:  # nothing else ties the old and new records: honest review, never a merge
        assert person[carter[0]] != person[carter[1]] and item(*carter)["suggestion"] == "unsure"
