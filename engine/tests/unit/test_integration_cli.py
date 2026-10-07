"""Bob integration retains native evidence and refuses stale or malformed inputs."""

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bob_resolve.cli import app
from bob_resolve.integration_cli import _write_new

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/integration-v1"
RUNNER = CliRunner()


def test_workflow_registered_and_exports_native_demo_context(tmp_path: Path) -> None:
    result = RUNNER.invoke(app, ["workflow", "--help"])
    assert result.exit_code == 0
    assert "export" in result.output and "apply" in result.output
    demo = FIXTURE.parents[1] / "dashboard/public/demo-run"
    out = tmp_path / "context.json"
    args = [
        "workflow",
        "export",
        "--run",
        str(demo),
        "--agency-id",
        "synthetic-agency-a",
        "--intake-run-id",
        "intake-synthetic-v1",
        "--out",
        str(out),
    ]
    result = RUNNER.invoke(app, args)
    assert result.exit_code == 0, result.output
    original = out.read_bytes()
    context = json.loads(original)
    assert context["data_kind"] == "synthetic"
    assert context["identities"] and context["events"] == []
    assert RUNNER.invoke(app, args).exit_code == 1
    assert out.read_bytes() == original


def resolve(out: Path, *extra: str):
    return RUNNER.invoke(
        app,
        [
            "integration",
            "resolve",
            "--packet",
            str(FIXTURE / "intake-packet.json"),
            "--intake-root",
            str(FIXTURE / "intake-run"),
            "--agency-id",
            "synthetic-agency-a",
            "--intake-run-id",
            "intake-synthetic-v1",
            "--run-id",
            "bob-cli-v1",
            "--as-of",
            "2026-10-01",
            "--data-kind",
            "synthetic",
            "--out",
            str(out),
            *extra,
        ],
    )


def test_native_resolution_packet_extraction_and_immutable_retry(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    result = resolve(a)
    assert result.exit_code == 0, result.output
    assert resolve(b).exit_code == 0
    assert a.read_bytes() == b.read_bytes()
    original = a.read_bytes()
    assert resolve(a).exit_code == 2
    assert a.read_bytes() == original
    envelope = json.loads(original)
    assert envelope["resolution"]["people"]
    assert "scored_pairs" in envelope and "packet" in envelope
    packet = tmp_path / "packet.json"
    args = [
        "integration",
        "packet",
        "--resolution",
        str(a),
        "--agency-id",
        "synthetic-agency-a",
        "--run-id",
        "bob-cli-v1",
        "--data-kind",
        "synthetic",
        "--out",
        str(packet),
    ]
    assert RUNNER.invoke(app, args).exit_code == 0
    assert json.loads(packet.read_text()) == envelope["packet"]
    assert RUNNER.invoke(app, args).exit_code == 2


@pytest.mark.parametrize(
    "extra",
    [
        ("--agency-id", "wrong"),
        ("--intake-run-id", "wrong"),
        ("--run-id", " "),
        ("--as-of", "tomorrow"),
        ("--data-kind", "public"),
    ],
)
def test_explicit_metadata_refused(tmp_path: Path, extra: tuple[str, ...]) -> None:
    out = tmp_path / "out.json"
    assert resolve(out, *extra).exit_code == 2
    assert not out.exists()


def test_stale_input_and_malformed_packet_leave_no_output(tmp_path: Path) -> None:
    source = tmp_path / "intake"
    shutil.copytree(FIXTURE / "intake-run", source)
    with (source / "clean/clients.csv").open("a") as stream:
        stream.write("\n")
    out = tmp_path / "out.json"
    assert resolve(out, "--intake-root", str(source)).exit_code == 2
    assert not out.exists()
    bad = tmp_path / "bad.json"
    bad.write_text('{"secret-value":42}')
    result = resolve(out, "--packet", str(bad))
    assert result.exit_code == 2
    assert "secret-value" not in result.output
    assert not out.exists()


def test_atomic_race_preserves_winner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out.json"
    link = os.link

    def competing_link(source: str, target: Path) -> None:
        target.write_text("successful concurrent output")
        link(source, target)

    monkeypatch.setattr(os, "link", competing_link)
    with pytest.raises(FileExistsError):
        _write_new(out, "loser")
    assert out.read_text() == "successful concurrent output"
    assert list(tmp_path.iterdir()) == [out]


def test_failed_publish_cleans_staging_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "out.json"
    with monkeypatch.context() as patch:

        def fail(*args: object) -> None:
            raise OSError("disk failure")

        patch.setattr(os, "link", fail)
        with pytest.raises(OSError):
            _write_new(out, "complete\n")
    assert not list(tmp_path.iterdir())
    _write_new(out, "complete\n")
    assert out.read_text() == "complete\n"
