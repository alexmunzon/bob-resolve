"""Hand-written synthetic fixtures. No model/provider calls or match approval."""

import json
import socket
from datetime import date

import pytest
from test_intake_adapter import packet
from typer.testing import CliRunner

from bob_resolve.adapters.contract import canonical_json
from bob_resolve.adapters.intake import resolve_intake
from bob_resolve.advisory.sidecar import build_sidecar
from bob_resolve.cli import app


def setup(root):
    source = packet(root)
    source = source.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"phone": None, "address_line1": None}) for c in source.clients
            )
        }
    )
    result = resolve_intake(source, root, run_id="bob-1", as_of=date(2026, 10, 1))
    return source, canonical_json(result).encode()


def fixture(entry, **changes):
    return json.dumps(
        dict(
            version="bob-second-opinion-v1",
            request_key=entry.request.key,
            origin="hand_written_synthetic_fixture",
            opinion="unsure",
            evidence=["dob"],
        )
        | changes
    ).encode()


def test_replay_is_bound_additive_cited_and_offline(tmp_path, monkeypatch):
    source, raw = setup(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def no_network(*args, **kwargs):
        pytest.fail("network attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    off = build_sidecar(source, raw, tmp_path)
    assert len(off.entries) == 1
    entry = off.entries[0]
    assert entry.result.status == "off"
    assert len(entry.citations) == 2
    assert "Taylor" not in entry.request.model_dump_json()
    assert "record-" not in entry.request.model_dump_json()
    responses = tmp_path / "fixtures"
    responses.mkdir()
    (responses / f"{entry.request.key}.json").write_bytes(fixture(entry))
    replay = build_sidecar(source, raw, tmp_path, mode="replay", responses=responses)
    assert replay.entries[0].result.status == "replayed"
    assert replay.entries[0].result.review_state == "needs_review"
    assert replay.entries[0].result.calls == 0
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())
    assert build_sidecar(source, raw, tmp_path, responses=responses) == off
    assert build_sidecar(source, raw, tmp_path, mode="replay").entries[0].result.status == "pending"


@pytest.mark.parametrize(
    "kind", ["stale", "malformed", "oversized", "contradictory", "symlink", "missing", "fifo"]
)
def test_bad_fixtures_pending(tmp_path, kind):
    source, raw = setup(tmp_path)
    entry = build_sidecar(source, raw, tmp_path).entries[0]
    responses = tmp_path / "fixtures"
    responses.mkdir()
    path = responses / f"{entry.request.key}.json"
    content = fixture(entry)
    if kind == "stale":
        content = fixture(entry, request_key="0" * 64)
    elif kind == "malformed":
        content = b"not json"
    elif kind == "oversized":
        content = b" " * 8193
    elif kind == "contradictory":
        content = fixture(entry, opinion="same_person")
    if kind == "fifo":
        import os

        os.mkfifo(path)
    elif kind == "missing":
        pass
    elif kind == "symlink":
        target = tmp_path / "elsewhere.json"
        target.write_bytes(content)
        path.symlink_to(target)
    else:
        path.write_bytes(content)
    r = build_sidecar(source, raw, tmp_path, mode="replay", responses=responses).entries[0].result
    assert r.status == "pending" and r.suggestion is None


def test_modified_source_or_scoring_refused(tmp_path):
    source, raw = setup(tmp_path)
    modified = json.loads(raw)
    modified["scored_pairs"][0]["score"] = 0.4
    with pytest.raises(ValueError, match="deterministic"):
        build_sidecar(source, json.dumps(modified).encode(), tmp_path)
    (tmp_path / "clients.csv").write_text("tampered")
    with pytest.raises(ValueError):
        build_sidecar(source, raw, tmp_path)


def test_cli_no_overwrite_and_no_input_mutation(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    source, raw = setup(root)
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(canonical_json(source))
    resolution = tmp_path / "resolution.json"
    resolution.write_bytes(raw)
    out = tmp_path / "sidecar.json"
    args = [
        "advisory",
        "sidecar",
        "--source-packet",
        str(packet_path),
        "--resolution",
        str(resolution),
        "--intake-root",
        str(root),
        "--out",
        str(out),
    ]
    runner = CliRunner()
    assert runner.invoke(app, args).exit_code == 0
    before = out.read_bytes()
    assert runner.invoke(app, args).exit_code == 2
    assert out.read_bytes() == before and resolution.read_bytes() == raw
    assert runner.invoke(app, args[:-1] + [str(root / "new.json")]).exit_code == 2


def test_off_never_reads_fixture_directory(tmp_path, monkeypatch):
    from pathlib import Path

    source, raw = setup(tmp_path)
    original = Path.open
    responses = tmp_path / "must-not-read"

    def guarded_open(self, *args, **kwargs):
        if self.is_relative_to(responses):
            pytest.fail("off mode opened response fixture")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert (
        build_sidecar(source, raw, tmp_path, responses=responses).entries[0].result.status == "off"
    )


def test_changed_run_does_not_reuse_fixture(tmp_path):
    source, raw = setup(tmp_path)
    first = build_sidecar(source, raw, tmp_path).entries[0]
    responses = tmp_path / "fixtures"
    responses.mkdir()
    (responses / f"{first.request.key}.json").write_bytes(fixture(first))
    changed = resolve_intake(source, tmp_path, run_id="bob-2", as_of=date(2026, 10, 1))
    second = build_sidecar(
        source, canonical_json(changed).encode(), tmp_path, mode="replay", responses=responses
    ).entries[0]
    assert second.request.key != first.request.key
    assert second.result.status == "pending" and second.result.suggestion is None


@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_fixture_swap_at_open_is_refused(tmp_path, monkeypatch, replacement):
    import os

    source, raw = setup(tmp_path)
    entry = build_sidecar(source, raw, tmp_path).entries[0]
    responses = tmp_path / "fixtures"
    responses.mkdir()
    name = f"{entry.request.key}.json"
    path = responses / name
    path.write_bytes(fixture(entry))
    outside = tmp_path / "outside.json"
    outside.write_bytes(fixture(entry))
    original = os.open

    def swapping_open(file, flags, mode=0o777, *, dir_fd=None):
        if file == name:
            path.unlink()
            if replacement == "symlink":
                path.symlink_to(outside)
            else:
                os.mkfifo(path)
        return original(file, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {swapping_open})
    result = build_sidecar(source, raw, tmp_path, mode="replay", responses=responses)
    assert result.entries[0].result.status == "pending"
    assert result.entries[0].result.suggestion is None


def test_directory_swap_cannot_redirect_open(tmp_path, monkeypatch):
    import os

    source, raw = setup(tmp_path)
    entry = build_sidecar(source, raw, tmp_path).entries[0]
    responses = tmp_path / "fixtures"
    responses.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    name = f"{entry.request.key}.json"
    (outside / name).write_bytes(fixture(entry))
    original = os.open

    def swapping_open(file, flags, mode=0o777, *, dir_fd=None):
        if file == name:
            responses.rename(tmp_path / "pinned-original")
            responses.symlink_to(outside, target_is_directory=True)
        return original(file, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {swapping_open})
    result = build_sidecar(source, raw, tmp_path, mode="replay", responses=responses)
    assert result.entries[0].result.status == "pending"
    assert result.entries[0].result.suggestion is None
