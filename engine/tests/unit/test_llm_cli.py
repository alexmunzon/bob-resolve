"""End-to-end saved explanations replayed offline, with explicitly synthetic provenance."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import bob_resolve.llm.run as llm_run
from bob_resolve.cli import app


def test_off_pending_invalid_and_replayed_runs_preserve_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    cassette_dir = tmp_path / "cassettes"
    cassette_dir.mkdir()
    seen: list[tuple[str, str]] = []
    real = llm_run.review_pair

    def spy(*args: Any, **kwargs: Any) -> Any:
        result = real(*args, **kwargs)
        seen.append((result.request_key, result.model))
        return result

    monkeypatch.setattr(llm_run, "review_pair", spy)
    args = [
        "run",
        "--enrollment",
        "hard-cases",
        "--out",
        str(tmp_path),
        "--no-parquet",
        "--now",
        "2026-10-01T12:00:00+00:00",
        "--llm-cassettes",
        str(cassette_dir),
    ]

    def run(name: str, mode: str) -> tuple[dict, list[dict]]:
        result = runner.invoke(app, [*args, "--run-id", name, "--llm-mode", mode])
        assert result.exit_code == 0, result.output
        folder = tmp_path / name
        manifest = json.loads((folder / "manifest.json").read_text())
        sidecar = folder / "llm_assessments.jsonl"
        rows = [json.loads(x) for x in sidecar.read_text().splitlines()] if sidecar.exists() else []
        return manifest, rows

    off, rows = run("off", "off")
    assert not rows and off["llm"]["calls"] == 0
    pending, rows = run("pending", "replay")
    assert pending["llm"]["pending"] > 0 and pending["llm"]["invalid"] == 0
    key, model = seen[0]
    cassette = cassette_dir / (key + ".json")
    cassette.write_text("{invalid")
    invalid, _ = run("invalid", "replay")
    assert invalid["llm"]["invalid"] == 1
    assert invalid["llm"]["pending"] == pending["llm"]["pending"] - 1
    cassette.write_text(
        json.dumps(
            {
                "request_key": key,
                "model": model,
                "rationale": "Synthetic test rationale, retain human review.",
                "provenance": "synthetic-test-stub-not-model-output",
                "cost_usd": 0,
            }
        )
    )
    replay, rows = run("replayed", "replay")
    assert replay["llm"]["replayed"] >= 1
    assert replay["llm"]["calls"] == replay["llm"]["cost_usd"] == 0
    assert all(x["requires_human_review"] for x in rows)
    for name in ("pending", "invalid", "replayed"):
        for filename in ("people.csv", "households.json", "review_queue.jsonl"):
            assert (tmp_path / "off" / filename).read_bytes() == (
                tmp_path / name / filename
            ).read_bytes()
