"""Synthetic orchestration probes; expensive matching is replaced with a tiny stub."""

from datetime import UTC, date, datetime

import bob_resolve.run as run


def test_overwrite_cannot_replace_input_tree(tmp_path, monkeypatch):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    sentinel = fixtures / "synthetic-input.txt"
    sentinel.write_text("preserve synthetic input\n")
    options = run.RunOptions(
        fixtures=fixtures,
        side="snapshot",
        shared_ids=True,
        out=tmp_path,
        run_id="fixtures",
        as_of=date(2026, 10, 1),
        now=datetime(2026, 10, 1, tzinfo=UTC),
        frozen_clock=True,
        overwrite=True,
    )
    monkeypatch.setattr(run, "compute", lambda *args: {})

    def write(o, c, target, parent):
        (target / "synthetic-output.txt").write_text("synthetic output\n")

    monkeypatch.setattr(run, "write_folder", write)
    try:
        run.execute(options)
    except run.RunRefused:
        pass
    print("OBSERVED overwrite preserved input tree:", sentinel.exists())
    assert sentinel.exists(), "overwrite removed the input fixtures tree"
