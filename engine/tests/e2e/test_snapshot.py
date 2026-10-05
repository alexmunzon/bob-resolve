"""PR 7: SPEC section 9 examples 1 to 8 end to end through `bob-resolve run`, plus every
SPEC decision 2 target on all four side and shared-ids combinations. Jev and LLM are off."""

import json
import shlex
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner

from bob_resolve.block import candidate_pairs
from bob_resolve.cli import app
from bob_resolve.cluster import components
from bob_resolve.golden import GOLDEN_FIELDS
from bob_resolve.golden.data import load_people
from bob_resolve.normalize.record import normalize_record
from bob_resolve.score import score_candidates
from bob_resolve.truth import build_snapshot_answer_key

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
NOW = "2026-10-01T12:00:00+00:00"
COMBOS = [(s, ids) for s in ("snapshot", "derived") for ids in (True, False)]


def run_cli(out: Path, side: str, ids: bool, run_id: str, *extra: str) -> Path:
    args = ["run", "--enrollment", side, "--shared-ids" if ids else "--no-shared-ids"]
    args += ["--out", str(out), "--run-id", run_id, "--as-of", "2026-10-01", "--now", NOW]
    result = CliRunner().invoke(app, [*args, *extra])
    assert result.exit_code == 0, result.output
    return out / run_id


def load(run: Path) -> dict[str, Any]:
    def jsonl(name: str) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (run / name).read_text().splitlines()]

    return {
        "manifest": json.loads((run / "manifest.json").read_text()),
        "scorecard": json.loads((run / "scorecard.json").read_text()),
        "households": json.loads((run / "households.json").read_text()),
        "people": pl.read_csv(run / "people.csv", infer_schema=False),
        "log": jsonl("merge_log.jsonl"),
        "queue": jsonl("review_queue.jsonl"),
        "members": jsonl("members.jsonl"),
    }


@pytest.fixture(scope="module", params=COMBOS, ids=[f"{s}-ids-{i}" for s, i in COMBOS])
def combo(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Any:
    side, ids = request.param
    return side, ids, load(run_cli(tmp_path_factory.mktemp("runs"), side, ids, "r"))


@pytest.fixture(scope="module", params=[True, False], ids=["hard-ids-True", "hard-ids-False"])
def hard(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Any:
    run = load(run_cli(tmp_path_factory.mktemp("runs"), "hard-cases", request.param, "hc"))
    return run | {"shared_ids": request.param}


def person_of(people: pl.DataFrame) -> dict[str, str]:
    return {
        r: p for p, ids in people.select("person_id", "record_ids").rows() for r in ids.split(";")
    }


def household_of(run: dict[str, Any]) -> dict[str, str]:
    return {p: h["household_id"] for h in run["households"]["households"] for p in h["person_ids"]}


def merged(run: dict[str, Any], a: str, b: str) -> bool:
    return any({e["a"], e["b"]} == {a, b} and e["action"] == "merge" for e in run["log"])


def test_decision_2_targets_on_every_combination(combo: Any) -> None:
    side, ids, run = combo
    sc = run["scorecard"]
    for name, target in (
        ("blocking_recall", 0.98),
        ("auto_merge_precision", 0.99),
        ("recall_after_review", 0.90),
    ):
        m = sc["metrics"][name]
        assert m["value"] >= target and m["target"] == target and m["meets_target"], name
        assert m["label"] == "measured on synthetic data"
        assert m["enrollment_side"] == side and m["shared_ids"] == ids
    assert sc["people_holding_two_true_people"] == 0
    assert sc["review_queue"]["size"] == len(run["queue"])
    assert sc["unidentifiable"] == 9
    # PR 9: each unidentifiable record names its source file and row, so a person can find it.
    assert len(sc["unidentifiable_records"]) == 9
    assert all(u["source_file"] and u["row_number"] >= 1 for u in sc["unidentifiable_records"])
    # members.jsonl holds every record of each person of two or more, MBI masked, no notes.
    owner = person_of(run["people"])
    sizes = Counter(owner.values())
    multi = {r: p for r, p in owner.items() if sizes[p] > 1}
    assert {m["record_id"]: m["person_id"] for m in run["members"]} == multi
    assert all("mbi" not in m and "notes" not in m for m in run["members"])


def test_example_1_happy_path_snapshot(combo: Any) -> None:
    """People count from the answer key alone: join every true pair except the true pairs the
    queue still holds as gray pairs (a human has not decided them yet). The resulting groups
    must equal the people in the run, one for one."""
    side, ids, run = combo
    people = run["people"]
    enr = FIXTURES / "agency-a-derived/enrollment_clean.csv" if side == "derived" else None
    key = build_snapshot_answer_key(FIXTURES / "agency-a-snapshot", enr, as_of=date(2026, 10, 1))
    waiting = {(i["pairs"][0]["a"], i["pairs"][0]["b"]) for i in run["queue"]
               if i["kind"] == "gray_pair"}  # fmt: skip
    in_run = {r for ids_ in people["record_ids"] for r in ids_.split(";")}
    edges = [p for p in key.pairs if p not in waiting and set(p) <= in_run]
    expected = components(sorted(in_run), edges)
    assert len(key.clusters) == 2000 and people.height == len(expected)
    assert {tuple(sorted(c)) for c in expected} == {
        tuple(sorted(x.split(";"))) for x in people["record_ids"]
    }
    assert run["scorecard"]["people"] == people.height
    for f in GOLDEN_FIELDS:
        has = people.filter(pl.col(f).is_not_null())
        assert has[f"{f}_source"].null_count() == 0 and has[f"{f}_row"].null_count() == 0
        assert set(has[f"{f}_tier"].unique()) <= {"rules", "single"}


def test_example_2_near_duplicate_with_typo(combo: Any) -> None:
    _, _, run = combo
    p = person_of(run["people"])
    assert p["crm:C-02011"] == p["crm:C-00023"]
    line = next(e for e in run["log"] if (e["a"], e["b"]) == ("crm:C-00023", "crm:C-02011"))
    assert line["tier"] == "rules" and line["score"] is not None and line["rule_ids"]


def test_example_3_nickname_across_sources(combo: Any, hard: dict[str, Any]) -> None:
    side, _, run = combo
    dave = hard["people"].filter(pl.col("record_ids").str.contains("crm:HC-009"))
    assert dave["first_name"].item() == "David" and "Dave" in dave["aliases"].item().split(";")
    if side != "derived":
        return
    crm = pl.read_csv(FIXTURES / "agency-a-snapshot/clients.csv", infer_schema=False)
    first = dict(crm.select("client_id", "first_name").rows())
    defects = json.loads((FIXTURES / "agency-a-snapshot/ground_truth.json").read_text())["defects"]
    nick = {d["record_key"]["client_id"] for d in defects if d["defect_type"] == "nickname"}
    checked = 0
    for row in run["people"].iter_rows(named=True):
        ids = row["record_ids"].split(";")
        crm_ids = [i[4:] for i in ids if i.startswith("crm:") and i[4:] in nick]
        if crm_ids and any(i.startswith("enrollment:") for i in ids):
            assert first[crm_ids[0]] in (row["aliases"] or "").split(";")
            assert row["first_name_source"].startswith("enrollment:")
            checked += 1
    assert checked >= 20


def test_example_4_twins_stay_two_people_in_one_household(hard: dict[str, Any]) -> None:
    p, hh = person_of(hard["people"]), household_of(hard)
    assert p["crm:HC-001"] != p["crm:HC-002"]
    assert hh[p["crm:HC-001"]] == hh[p["crm:HC-002"]]
    assert not merged(hard, "crm:HC-001", "crm:HC-002")
    assert not merged(hard, "enrollment:1", "enrollment:2")


def rules_decision(a: str, b: str, shared_ids: bool) -> str:
    """The rules arm's own decision on one hard-case pair, recomputed outside the run."""
    hc = FIXTURES / "hard-cases"
    recs, _ = load_people(hc / "clients.csv", hc / "enrollment_export.csv", None,
                          date(2026, 10, 1))  # fmt: skip
    norm = [normalize_record(r) for r in recs]
    for p in score_candidates(norm, candidate_pairs(norm, shared_ids), shared_ids):
        if {p.a, p.b} == {a, b}:
            return str(p.decision)
    return "NOT_A_CANDIDATE"


def test_example_5_jr_and_sr(hard: dict[str, Any]) -> None:
    """Jr and Sr stay apart. Each pair is either queued suggesting "different people", or
    absent from the queue because the scorer rejected it outright (score below the auto-reject
    line, or never a candidate): the queue holds only gray pairs and conflicts."""
    p = person_of(hard["people"])
    assert p["crm:HC-003"] != p["crm:HC-004"] and p["crm:HC-003"] != p["enrollment:4"]
    logged = {(e["a"], e["b"]) for e in hard["log"]}  # any log line means it was matched
    for a, b in (("crm:HC-003", "crm:HC-004"), ("crm:HC-003", "enrollment:4")):
        assert not merged(hard, a, b) and (a, b) not in logged
        items = [i for i in hard["queue"] if {a, b} <= {r["record_id"] for r in i["records"]}]
        if items:
            assert all(i["suggestion"] == "different_people" for i in items)
        else:  # absent for a stated reason: the scorer rejected it or never paired it
            assert rules_decision(a, b, hard["shared_ids"]) in ("AUTO_REJECT", "NOT_A_CANDIDATE")


def test_example_6_shared_contact_details(hard: dict[str, Any]) -> None:
    p, hh = person_of(hard["people"]), household_of(hard)
    assert p["crm:HC-005"] != p["crm:HC-006"]
    assert hh[p["crm:HC-005"]] == hh[p["crm:HC-006"]]
    assert not merged(hard, "crm:HC-005", "crm:HC-006")


def test_example_7_identity_conflict_goes_to_review_high(hard: dict[str, Any]) -> None:
    p = person_of(hard["people"])
    assert p["crm:HC-007"] != p["crm:HC-008"]
    assert not merged(hard, "crm:HC-007", "crm:HC-008")
    if not hard["shared_ids"]:
        # No shared ids withholds the MBI, so the shared-MBI conflict (GR-002) cannot be seen:
        # the pair stays apart on its far birth dates and is not queued as a conflict.
        assert not any(i["reason"] == "IDENTITY_CONFLICT" for i in hard["queue"])
        return
    item = next(
        i
        for i in hard["queue"]
        if {r["record_id"] for r in i["records"]} == {"crm:HC-007", "crm:HC-008"}
    )
    assert item["reason"] == "IDENTITY_CONFLICT" and item["severity"] == "high"
    assert "GR-002" in item["rule_ids"]
    for r in item["records"]:  # minimized: MBI masked to the last 4
        assert r["mbi_masked"].startswith("*") and len(r["mbi_masked"].strip("*")) == 4
        assert "mbi" not in r and "notes" not in r


def test_example_8_jev_off_every_gray_pair_queued(combo: Any) -> None:
    _, _, run = combo
    m = run["manifest"]
    assert m["modes"] == {"rules": "on", "jev": "off", "llm": "off"}
    for arm in ("jev", "llm"):
        assert m[arm] == {"mode": "off", "calls": 0, "cost_usd": 0.0}
    gray = run["scorecard"]["per_tier"]["rules"]["gray"]
    queued = [i for i in run["queue"] if i["kind"] == "gray_pair"]
    assert len(queued) == gray
    for i in run["queue"]:
        assert i["deciding_tier"] == "rules" and i["severity"] in ("high", "medium")


def test_examples_9_and_10_guard_rails_reach_the_queue(hard: dict[str, Any]) -> None:
    """GR-004 (two Owen Marlowes) and GR-005 (twins Patrick and Patricia) stay apart and are
    queued with their rule id; GR-005 suggests "different people"."""
    p = person_of(hard["people"])
    for a, b, rule, suggestion in (
        ("crm:HC-010", "crm:HC-011", "GR-004", "unsure"),
        ("crm:HC-012", "crm:HC-013", "GR-005", "different_people"),
    ):
        assert p[a] != p[b] and not merged(hard, a, b)
        item = next(i for i in hard["queue"] if {r["record_id"] for r in i["records"]} == {a, b})
        assert rule in item["rule_ids"] and item["suggestion"] == suggestion


def test_review_2_examples_11_to_13_never_merge(hard: dict[str, Any]) -> None:
    """Review 2, both shared-ids modes: two formal or short first names one edit apart (GR-005,
    even with a shared MBI), a changed birth-year digit (far), a year transposition with no
    independent evidence (GR-006), and two James Smiths in different ZIPs (GR-007)."""
    p = person_of(hard["people"])
    for a, b, rule, suggestion in (
        ("crm:HC-006", "crm:HC-014", "GR-005", "different_people"),
        ("crm:HC-007", "crm:HC-015", "GR-005", "different_people"),
        ("crm:HC-001", "crm:HC-017", "GR-006", "unsure"),
        ("crm:HC-018", "crm:HC-019", "GR-007", "unsure"),
    ):
        assert p[a] != p[b] and not merged(hard, a, b)
        item = next(i for i in hard["queue"] if {r["record_id"] for r in i["records"]} == {a, b})
        assert rule in item["rule_ids"] and item["suggestion"] == suggestion
    for a in ("crm:HC-003", "crm:HC-004"):
        assert p[a] != p["crm:HC-016"] and not merged(hard, a, "crm:HC-016")
        item = next(
            i for i in hard["queue"] if {r["record_id"] for r in i["records"]} == {a, "crm:HC-016"}
        )
        assert item["pairs"][0]["evidence"]["dob"] == "far"
        assert item["suggestion"] != "same_person"
    # A unique name plus DOB with no location conflict still auto-merges (Dave and David).
    assert merged(hard, "crm:HC-009", "enrollment:9")


def test_committed_demo_regenerates_byte_identical(tmp_path: Path) -> None:
    """`npm run demo` into a temp folder must equal the committed public demo, byte for byte."""
    script = json.loads((FIXTURES.parent / "package.json").read_text())["scripts"]["demo"]
    args = shlex.split(script.split("bob-resolve ", 1)[1])
    i = args.index("--out")
    args[i + 1] = str(tmp_path)
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    committed = FIXTURES.parent / "dashboard/public/demo-run"
    fresh = tmp_path / "demo-run"
    assert sorted(p.name for p in fresh.iterdir()) == sorted(p.name for p in committed.iterdir())
    for p in sorted(committed.iterdir()):
        assert (fresh / p.name).read_bytes() == p.read_bytes(), p.name
