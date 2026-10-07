"""Release 0.1.0 review findings: review apply cannot clobber its parent (F5), counts only kept
merges (F6), severity (F7), and the public demo never carries a full MBI (F9)."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bob_resolve import __version__
from bob_resolve.cli import app

NOW = ["--now", "2026-10-01T12:00:00+00:00"]
REPO = Path(__file__).resolve().parents[3]
WHEN = "2026-10-02T09:00:00+00:00"
# An MBI is 11 characters: digit, letter, letter or digit, digit, letter, letter or digit,
# digit, letter, letter, digit, digit. Dashes are allowed between the groups.
MBI_SHAPE = re.compile(
    r"(?<![A-Za-z0-9*])[1-9][A-Z][A-Z0-9][0-9]-?[A-Z][A-Z0-9][0-9]-?[A-Z]{2}[0-9]{2}(?![A-Za-z0-9])"
)


def cli(*args: str) -> tuple[int, str]:
    r = CliRunner().invoke(app, [*args, *NOW])
    return r.exit_code, r.output


def run(out: Path, run_id: str, *extra: str) -> Path:
    code, output = cli("run", "--enrollment", "hard-cases", "--out", str(out), "--run-id", run_id,
                       "--no-parquet", *extra)  # fmt: skip
    assert code == 0, output
    return out / run_id


def files(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())}


def queue(run: Path) -> list[dict[str, object]]:
    return [json.loads(x) for x in (run / "review_queue.jsonl").read_text().splitlines()]


def item_for(run: Path, *ids: str) -> str:
    want = set(ids)
    return next(
        str(i["item_id"])
        for i in queue(run)
        if {r["record_id"] for r in i["records"]} == want  # type: ignore[attr-defined]
    )


def decisions(path: Path, *item_ids: str) -> Path:
    lines = [{"item_id": i, "decision": "same_person", "reviewer": "ops-1", "decided_at": WHEN}
             for i in item_ids]  # fmt: skip
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def apply(old: Path, dec: Path, out: Path, run_id: str, *extra: str) -> tuple[int, str]:
    return cli("review", "apply", "--run", str(old), "--decisions", str(dec), "--out", str(out),
               "--run-id", run_id, "--no-parquet", *extra)  # fmt: skip


def test_f5_review_apply_refuses_to_replace_its_own_parent(tmp_path: Path) -> None:
    x = run(tmp_path / "runs", "x")
    before = files(x)
    dec = decisions(tmp_path / "d.jsonl", item_for(x, "crm:HC-008", "enrollment:8"))
    # The reviewer's case: same folder, same id, --overwrite.
    code, out = apply(x, dec, x.parent, "x", "--overwrite")
    assert code == 1 and "parent" in out
    assert files(x) == before
    # A new folder that holds the old run, or sits inside it, is refused too.
    code, _ = apply(x, dec, tmp_path, "runs", "--overwrite")
    assert code == 1 and files(x) == before
    code, _ = apply(x, dec, x, "child")
    assert code == 1 and not (x / "child").exists() and files(x) == before
    # A symlink to the runs folder resolves to the same place.
    (tmp_path / "link").symlink_to(x.parent)
    code, _ = apply(x, dec, tmp_path / "link", "x", "--overwrite")
    assert code == 1 and files(x) == before
    # The new run id may not equal the parent's, even in another folder.
    code, out = apply(x, dec, tmp_path / "elsewhere", "x")
    assert code == 1 and not (tmp_path / "elsewhere" / "x").exists()


def test_f6_decisions_applied_counts_only_kept_merges(tmp_path: Path) -> None:
    r1 = run(tmp_path, "r1")
    # PR 21a: HC-007 and HC-008 have birth dates far apart, so they conflict, and HC-007 also
    # conflicts with enrollment:8. Both reviewed links lie on the path between those records, so
    # both are held for review again: neither counts as applied and neither is logged as a merge.
    kept = item_for(r1, "crm:HC-008", "enrollment:8")
    cut = item_for(r1, "crm:HC-007", "crm:HC-008")
    code, out = apply(r1, decisions(tmp_path / "d.jsonl", kept, cut), tmp_path, "r2")
    assert code == 0, out
    assert "0 decisions applied" in out and "2 cut by the cluster check" in out
    m = json.loads((tmp_path / "r2/manifest.json").read_text())
    assert m["decisions_applied"] == 0
    assert m["decisions_cut"] == [["crm:HC-007", "crm:HC-008"], ["crm:HC-008", "enrollment:8"]]
    log = (tmp_path / "r2/merge_log.jsonl").read_text().splitlines()
    review_lines = [json.loads(x) for x in log if '"tier": "review"' in x]
    assert [e for e in review_lines if e["action"] == "merge"] == []
    assert sorted((e["a"], e["b"]) for e in review_lines if e["action"] == "split") == [
        ("crm:HC-007", "crm:HC-008"),
        ("crm:HC-008", "enrollment:8"),
    ]


def test_f6_a_second_review_keeps_the_first_reviews_merges(tmp_path: Path) -> None:
    r1 = run(tmp_path, "r1")
    nina = item_for(r1, "crm:HC-008", "enrollment:8")
    assert apply(r1, decisions(tmp_path / "d1.jsonl", nina), tmp_path, "r2")[0] == 0
    r2 = tmp_path / "r2"
    other = str(queue(r2)[-1]["item_id"])
    dec2 = tmp_path / "d2.jsonl"
    dec2.write_text(json.dumps({"item_id": other, "decision": "different_people",
                                "reviewer": "ops-2", "decided_at": WHEN}) + "\n")  # fmt: skip
    assert apply(r2, dec2, tmp_path, "r3")[0] == 0
    people = (tmp_path / "r3/people.csv").read_text()
    assert any("crm:HC-008" in x and "enrollment:8" in x for x in people.splitlines())
    m = json.loads((tmp_path / "r3/manifest.json").read_text())
    assert m["review_pairs"] == [["crm:HC-008", "enrollment:8"]]
    assert len((tmp_path / "r3/decisions.jsonl").read_text().splitlines()) == 2


@pytest.mark.parametrize("ids", ["--shared-ids", "--no-shared-ids"])
def test_f7_severity_and_order(tmp_path: Path, ids: str) -> None:
    q = queue(run(tmp_path, "r", ids))
    for i in q:
        high = i["reason"] == "IDENTITY_CONFLICT" or (
            i["suggestion"] == "same_person"
            and len({r["record_id"] for r in i["records"] if r["active_policy"]}) == 2  # type: ignore[attr-defined]
        )
        if i["reason"] == "IDENTITY_CONFLICT":
            assert i["severity"] == "high"
        elif not high:
            assert i["severity"] == "medium", i
    # "different people" twins with active policies are not high: no merge is suggested.
    assert all(i["severity"] == "medium" for i in q if i["suggestion"] != "same_person"
               and i["reason"] != "IDENTITY_CONFLICT")  # fmt: skip
    keys = [(i["severity"] != "high", i["cutoff_distance"], i["item_id"]) for i in q]
    assert keys == sorted(keys)  # type: ignore[type-var]


def test_f7_cutoff_distance_is_from_the_nearer_line() -> None:
    from bob_resolve.config import SCORE_HIGH, SCORE_LOW
    from bob_resolve.queue import cutoff_distance

    assert cutoff_distance([0.5]) == pytest.approx(min(SCORE_HIGH - 0.5, 0.5 - SCORE_LOW))
    assert cutoff_distance([0.98, 0.2]) == pytest.approx(SCORE_HIGH - 0.98)
    assert cutoff_distance([]) == 0.0


def test_f9_public_folder_requires_masking(tmp_path: Path) -> None:
    code, out = cli("run", "--enrollment", "hard-cases", "--out", str(tmp_path / "public"),
                    "--run-id", "d", "--no-parquet")  # fmt: skip
    assert code == 1 and "mask" in out
    d = run(tmp_path / "public", "d", "--mask-mbi")
    assert not MBI_SHAPE.search((d / "people.csv").read_text())
    assert "*******AA01" in (d / "people.csv").read_text()
    full = run(tmp_path / "private", "d")  # outside public the synthetic MBI is kept
    assert MBI_SHAPE.search((full / "people.csv").read_text())


def test_f9_committed_public_demo_has_no_full_mbi() -> None:
    public = REPO / "dashboard/public"
    checked = 0
    for p in sorted(public.rglob("*")):
        if p.is_file():
            hits = MBI_SHAPE.findall(p.read_text(encoding="utf-8", errors="ignore"))
            assert not hits, f"{p.relative_to(REPO)} carries MBI-shaped values: {hits[:3]}"
            checked += 1
    assert checked >= 6
    assert MBI_SHAPE.search("5JR1EA3UD29") and MBI_SHAPE.search("9AA0-AA0-AA01")
    assert not MBI_SHAPE.search("*******UD29")


def test_f10_version_is_0_1_0() -> None:
    assert __version__ == "0.1.0"
    assert 'version = "0.1.0"' in (REPO / "engine/pyproject.toml").read_text()
    demo = json.loads((REPO / "dashboard/public/demo-run/manifest.json").read_text())
    assert demo["versions"]["engine"] == "0.1.0"


def test_f7_high_only_when_a_merge_would_move_money() -> None:
    from bob_resolve.queue import severity

    ids = ["crm:C-1", "enrollment:5"]
    assert severity("IDENTITY_CONFLICT", "unsure", ids, {}) == "high"
    two_clients = {"crm:C-1": "C-1", "enrollment:5": "C-2"}
    assert severity("GRAY_ZONE", "same_person", ids, two_clients) == "high"
    one_client = {"crm:C-1": "C-1", "enrollment:5": "C-1"}  # the row is C-1's own policy
    assert severity("GRAY_ZONE", "same_person", ids, one_client) == "medium"
    assert severity("GRAY_ZONE", "different_people", ids, two_clients) == "medium"
    assert severity("GRAY_ZONE", "same_person", ids, {"crm:C-1": "C-1"}) == "medium"
