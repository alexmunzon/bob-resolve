"""Saved explanations replayed offline are advisory only: no network path, no paid path, no
decision change, and a missing or broken saved explanation never stops a run.
All records here are synthetic."""

import ast
import json
import socket
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import bob_resolve.llm.run as llm_run
from bob_resolve.cli import app
from bob_resolve.llm.replay import MAX_CASSETTE_BYTES, plain_text, request_key, review_pair
from bob_resolve.llm.run import LABEL, evaluate_rationales
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.score.rules import GUARD_RAILS, ScoredPair

LLM_SRC = Path(__file__).resolve().parents[2] / "src" / "bob_resolve" / "llm"
FIELDS = {"first_name": ("Alex", "Alec"), "dob": ("1960-01-01", "1960-01-01")}
NOW = "2026-10-01T12:00:00+00:00"
# Byte-identical with replay on or off: everything a match decision touches.
DECISION_FILES = ("people.csv", "households.json", "members.jsonl", "review_queue.jsonl")


def _merge_log(folder: Path) -> list[dict]:
    """Merge log lines without the run id, which names the run and differs by design."""
    lines = [json.loads(x) for x in (folder / "merge_log.jsonl").read_text().splitlines()]
    return [{k: v for k, v in line.items() if k != "run_id"} for line in lines]


def _person(rid: str) -> PersonRecord:
    lineage = Lineage(source_file="synthetic.csv", row_number=1, raw_sha256="0" * 64)
    return PersonRecord(
        record_id=rid,
        source="crm",
        first_name="wren",
        last_name="halloway",
        dob=date(1938, 4, 12),
        mbi=None,
        address_line1="40 sample care way",
        lineage=lineage,
    )


def _gr008_pair() -> tuple[ScoredPair, dict[str, PersonRecord]]:
    pair = ScoredPair.model_construct(
        a="crm:R-1",
        b="crm:R-2",
        score=0.9,
        decision="GRAY",
        guard_rails=("GR-008",),
        reason=None,
        suggestion=None,
    )
    return pair, {"crm:R-1": _person("crm:R-1"), "crm:R-2": _person("crm:R-2")}


def test_every_current_guard_rail_is_accepted_including_gr_008() -> None:
    for rail in GUARD_RAILS:
        assert request_key(FIELDS, guardrail_ids=(rail,))
    with pytest.raises(ValueError, match="guardrail"):
        request_key(FIELDS, guardrail_ids=("GR-999",))


@pytest.mark.parametrize("mode", ["off", "replay"])
def test_gr_008_pair_never_crashes(tmp_path: Path, mode: Any) -> None:
    pair, records = _gr008_pair()
    rows, usage = evaluate_rationales(
        [pair], records, {}, mode=mode, cassette_dir=tmp_path, shared_ids=False
    )
    assert usage["calls"] == 0 and usage["cost_usd"] == 0.0
    if mode == "off":
        assert rows == []
    else:
        assert [r["status"] for r in rows] == ["pending"]
        assert rows[0]["guardrail_ids"] == ("GR-008",)


def test_any_advisory_error_becomes_invalid_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair, records = _gr008_pair()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(llm_run, "review_pair", boom)
    rows, usage = evaluate_rationales(
        [pair], records, {}, mode="replay", cassette_dir=tmp_path, shared_ids=True
    )
    assert [r["status"] for r in rows] == ["invalid"] and usage["invalid"] == 1
    assert rows[0]["rationale"] is None and rows[0]["requires_human_review"]


def test_high_stakes_follows_spec_any_active_policy(tmp_path: Path) -> None:
    pair, records = _gr008_pair()
    for owners, model in (({}, "sonnet"), ({"crm:R-1": "R-1"}, "opus")):
        rows, _ = evaluate_rationales(
            [pair], records, owners, mode="replay", cassette_dir=tmp_path, shared_ids=True
        )
        assert rows[0]["model"] == model


def test_llm_package_imports_no_network_or_model_client() -> None:
    banned = {
        "anthropic",
        "openai",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "http",
        "aiohttp",
        "socket",
        "jev_client",
        "bob_resolve.jev",
        "os",
        "subprocess",
    }
    for path in sorted(LLM_SRC.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in banned, f"{path.name} imports {name}"
                assert name not in banned, f"{path.name} imports {name}"
        for needle in ("API_KEY", "environ", "getenv", "dotenv"):
            assert needle not in text, f"{path.name} mentions {needle}"


def _run(tmp: Path, name: str, mode: str, cassettes: Path, *extra: str) -> Path:
    args = ["run", "--enrollment", "hard-cases", "--out", str(tmp), "--no-parquet"]
    args += ["--now", NOW, "--run-id", name]
    args += ["--llm-mode", mode, "--llm-cassettes", str(cassettes), *extra]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return tmp / name


def _rows(folder: Path) -> list[dict]:
    return [json.loads(x) for x in (folder / "llm_assessments.jsonl").read_text().splitlines()]


def _capture_keys(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Request keys and models the run looked for, so a test can save explanations for them."""
    seen: list[tuple[str, str]] = []
    real = llm_run.review_pair

    def spy(*args: Any, **kwargs: Any) -> Any:
        result = real(*args, **kwargs)
        seen.append((result.request_key, result.model))
        return result

    monkeypatch.setattr(llm_run, "review_pair", spy)
    return seen


def _saved(key: str, model: str, text: str = "Synthetic test text. A person still decides.") -> str:
    return json.dumps(
        {
            "request_key": key,
            "model": model,
            "rationale": text,
            "provenance": "synthetic-test-stub-not-model-output",
            "cost_usd": 0,
        }
    )


@pytest.mark.parametrize("shared", ["--shared-ids", "--no-shared-ids"])
def test_replay_without_network_keeps_every_decision_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shared: str
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    seen = _capture_keys(monkeypatch)
    cassettes = tmp_path / "saved"
    cassettes.mkdir()
    off = _run(tmp_path, "off", "off", cassettes, shared)
    assert seen == []  # off never even builds a request
    missing = _run(tmp_path, "missing", "replay", cassettes, shared)
    rows = _rows(missing)
    assert rows and all(r["status"] == "pending" for r in rows)
    assert len(seen) == len(rows)
    for i, (key, model) in enumerate(dict(seen).items()):
        path = cassettes / f"{key}.json"
        if i % 3 == 0:
            path.write_text("[" * 100_000)  # too deep to parse
        elif i % 3 == 1:
            path.mkdir()  # not a file
        else:
            path.write_text(_saved(key, model))
    mixed = _run(tmp_path, "mixed", "replay", cassettes, shared)
    rows = _rows(mixed)
    assert {r["status"] for r in rows} == {"invalid", "replayed"}
    assert all(r["requires_human_review"] and r["label"] == LABEL for r in rows)
    assert not any(k in r for r in rows for k in ("decision", "merge", "request_key"))
    m = json.loads((mixed / "manifest.json").read_text())
    assert m["llm"]["invalid"] > 0 and m["llm"]["replayed"] > 0 and m["llm"]["pending"] == 0
    for folder in (missing, mixed):
        for name in DECISION_FILES:
            assert (off / name).read_bytes() == (folder / name).read_bytes(), name
        assert _merge_log(off) == _merge_log(folder)
        a = json.loads((off / "scorecard.json").read_text())
        b = json.loads((folder / "scorecard.json").read_text())
        assert b["per_tier"]["llm"]["mode"] == "replay"
        b["per_tier"]["llm"]["mode"] = "off"
        assert a == b  # same rail hits, queue, metrics and counts
        ma = json.loads((off / "manifest.json").read_text())
        mb = json.loads((folder / "manifest.json").read_text())
        assert ma["review_pairs"] == mb["review_pairs"]
        assert mb["llm"]["calls"] == 0 and mb["llm"]["cost_usd"] == 0.0
        assert mb["llm"]["label"] == LABEL
    assert not (off / "llm_assessments.jsonl").exists()


def test_off_is_the_default_and_writes_no_explanations(tmp_path: Path) -> None:
    args = ["run", "--enrollment", "hard-cases", "--out", str(tmp_path), "--no-parquet"]
    result = CliRunner().invoke(app, [*args, "--now", NOW, "--run-id", "default"])
    assert result.exit_code == 0, result.output
    m = json.loads((tmp_path / "default" / "manifest.json").read_text())
    assert m["modes"]["llm"] == "off"
    assert m["llm"] == {"mode": "off", "calls": 0, "cost_usd": 0.0}
    assert not (tmp_path / "default" / "llm_assessments.jsonl").exists()
    assert "saved explanations" not in result.output


def test_off_mode_never_touches_the_saved_folder(tmp_path: Path) -> None:
    pair, records = _gr008_pair()
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x")
    blocker.chmod(0)
    rows, usage = evaluate_rationales(
        [pair], records, {}, mode="off", cassette_dir=blocker / "x", shared_ids=True
    )
    assert rows == [] and usage == {"mode": "off", "calls": 0, "cost_usd": 0.0}


def test_public_folder_refuses_replay(tmp_path: Path) -> None:
    public = tmp_path / "public"
    args = ["run", "--enrollment", "hard-cases", "--out", str(public), "--no-parquet", "--mask-mbi"]
    args += ["--now", NOW, "--run-id", "r", "--llm-mode", "replay"]
    args += ["--llm-cassettes", str(tmp_path)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert "never written there" in result.output
    assert not (public / "r").exists()


def test_cli_output_says_saved_and_offline(tmp_path: Path) -> None:
    cassettes = tmp_path / "saved"
    cassettes.mkdir()
    args = ["run", "--enrollment", "hard-cases", "--out", str(tmp_path), "--no-parquet"]
    args += ["--now", NOW, "--run-id", "r", "--llm-mode", "replay"]
    result = CliRunner().invoke(app, [*args, "--llm-cassettes", str(cassettes)])
    assert result.exit_code == 0, result.output
    lowered = result.output.lower()
    assert "saved explanations replayed offline" in lowered
    assert "no model was called" in lowered
    assert "live ai" not in lowered and "ai explains" not in lowered


def _write_one(tmp_path: Path, content: bytes | None = None, link: bool = False) -> Path:
    key = request_key(FIELDS)
    path = tmp_path / f"{key}.json"
    if link:
        target = tmp_path / "elsewhere.json"
        target.write_text(_saved(key, "sonnet"))
        path.symlink_to(target)
    else:
        path.write_bytes(content or b"")
    return path


@pytest.mark.parametrize(
    "case",
    ["symlink", "oversized", "non_utf8"],
)
def test_unsafe_saved_files_are_invalid(tmp_path: Path, case: str) -> None:
    key = request_key(FIELDS)
    if case == "symlink":
        _write_one(tmp_path, link=True)
    elif case == "oversized":
        padded = _saved(key, "sonnet", "x" * 1500) + " " * MAX_CASSETTE_BYTES
        _write_one(tmp_path, padded.encode())
    else:
        _write_one(tmp_path, b'{"rationale": "\xff\xfe"}')
    with pytest.raises(ValueError):
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path)


def test_rationale_is_plain_text_without_control_or_bidi_characters(tmp_path: Path) -> None:
    key = request_key(FIELDS)
    text = "Same‮ DOB\x1b[31m and​ name.\nA person decides."
    _write_one(tmp_path, _saved(key, "sonnet", text).encode())
    result = review_pair(FIELDS, mode="replay", cassette_dir=tmp_path)
    assert result.rationale == plain_text(text)
    assert not any(ch in result.rationale for ch in "‮\x1b​\n")
    _write_one(tmp_path, _saved(key, "sonnet", "‮​").encode())
    with pytest.raises(ValueError):
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path)


def test_review_apply_carries_the_replay_mode(tmp_path: Path) -> None:
    cassettes = tmp_path / "saved"
    cassettes.mkdir()
    first = _run(tmp_path, "first", "replay", cassettes)
    items = [json.loads(x) for x in (first / "review_queue.jsonl").read_text().splitlines()]
    item = next(i for i in items if i["kind"] == "gray_pair")
    decisions = tmp_path / "d.jsonl"
    decisions.write_text(
        json.dumps(
            {"item_id": item["item_id"], "decision": "same_person", "reviewer": "r1"}
            | {"decided_at": NOW}
        )
        + "\n"
    )
    args = ["review", "apply", "--run", str(first), "--decisions", str(decisions)]
    args += ["--out", str(tmp_path), "--run-id", "second", "--no-parquet", "--now", NOW]
    result = CliRunner().invoke(app, [*args, "--llm-cassettes", str(cassettes)])
    assert result.exit_code == 0, result.output
    m = json.loads((tmp_path / "second" / "manifest.json").read_text())
    assert m["modes"]["llm"] == "replay" and m["llm"]["calls"] == 0
    assert (tmp_path / "second" / "llm_assessments.jsonl").exists()


def test_unsafe_review_pair_modes_still_rejected(tmp_path: Path) -> None:
    for mode in ("live", "record"):
        with pytest.raises(ValueError, match="off or replay"):
            review_pair(FIELDS, mode=mode, cassette_dir=tmp_path)
