"""PR 6: the merge log is append-only JSONL. A correction is a new line, never a rewrite."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from bob_resolve.mergelog import MergeLogEntry, append_entries, read_entries

T = datetime(2026, 10, 1, 12, 0, tzinfo=UTC).isoformat()


def _entry(a: str, b: str, **kw: object) -> MergeLogEntry:
    base: dict[str, object] = {
        "action": "merge",
        "a": a,
        "b": b,
        "tier": "rules",
        "score": 0.995,
        "rule_ids": ("AUTO-MATCH-HIGH",),
        "run_id": "r1",
        "time": T,
    }
    base.update(kw)
    return MergeLogEntry.model_validate(base)


def test_appending_never_rewrites_an_existing_line(tmp_path: Path) -> None:
    log = tmp_path / "merge_log.jsonl"
    assert append_entries(log, [_entry("crm:A", "crm:B"), _entry("crm:C", "crm:D")]) == 2
    before = log.read_bytes()
    fix = _entry("crm:A", "crm:B", action="correction", corrects_line=1, score=None, run_id="r2")
    append_entries(log, [fix])
    after = log.read_bytes()
    assert after.startswith(before) and after.count(b"\n") == 3
    entries = read_entries(log)
    assert entries[0] == _entry("crm:A", "crm:B")
    assert entries[2].action == "correction" and entries[2].corrects_line == 1


def test_a_log_whose_last_line_is_cut_off_is_refused(tmp_path: Path) -> None:
    log = tmp_path / "merge_log.jsonl"
    log.write_text('{"action": "merge"')
    with pytest.raises(ValueError, match="does not end with a newline"):
        append_entries(log, [_entry("crm:A", "crm:B")])
    assert log.read_text() == '{"action": "merge"'


def test_a_correction_must_name_the_line_it_corrects() -> None:
    with pytest.raises(ValueError):
        _entry("crm:A", "crm:B", action="correction")
