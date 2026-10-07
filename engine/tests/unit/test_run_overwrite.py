"""Failed replacement must preserve the last completed child and its parent."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import bob_resolve.run as run

REPO = Path(__file__).resolve().parents[3]


def snapshot(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@pytest.fixture
def completed_child(tmp_path: Path) -> tuple[Path, Path, run.RunOptions]:
    options = run.RunOptions(
        fixtures=REPO / "fixtures",
        side="hard-cases",
        shared_ids=True,
        out=tmp_path / "runs",
        run_id="parent",
        as_of=date(2026, 10, 7),
        now=datetime(2026, 10, 7, tzinfo=UTC),
        frozen_clock=True,
        parquet=False,
    )
    parent = run.execute(options)
    item = json.loads((parent / "review_queue.jsonl").read_text().splitlines()[0])
    decisions = tmp_path / "decisions.jsonl"
    decisions.write_text(
        json.dumps(
            {
                "item_id": item["item_id"],
                "decision": "same_person",
                "reviewer": "synthetic-overwrite-test",
                "decided_at": "2026-10-07T00:00:00+00:00",
            }
        )
        + "\n"
    )
    child_options = replace(options, run_id="child")
    run.apply_review(parent, decisions, child_options)
    return (
        parent,
        decisions,
        replace(child_options, overwrite=True, now=datetime(2026, 10, 8, tzinfo=UTC)),
    )


@pytest.mark.parametrize("error_type", [OSError, KeyboardInterrupt])
def test_failed_publication_restores_completed_child(
    completed_child: tuple[Path, Path, run.RunOptions],
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
) -> None:
    parent, decisions, options = completed_child
    child = options.out / options.run_id
    before, parent_before = snapshot(child), snapshot(parent)
    real_rename = Path.rename

    def interrupted(source: Path, target: Path) -> Path:
        if (
            source.name.startswith(".child-")
            and source.name != ".child-replaced"
            and target == child
        ):
            raise error_type("synthetic publication interruption")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(error_type, match="synthetic publication interruption"):
        run.apply_review(parent, decisions, options)
    assert child.exists()
    assert snapshot(child) == before
    assert snapshot(parent) == parent_before
    run.verify_folder(child)
    assert not list(options.out.glob(".child-*"))


def test_failed_rollback_keeps_completed_child_in_backup(
    completed_child: tuple[Path, Path, run.RunOptions], monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, decisions, options = completed_child
    child = options.out / options.run_id
    before, parent_before = snapshot(child), snapshot(parent)
    backup = options.out / ".child-replaced"
    real_rename = Path.rename

    def interrupted(source: Path, target: Path) -> Path:
        if target == child:
            raise OSError("synthetic publication and rollback interruption")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(OSError, match="synthetic publication and rollback interruption"):
        run.apply_review(parent, decisions, options)
    assert backup.exists()
    assert snapshot(backup) == before
    run.verify_folder(backup)
    assert snapshot(parent) == parent_before
    assert list(options.out.glob(".child-*")) == [backup]


def test_failed_writing_preserves_completed_child_and_existing_backup(
    completed_child: tuple[Path, Path, run.RunOptions], monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, decisions, options = completed_child
    child = options.out / options.run_id
    before, parent_before = snapshot(child), snapshot(parent)
    backup = options.out / ".child-replaced"
    backup.mkdir()
    (backup / "prior-output").write_bytes(b"recoverable previous output")
    backup_before = snapshot(backup)

    def interrupted(*args: object) -> None:
        raise OSError("synthetic writing interruption")

    monkeypatch.setattr(run, "write_folder", interrupted)
    with pytest.raises(OSError, match="synthetic writing interruption"):
        run.apply_review(parent, decisions, options)
    assert snapshot(child) == before
    assert snapshot(backup) == backup_before
    assert snapshot(parent) == parent_before
    assert list(options.out.glob(".child-*")) == [backup]


def test_successful_overwrite_publishes_new_child_and_removes_backup(
    completed_child: tuple[Path, Path, run.RunOptions],
) -> None:
    parent, decisions, options = completed_child
    parent_before = snapshot(parent)
    child, *_ = run.apply_review(parent, decisions, options)
    assert run.verify_folder(child)["created_at"] == options.now.isoformat()
    assert snapshot(parent) == parent_before
    assert not list(options.out.glob(".child-*"))
