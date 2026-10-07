import json
from pathlib import Path

import pytest

from bob_resolve.benchmark import COUNTS as COUNT_NAMES
from bob_resolve.benchmark import build_benchmark, write_benchmark


def write_run(
    root: Path,
    *,
    side: str = "derived",
    jev_mode: str = "off",
    llm_mode: str = "off",
    resolution: dict[str, int] | None = None,
) -> Path:
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": root.name,
                "args": {"enrollment": side, "shared_ids": True},
                "modes": {"rules": "on", "jev": jev_mode, "llm": llm_mode},
                "jev": {"mode": jev_mode, "calls": 0},
                "llm": {"mode": llm_mode, "calls": 0},
            }
        )
    )
    (root / "scorecard.json").write_text(
        json.dumps(
            {
                "candidate_pairs": 2000,
                "metrics": {
                    "auto_merge_precision": {"value": 0.9},
                    "recall_after_review": {"value": 0.8},
                },
                "resolution": resolution
                if resolution is not None
                else {
                    "true_pairs": 100,
                    "found_automatically": 70,
                    "suggested_same_person": 10,
                    "human_confirmed_merges": 0,
                    "awaiting_review": 25,
                },
            }
        )
    )
    return root


def test_rules_only_run_reports_automatic_figures_and_review_counts(tmp_path: Path) -> None:
    run = write_run(tmp_path / "demo")

    report = build_benchmark([run])

    assert report["schema_version"] == 1
    assert report["label"] == "measured on synthetic data"
    entry = report["runs"][0]
    assert entry["dataset"] == {
        "side": "derived",
        "label": "derived from the answer key",
        "status": "derived",
    }
    assert entry["model_tiers_used"] == []
    assert entry["metrics"] == {
        "automatic_precision": 0.9,
        "automatic_recall": 0.7,
        "automatic_f1": 0.7875,
        "recall_if_suggestions_confirmed": 0.8,
        "human_confirmed_merges": 0,
        "awaiting_review": 25,
    }


@pytest.mark.parametrize(
    ("jev", "llm", "used"),
    [
        (("replay", 14), ("off", 0), ["jev"]),
        (("replay", 3), ("replay", 2), ["jev", "llm"]),
        (("replay", 0), ("off", 0), []),
        (("replay", True), ("off", 0), []),
        (("off", 9), ("off", 0), []),
    ],
)
def test_model_tiers_count_only_recorded_calls(
    tmp_path: Path, jev: tuple[str, object], llm: tuple[str, object], used: list[str]
) -> None:
    run = write_run(tmp_path / "run", jev_mode=jev[0], llm_mode=llm[0])
    data = json.loads((run / "manifest.json").read_text())
    data["jev"]["calls"], data["llm"]["calls"] = jev[1], llm[1]
    (run / "manifest.json").write_text(json.dumps(data))

    assert build_benchmark([run])["runs"][0]["model_tiers_used"] == used


def test_multi_agency_is_seen_unless_manifest_explicitly_marks_held_out(tmp_path: Path) -> None:
    seen = write_run(tmp_path / "seen", side="multi-a-b")
    held = write_run(tmp_path / "held", side="multi-a-b")
    data = json.loads((held / "manifest.json").read_text())
    data["benchmark_status"] = "held_out"
    (held / "manifest.json").write_text(json.dumps(data))

    statuses = {r["run_id"]: r["dataset"]["status"] for r in build_benchmark([seen, held])["runs"]}

    assert statuses == {"seen": "seen", "held": "held_out"}


def test_refuses_missing_or_duplicate_run_files_and_writes_stably(tmp_path: Path) -> None:
    run = write_run(tmp_path / "demo")
    with pytest.raises(ValueError, match="manifest.json and scorecard.json"):
        build_benchmark([tmp_path / "missing"])
    with pytest.raises(ValueError, match="duplicate run id"):
        build_benchmark([run, run])

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_benchmark([run], first)
    write_benchmark([run], second)
    assert first.read_bytes() == second.read_bytes()


def test_suggestions_never_count_as_automatic_or_human_resolution(tmp_path: Path) -> None:
    run = write_run(
        tmp_path / "reviewed",
        resolution={
            "true_pairs": 50,
            "found_automatically": 30,
            "suggested_same_person": 5,
            "human_confirmed_merges": 3,
            "awaiting_review": 7,
        },
    )

    metrics = build_benchmark([run])["runs"][0]["metrics"]

    assert metrics["automatic_recall"] == 0.6
    assert metrics["recall_if_suggestions_confirmed"] == 0.8
    assert metrics["human_confirmed_merges"] == 3
    assert metrics["awaiting_review"] == 7


def test_older_runs_without_resolution_counts_report_null_not_the_suggestion_figure(
    tmp_path: Path,
) -> None:
    run = write_run(tmp_path / "old")
    data = json.loads((run / "scorecard.json").read_text())
    del data["resolution"]
    (run / "scorecard.json").write_text(json.dumps(data))

    metrics = build_benchmark([run])["runs"][0]["metrics"]

    assert metrics["automatic_recall"] is None
    assert metrics["automatic_f1"] is None
    assert metrics["human_confirmed_merges"] is None
    assert metrics["awaiting_review"] is None
    assert metrics["recall_if_suggestions_confirmed"] == 0.8


def test_dataset_label_never_claims_held_out_unless_status_says_so(tmp_path: Path) -> None:
    run = write_run(tmp_path / "world", side="multi-a-b")
    card = json.loads((run / "scorecard.json").read_text())
    card["enrollment_side_label"] = "held-out: never used to tune the matcher"
    (run / "scorecard.json").write_text(json.dumps(card))

    dataset = build_benchmark([run])["runs"][0]["dataset"]

    assert dataset == {"side": "multi-a-b", "label": "two-agency synthetic world", "status": "seen"}


@pytest.mark.parametrize(
    ("side", "status"),
    [("derived", "held_out"), ("snapshot", "derived"), ("multi-a-b", "snapshot")],
)
def test_refuses_a_status_that_does_not_fit_the_dataset(
    tmp_path: Path, side: str, status: str
) -> None:
    run = write_run(tmp_path / "run", side=side)
    data = json.loads((run / "manifest.json").read_text())
    data["benchmark_status"] = status
    (run / "manifest.json").write_text(json.dumps(data))

    with pytest.raises(ValueError, match="benchmark_status"):
        build_benchmark([run])


@pytest.mark.parametrize(
    "change",
    [
        {"found_automatically": 15},
        {"found_automatically": -3},
        {"found_automatically": 4, "suggested_same_person": 7},
        {"true_pairs": True},
        {"awaiting_review": "19"},
        {"awaiting_review": None},
    ],
)
def test_refuses_impossible_missing_or_non_numeric_counts(tmp_path: Path, change: dict) -> None:
    counts = dict.fromkeys(COUNT_NAMES, 0) | {"true_pairs": 10} | change
    resolution = {k: v for k, v in counts.items() if v is not None}
    run = write_run(tmp_path / "bad", resolution=resolution)

    with pytest.raises(ValueError, match="run bad: resolution"):
        build_benchmark([run])


@pytest.mark.parametrize(
    "metrics",
    [
        {"auto_merge_precision": {"value": True}},
        {"auto_merge_precision": {"value": float("nan")}},
        {"auto_merge_precision": {"value": 1.5}},
        {"auto_merge_precision": 0.9},
    ],
)
def test_refuses_malformed_metrics_with_a_clear_error(tmp_path: Path, metrics: dict) -> None:
    run = write_run(tmp_path / "bad")
    card = json.loads((run / "scorecard.json").read_text())
    card["metrics"] = metrics
    (run / "scorecard.json").write_text(json.dumps(card))

    with pytest.raises(ValueError, match="auto_merge_precision"):
        build_benchmark([run])


def test_refuses_a_suggestion_figure_below_automatic_recall(tmp_path: Path) -> None:
    run = write_run(tmp_path / "odd")
    card = json.loads((run / "scorecard.json").read_text())
    card["metrics"]["recall_after_review"] = {"value": 0.5}
    (run / "scorecard.json").write_text(json.dumps(card))

    with pytest.raises(ValueError, match="run odd: recall_after_review is below automatic recall"):
        build_benchmark([run])
