"""Bounded synthetic correctness regressions. Run only with the isolated audit runner.

These tests express expected safe behavior and fail on captured implementations.
No fixtures are downloaded, no subprocess/server is started, and all files are temporary.
"""

import csv
import json
from datetime import UTC, date, datetime
from itertools import combinations
from pathlib import Path

import pytest

from bob_resolve.block import candidate_pairs
from bob_resolve.block import evaluate as evaluate_blocking
from bob_resolve.cluster import conflict_reasons
from bob_resolve.golden import build_golden, resolve
from bob_resolve.load import read_crm, to_records
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import normalize_record
from bob_resolve.run import RunOptions, RunRefused, apply_review, execute
from bob_resolve.score import score_pair
from bob_resolve.truth import AnswerKey

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_duplicate_csv_ids_are_refused_before_scoring(tmp_path):
    fixtures = synthetic_world(
        tmp_path,
        [
            {"client_id": "A", "first_name": "Ada", "last_name": "Vance", "dob": "1950-01-01"},
            {"client_id": "A", "first_name": "Boris", "last_name": "Quill", "dob": "1950-01-01"},
        ],
        [],
    )
    frame = read_crm(fixtures / "hard-cases/clients.csv", NOW.date())
    with pytest.raises(ValueError, match="Duplicate"):
        to_records(frame, "crm")


@pytest.mark.parametrize("shared_ids,conflicts", [(True, False), (False, True)])
def test_gr006_cluster_check_obeys_shared_identifier_mode(shared_ids, conflicts):
    a = normalize_record(
        record(
            "crm:A", first_name="Ellen", last_name="Quarry", dob=date(1952, 2, 3), mbi="9ZZ0ZZ0ZZ01"
        )
    )
    b = normalize_record(
        record(
            "crm:B", first_name="Ellen", last_name="Quarry", dob=date(1925, 2, 3), mbi="9ZZ0ZZ0ZZ01"
        )
    )
    assert bool(conflict_reasons(a, b, shared_ids=shared_ids)) is conflicts


def test_negative_constraint_survives_multiple_applies(tmp_path):
    fixtures = synthetic_world(
        tmp_path / "fixtures",
        [
            {"client_id": c, "first_name": "James", "last_name": "Smith", "dob": "1950-02-03"}
            for c in "ABC"
        ],
        [],
    )
    (fixtures / "hard-cases/expected.json").write_text(
        json.dumps(
            {
                "people": {"A": ["crm:A", "crm:C"], "B": ["crm:B"]},
                "must_not_merge": [],
                "same_person": [],
            }
        )
    )
    out = tmp_path / "runs"
    first = execute(options(fixtures, out, "r1"))
    ids = {
        tuple(sorted(r["record_id"] for r in item["records"])): item["item_id"]
        for item in queue(first)
    }
    second, *_ = apply_review(
        first,
        decisions(tmp_path / "d1.jsonl", [(ids[("crm:A", "crm:B")], "different_people")]),
        options(fixtures, out, "r2"),
    )
    third, *_ = apply_review(
        second,
        decisions(tmp_path / "d2.jsonl", [(ids[("crm:A", "crm:C")], "same_person")]),
        options(fixtures, out, "r3"),
    )
    with pytest.raises(RunRefused, match="different_people"):
        apply_review(
            third,
            decisions(tmp_path / "d3.jsonl", [(ids[("crm:B", "crm:C")], "same_person")]),
            options(fixtures, out, "r4"),
        )
    assert third.exists() and not (out / "r4").exists()


def record(rid: str, row: int = 1, **fields) -> PersonRecord:
    return PersonRecord(
        record_id=rid,
        source=rid.split(":")[0],
        lineage=Lineage(source_file="synthetic/source.csv", row_number=row, raw_sha256="0" * 64),
        **{"first_name": None, "last_name": None, "dob": None, "mbi": None, **fields},
    )


def options(fixtures: Path, out: Path, run_id: str) -> RunOptions:
    return RunOptions(
        fixtures,
        "hard-cases",
        True,
        out,
        run_id,
        date(2026, 10, 1),
        NOW,
        True,
        parquet=False,
        mask_mbi=True,
    )


def synthetic_world(root: Path, crm_rows: list[dict], enrollment_rows: list[dict]) -> Path:
    hc = root / "hard-cases"
    hc.mkdir(parents=True)
    crm_columns = [
        "client_id",
        "first_name",
        "last_name",
        "dob",
        "mbi",
        "phone",
        "email",
        "address_line1",
        "city",
        "state",
        "zip",
        "household_id",
    ]
    enr_columns = [
        "member_first",
        "member_last",
        "Birth Dt (mm/dd/yy)",
        "policy_number",
        "mbi",
        "effective",
        "application_status",
    ]
    for name, rows, columns, delimiter in [
        ("clients.csv", crm_rows, crm_columns, ","),
        ("enrollment_export.csv", enrollment_rows, enr_columns, ";"),
    ]:
        with (hc / name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
    people = {r["client_id"]: [f"crm:{r['client_id']}"] for r in crm_rows}
    people.update({f"E{i}": [f"enrollment:{i}"] for i in range(1, len(enrollment_rows) + 1)})
    (hc / "expected.json").write_text(
        json.dumps({"people": people, "must_not_merge": [], "same_person": []})
    )
    return root


def queue(path: Path) -> list[dict]:
    return [json.loads(line) for line in (path / "review_queue.jsonl").read_text().splitlines()]


def decisions(path: Path, labels: list[tuple[str, str]]) -> Path:
    path.write_text(
        "".join(
            json.dumps(
                {
                    "item_id": item,
                    "decision": decision,
                    "reviewer": "synthetic-auditor",
                    "decided_at": NOW.isoformat(),
                }
            )
            + "\n"
            for item, decision in labels
        )
    )
    return path


@pytest.mark.parametrize(
    "given,surname,field,expected",
    [("Ada", None, "first_name", "Ada"), (None, "Vance", "last_name", "Vance")],
)
def test_partial_name_is_preserved(given, surname, field, expected):
    r = record("crm:A", first_name=given, last_name=surname)
    golden = build_golden([r], {}, {r.record_id: "single"})
    assert golden.fields[field].value == expected
    assert golden.fields[field].record_id == r.record_id


def test_duplicate_record_ids_are_rejected_before_lineage_is_lost():
    rs = [
        record("crm:A", 1, first_name="Ada", last_name="Vance"),
        record("crm:A", 2, first_name="Boris", last_name="Quill"),
    ]
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        resolve(rs, [], {}, run_id="synthetic", clock=lambda: NOW)


def test_negative_label_blocks_transitive_human_merge(tmp_path):
    fixtures = synthetic_world(
        tmp_path / "fixtures",
        [
            {"client_id": c, "first_name": "James", "last_name": "Smith", "dob": "1950-02-03"}
            for c in "ABC"
        ],
        [],
    )
    (fixtures / "hard-cases/expected.json").write_text(
        json.dumps(
            {
                "people": {"A": ["crm:A", "crm:C"], "B": ["crm:B"]},
                "must_not_merge": [],
                "same_person": [],
            }
        )
    )
    out = tmp_path / "runs"
    first = execute(options(fixtures, out, "r1"))
    items = {
        tuple(sorted(r["record_id"] for r in i["records"])): i["item_id"] for i in queue(first)
    }
    labels = [
        (items[("crm:A", "crm:B")], "different_people"),
        (items[("crm:A", "crm:C")], "same_person"),
        (items[("crm:B", "crm:C")], "same_person"),
    ]
    try:
        second, _, _, _ = apply_review(
            first, decisions(tmp_path / "labels.jsonl", labels), options(fixtures, out, "r2")
        )
    except Exception as error:
        # A specific safety refusal is also acceptable; unrelated exceptions are failures.
        assert "different" in str(error).lower() or "contradict" in str(error).lower()
        return
    with (second / "people.csv").open() as f:
        people = list(csv.DictReader(f))
    assert all(not {"crm:A", "crm:B"} <= set(p["record_ids"].split(";")) for p in people)


def test_recording_label_does_not_resolve_authoritative_identity_conflict(tmp_path):
    fixtures = synthetic_world(
        tmp_path / "fixtures",
        [],
        [
            {
                "member_first": "Ada",
                "member_last": "Vance",
                "Birth Dt (mm/dd/yy)": dob,
                "policy_number": str(i),
                "mbi": "9ZZ0ZZ0ZZ01",
                "effective": "20250101",
                "application_status": "Approved",
            }
            for i, dob in enumerate(["01/01/50", "01/07/50"], 1)
        ],
    )
    (fixtures / "hard-cases/expected.json").write_text(
        json.dumps(
            {
                "people": {"Ada": ["enrollment:1", "enrollment:2"]},
                "must_not_merge": [],
                "same_person": [],
            }
        )
    )
    out = tmp_path / "runs"
    first = execute(options(fixtures, out, "r1"))
    conflict = next(i for i in queue(first) if i["kind"] == "identity_conflict")
    second, kept, cut, stored = apply_review(
        first,
        decisions(tmp_path / "labels.jsonl", [(conflict["item_id"], "same_person")]),
        options(fixtures, out, "r2"),
    )
    assert (kept, cut, stored) == (0, 0, 1)
    with (second / "people.csv").open() as f:
        person = next(csv.DictReader(f))
    assert person["dob"] == "" and person["review_reasons"] == "IDENTITY_CONFLICT"
    assert any(i["reason"] == "IDENTITY_CONFLICT" for i in queue(second))


def test_cluster_rechecks_gr006_for_transitive_auto_merges():
    # A/B agree on MBI; B/C agree on phone. A/C share no additional identifier.
    rs = [
        record(
            "crm:A", first_name="Ellen", last_name="Quarry", dob=date(1952, 2, 3), mbi="9ZZ0ZZ0ZZ01"
        ),
        record(
            "crm:B",
            first_name="Ellen",
            last_name="Quarry",
            dob=date(1952, 2, 3),
            mbi="9ZZ0ZZ0ZZ01",
            phone="5555550199",
        ),
        record(
            "crm:C",
            first_name="Ellen",
            last_name="Quarry",
            dob=date(1925, 2, 3),
            phone="5555550199",
        ),
    ]
    norm = [normalize_record(r) for r in rs]
    scored = [score_pair(a, b) for a, b in combinations(norm, 2)]
    by_pair = {(p.a, p.b): p for p in scored}
    assert by_pair[("crm:A", "crm:B")].decision == "AUTO_MATCH"
    assert by_pair[("crm:B", "crm:C")].decision == "AUTO_MATCH"
    assert "GR-006" in by_pair[("crm:A", "crm:C")].guard_rails
    res = resolve(rs, scored, {}, run_id="synthetic", clock=lambda: NOW)
    assert all(not {"crm:A", "crm:C"} <= set(p.record_ids) for p in res.people)


def test_blocking_metrics_accept_zero_true_pairs():
    rs = [
        record("crm:A", first_name="Ada", last_name="Vance", dob=date(1950, 2, 3)),
        record("crm:B", first_name="James", last_name="Smith", dob=date(1960, 4, 5)),
    ]
    norm = [normalize_record(r) for r in rs]
    key = AnswerKey(clusters={"A": ("crm:A",), "B": ("crm:B",)})
    result = evaluate_blocking(candidate_pairs(norm, True), key, len(norm), True)
    assert result.true_pairs == 0 and result.recall == 1.0
