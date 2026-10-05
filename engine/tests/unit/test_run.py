"""PR 7: the run folder is immutable and repeatable, and review apply only appends."""

import json
from pathlib import Path

from typer.testing import CliRunner

from bob_resolve.cli import app
from bob_resolve.queue import mask_mbi
from bob_resolve.run import verify_folder

NOW = ["--now", "2026-10-01T12:00:00+00:00"]


def run(out: Path, run_id: str, *extra: str) -> tuple[int, str]:
    args = ["run", "--enrollment", "hard-cases", "--out", str(out), "--run-id", run_id]
    r = CliRunner().invoke(app, [*args, *NOW, *extra])
    return r.exit_code, r.output


def files(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())}


def test_run_is_byte_identical_and_refuses_to_overwrite(tmp_path: Path) -> None:
    assert run(tmp_path, "a")[0] == 0 and run(tmp_path / "again", "a")[0] == 0
    a = files(tmp_path / "a")
    assert set(a) == {"manifest.json", "people.csv", "people.parquet", "households.json",
                      "merge_log.jsonl", "review_queue.jsonl", "scorecard.json"}  # fmt: skip
    assert files(tmp_path / "again" / "a") == a
    code, out = run(tmp_path, "a")
    assert code == 1 and "immutable" in out and files(tmp_path / "a") == a
    assert run(tmp_path, "a", "--overwrite")[0] == 0 and files(tmp_path / "a") == a
    m = verify_folder(tmp_path / "a")
    assert m["timings_ms"] is None and str(tmp_path) not in json.dumps(m)


def test_mask_mbi_keeps_last_four() -> None:
    assert mask_mbi("9AA0-AA0-AA01") == "*******AA01" and mask_mbi(None) is None


def test_review_apply_appends_and_never_touches_the_old_run(tmp_path: Path) -> None:
    run(tmp_path, "r1")
    old = files(tmp_path / "r1")
    queue = [json.loads(x) for x in old["review_queue.jsonl"].splitlines()]

    def item_for(ids: set[str]) -> str:
        return next(i["item_id"] for i in queue if {r["record_id"] for r in i["records"]} == ids)

    nina = item_for({"crm:HC-008", "enrollment:8"})
    twins = item_for({"crm:HC-012", "crm:HC-013"})
    when = "2026-10-02T09:00:00+00:00"
    labels = [
        {"item_id": nina, "decision": "same_person", "reviewer": "ops-1", "decided_at": when},
        {"item_id": twins, "decision": "different_people", "reviewer": "ops-1", "decided_at": when},
    ]
    dec = tmp_path / "decisions.jsonl"
    dec.write_text("".join(json.dumps(x) + "\n" for x in labels))
    args = ["review", "apply", "--run", str(tmp_path / "r1"), "--decisions", str(dec)]
    r = CliRunner().invoke(app, [*args, "--out", str(tmp_path), "--run-id", "r2", *NOW])
    assert r.exit_code == 0, r.output
    assert "1 decisions applied, 1 stored only" in r.output
    assert files(tmp_path / "r1") == old  # the old run is never changed
    new = files(tmp_path / "r2")
    assert new["merge_log.jsonl"].startswith(old["merge_log.jsonl"])
    added = [
        json.loads(x) for x in new["merge_log.jsonl"][len(old["merge_log.jsonl"]) :].splitlines()
    ]
    assert [(e["a"], e["b"], e["tier"], e["rule_ids"], e["run_id"]) for e in added] == [
        ("crm:HC-008", "enrollment:8", "review", ["REVIEW-DECISION"], "r2")
    ]
    ids = {json.loads(x)["item_id"] for x in new["review_queue.jsonl"].splitlines()}
    assert nina not in ids and twins not in ids
    assert len(new["decisions.jsonl"].splitlines()) == 2
    assert json.loads(new["manifest.json"])["parent_run_id"] == "r1"


def test_review_apply_refuses_unknown_items(tmp_path: Path) -> None:
    run(tmp_path, "r1")
    dec = tmp_path / "d.jsonl"
    line = {"item_id": "rq-nope", "decision": "same_person", "reviewer": "x",
            "decided_at": "2026-10-02T09:00:00+00:00"}  # fmt: skip
    dec.write_text(json.dumps(line) + "\n")
    args = ["review", "apply", "--run", str(tmp_path / "r1"), "--decisions", str(dec)]
    r = CliRunner().invoke(app, [*args, "--out", str(tmp_path), "--run-id", "r2"])
    assert r.exit_code == 1 and not (tmp_path / "r2").exists()
