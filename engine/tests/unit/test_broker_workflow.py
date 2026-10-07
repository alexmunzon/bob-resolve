import json

import pytest

from bob_resolve.broker_workflow import apply, initial, validate


def run(tmp_path):
    folder = tmp_path / "parent"
    folder.mkdir()
    queue = {"item_id": "rq-1", "records": [{"record_id": "opaque-1"}]}
    (folder / "review_queue.jsonl").write_text(json.dumps(queue) + "\n")
    (folder / "people.csv").write_text("unchanged\n")
    from bob_resolve.run import sha256

    (folder / "manifest.json").write_text(
        json.dumps({"run_id": "parent", "outputs": {p.name: sha256(p) for p in folder.iterdir()}})
    )
    return folder


def event(kind, **kwargs):
    return dict(
        dict(
            event_id=kind,
            item_id="rq-1",
            kind=kind,
            actor="Synthetic reviewer",
            at="2026-10-07T12:00:00Z",
        ),
        **kwargs,
    )


def test_decision_does_not_resolve_evidence_and_child_history(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [
        event("request", text="Confirm identifier"),
        event("decision", text="Still missing", decision="same_person"),
    ]
    child = apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    assert child["cases"]["rq-1"]["status"] == "needs_evidence"
    assert child["cases"]["rq-1"]["decision"] == "same_person"
    assert (tmp_path / "child/people.csv").read_bytes() == (parent / "people.csv").read_bytes()
    next_draft = initial(tmp_path / "child", "agency", "intake")
    assert len(next_draft["history"]) == 2
    assert next_draft["events"] == []
    assert next_draft["base_hash"] != draft["base_hash"]
    with pytest.raises(ValueError, match="binding"):
        apply(
            tmp_path / "child",
            draft,
            tmp_path / "stale",
            agency_id="agency",
            intake_run_id="intake",
        )
    assert not (tmp_path / "stale").exists()


def test_response_and_acceptance_are_separate(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [
        event("assign", text="Synthetic owner"),
        event("request", text="Need source"),
        event(
            "response",
            request_id="request",
            text="Synthetic evidence",
            provenance={
                "source_file": "fixture.json",
                "sha256": "a" * 64,
                "row_number": 1,
                "received_at": "2026-10-07T12:00:00Z",
            },
        ),
    ]
    assert (
        validate(draft, initial(parent, "agency", "intake"))["rq-1"]["status"] == "needs_evidence"
    )
    draft["events"].append(
        event("accept", request_id="request", response_id="response", text="Checked source")
    )
    cases = validate(draft, initial(parent, "agency", "intake"))
    assert cases["rq-1"]["status"] == "evidence_reviewed"
    assert cases["rq-1"]["identity_state"] == "unresolved"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(queue_sha256="0" * 64),
        lambda d: d.update(run_id="other"),
        lambda d: d.update(agency_id="other"),
        lambda d: d.update(schema_version="9"),
        lambda d: d.update(unknown=True),
        lambda d: d["events"].append(
            event("accept", request_id="absent", response_id="none", text="x")
        ),
        lambda d: d["events"].extend([event("request", text="x"), event("request", text="x")]),
        lambda d: d["events"].append(event("decision", decision="merge", text="x")),
        lambda d: d["events"].append(event("assign", text="")),
        lambda d: d["events"].append(event("assign", text="x", item_id="missing")),
    ],
)
def test_invalid_imports(tmp_path, mutation):
    parent = run(tmp_path)
    expected = initial(parent, "agency", "intake")
    draft = json.loads(json.dumps(expected))
    mutation(draft)
    with pytest.raises(ValueError):
        validate(draft, expected)


def test_repeated_apply_refuses_overwrite(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("decision", text="No evidence", decision="different_people")]
    apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    before = (tmp_path / "child/broker_workflow.json").read_bytes()
    with pytest.raises(ValueError):
        apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    assert before == (tmp_path / "child/broker_workflow.json").read_bytes()


def test_native_review_carries_open_history_and_replay(tmp_path):
    from typer.testing import CliRunner

    from bob_resolve.cli import app
    from bob_resolve.run import verify_folder

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--enrollment",
            "hard-cases",
            "--out",
            str(tmp_path),
            "--run-id",
            "base",
            "--llm-mode",
            "replay",
            "--no-parquet",
        ],
    )
    assert result.exit_code == 0, result.output
    parent = tmp_path / "base"
    before = {p.name: p.read_bytes() for p in parent.iterdir()}
    draft = initial(parent, "agency", "intake")
    key = next(iter(draft["identities"]))
    draft["events"] = [
        event("request", item_id=key, text="Missing evidence"),
        event("decision", item_id=key, text="Label only", decision="same_person"),
    ]
    apply(parent, draft, tmp_path / "workflow", agency_id="agency", intake_run_id="intake")
    assert {p.name: p.read_bytes() for p in parent.iterdir()} == before
    assert (tmp_path / "workflow/llm_assessments.jsonl").read_bytes() == before[
        "llm_assessments.jsonl"
    ]
    label = tmp_path / "label.jsonl"
    label.write_text(
        json.dumps(
            dict(
                item_id=key,
                decision="different_people",
                reviewer="Synthetic",
                decided_at="2026-10-07T12:00:00Z",
            )
        )
    )
    result = runner.invoke(
        app,
        [
            "review",
            "apply",
            "--run",
            str(tmp_path / "workflow"),
            "--decisions",
            str(label),
            "--out",
            str(tmp_path),
            "--run-id",
            "review-child",
            "--no-parquet",
        ],
    )
    assert result.exit_code == 0, result.output
    verify_folder(tmp_path / "review-child")
    child_draft = initial(tmp_path / "review-child", "agency", "intake")
    assert key not in child_draft["identities"]
    assert validate(child_draft, child_draft)[key]["status"] == "needs_evidence"
    assert (tmp_path / "review-child/broker_workflow.json").read_bytes() == (
        tmp_path / "workflow/broker_workflow.json"
    ).read_bytes()


def test_changed_source_and_parent_overlap_refused(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic")]
    from bob_resolve.run import RunRefused

    with pytest.raises(RunRefused):
        apply(parent, draft, parent / "child", agency_id="agency", intake_run_id="intake")
    (parent / "review_queue.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="Stale"):
        apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")


def test_cli_scope_and_repeated_export(tmp_path):
    from typer.testing import CliRunner

    from bob_resolve.broker_workflow.__main__ import app

    parent = run(tmp_path)
    runner = CliRunner()
    path = tmp_path / "context.json"
    args = [
        "export",
        "--run",
        str(parent),
        "--agency-id",
        "agency",
        "--intake-run-id",
        "intake",
        "--out",
        str(path),
    ]
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, args).exit_code == 1
    draft = json.loads(path.read_text())
    draft["events"] = [event("assign", text="Synthetic owner")]
    path.write_text(json.dumps(draft))
    args = [
        "apply",
        "--run",
        str(parent),
        "--draft",
        str(path),
        "--out",
        str(tmp_path / "child"),
        "--agency-id",
        "other",
        "--intake-run-id",
        "intake",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 1 and "binding" in result.output
    assert not (tmp_path / "child").exists()
    args[args.index("other")] = "agency"
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, args).exit_code == 1


def test_deterministic_workflow_application(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    a = tmp_path / "one/child"
    b = tmp_path / "two/child"
    apply(parent, draft, a, agency_id="agency", intake_run_id="intake")
    apply(parent, draft, b, agency_id="agency", intake_run_id="intake")
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {
        p.name: p.read_bytes() for p in b.iterdir()
    }


def repin(folder, name):
    from bob_resolve.run import sha256

    path = folder / "manifest.json"
    data = json.loads(path.read_text())
    data["outputs"][name] = sha256(folder / name)
    path.write_text(json.dumps(data))


def test_duplicate_queue_ids_refused(tmp_path):
    parent = run(tmp_path)
    queue = parent / "review_queue.jsonl"
    queue.write_text(queue.read_text() * 2)
    repin(parent, queue.name)
    with pytest.raises(ValueError, match="Duplicate"):
        initial(parent, "agency", "intake")


def test_opaque_ids_preserved(tmp_path):
    parent = run(tmp_path)
    queue = parent / "review_queue.jsonl"
    queue.write_text(json.dumps({"item_id": " rq-1 ", "records": [{"record_id": " opaque-1 "}]}))
    repin(parent, queue.name)
    draft = initial(parent, " agency ", " intake ")
    draft["events"] = [event("assign", item_id=" rq-1 ", text="Synthetic owner")]
    ledger = apply(
        parent, draft, tmp_path / "child", agency_id=" agency ", intake_run_id=" intake "
    )
    assert ledger["agency_id"] == " agency "
    assert ledger["intake_run_id"] == " intake "
    assert list(ledger["cases"]) == [" rq-1 "]
    assert ledger["history"][0]["event"]["item_id"] == " rq-1 "


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version="9.0.0"),
        lambda d: d.update(unknown=True),
        lambda d: d.update(identity_changes_applied=1),
        lambda d: d.update(reviewer_authentication="authenticated"),
        lambda d: d["history"][0]["event"].update(unknown=True),
        lambda d: d["cases"]["rq-1"].update(status="evidence_reviewed"),
    ],
)
def test_malformed_saved_ledger_refused(tmp_path, mutation):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("request", text="Need source")]
    target = tmp_path / "child"
    ledger = apply(parent, draft, target, agency_id="agency", intake_run_id="intake")
    mutation(ledger)
    (target / "broker_workflow.json").write_text(json.dumps(ledger))
    repin(target, "broker_workflow.json")
    with pytest.raises(ValueError):
        initial(target, "agency", "intake")


def test_staging_creation_failure_releases_lock(tmp_path, monkeypatch):
    import bob_resolve.broker_workflow as workflow

    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]

    def fail(**kwargs):
        raise OSError("Synthetic staging failure")

    monkeypatch.setattr(workflow.tempfile, "mkdtemp", fail)
    with pytest.raises(OSError, match="staging failure"):
        apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    assert not (tmp_path / ".child.workflow-lock").exists()
    assert not (tmp_path / "child").exists()


def test_failed_copy_leaves_no_child_and_preserves_parent(tmp_path, monkeypatch):
    import bob_resolve.broker_workflow as workflow

    parent = run(tmp_path)
    before = {p.name: p.read_bytes() for p in parent.iterdir()}
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    original = workflow.shutil.copyfile

    def stale_copy(source, target):
        original(source, target)
        target.write_text("Synthetic changed bytes")

    monkeypatch.setattr(workflow.shutil, "copyfile", stale_copy)
    with pytest.raises(ValueError, match="Source changed"):
        apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    assert not (tmp_path / "child").exists()
    assert not (tmp_path / ".child.workflow-lock").exists()
    assert not list(tmp_path.glob(".workflow-*"))
    assert {p.name: p.read_bytes() for p in parent.iterdir()} == before


@pytest.mark.parametrize("value", [1728302400, True, None])
def test_timestamp_requires_aware_text(tmp_path, value):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner", at=value)]
    with pytest.raises(ValueError):
        validate(draft, initial(parent, "agency", "intake"))


def test_duplicate_json_keys_refused_by_cli(tmp_path):
    from typer.testing import CliRunner

    from bob_resolve.broker_workflow.__main__ import app

    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    raw = json.dumps(draft).replace(
        '"agency_id": "agency"', '"agency_id": "wrong", "agency_id": "agency"'
    )
    path = tmp_path / "draft.json"
    path.write_text(raw)
    result = CliRunner().invoke(
        app,
        [
            "apply",
            "--run",
            str(parent),
            "--draft",
            str(path),
            "--out",
            str(tmp_path / "child"),
            "--agency-id",
            "agency",
            "--intake-run-id",
            "intake",
        ],
    )
    assert result.exit_code == 1 and "Duplicate" in result.output
    assert not (tmp_path / "child").exists()


def test_dangling_target_symlink_refused(tmp_path):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    target = tmp_path / "child"
    target.symlink_to(tmp_path / "absent")
    with pytest.raises(ValueError, match="exists"):
        apply(parent, draft, target, agency_id="agency", intake_run_id="intake")
    assert target.is_symlink()


@pytest.mark.parametrize("alias", [False, True])
def test_workflow_refuses_public_output(tmp_path, alias):
    from bob_resolve.run import RunRefused

    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    public = tmp_path / "dashboard/public"
    public.mkdir(parents=True)
    destination = public
    if alias:
        destination = tmp_path / "alias"
        destination.symlink_to(public, target_is_directory=True)
    with pytest.raises(RunRefused, match="public"):
        apply(parent, draft, destination / "child", agency_id="agency", intake_run_id="intake")
    assert not (public / "child").exists()
    assert list(public.iterdir()) == []


@pytest.mark.parametrize("field", ["request_id", "response_id", "provenance", "decision"])
def test_explicit_null_action_fields_refused(tmp_path, field):
    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner", **{field: None})]
    with pytest.raises(ValueError, match="null action field"):
        validate(draft, initial(parent, "agency", "intake"))


def test_child_appearing_at_publication_is_never_replaced(tmp_path, monkeypatch):
    import bob_resolve.broker_workflow as workflow

    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    target = tmp_path / "child"
    original = workflow.publish

    def collision(staged, child):
        child.mkdir()
        original(staged, child)

    monkeypatch.setattr(workflow, "publish", collision)
    with pytest.raises(ValueError, match="appeared"):
        apply(parent, draft, target, agency_id="agency", intake_run_id="intake")
    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert not (tmp_path / ".child.workflow-lock").exists()
    assert not list(tmp_path.glob(".workflow-*"))


def test_unsupported_publication_platform_fails_closed(tmp_path, monkeypatch):
    import bob_resolve.broker_workflow as workflow
    from bob_resolve.run import RunRefused

    parent = run(tmp_path)
    draft = initial(parent, "agency", "intake")
    draft["events"] = [event("assign", text="Synthetic owner")]
    monkeypatch.setattr(workflow.sys, "platform", "unsupported")
    with pytest.raises(RunRefused, match="requires macOS or Linux"):
        apply(parent, draft, tmp_path / "child", agency_id="agency", intake_run_id="intake")
    assert not (tmp_path / "child").exists()
    assert not (tmp_path / ".child.workflow-lock").exists()
    assert not list(tmp_path.glob(".workflow-*"))


def test_export_refuses_public_context(tmp_path):
    from typer.testing import CliRunner

    from bob_resolve.broker_workflow.__main__ import app

    parent = run(tmp_path)
    public = tmp_path / "public"
    public.mkdir()
    result = CliRunner().invoke(
        app,
        [
            "export",
            "--run",
            str(parent),
            "--out",
            str(public / "context.json"),
            "--agency-id",
            "agency",
            "--intake-run-id",
            "intake",
        ],
    )
    assert result.exit_code == 1 and "public" in result.output
    assert list(public.iterdir()) == []


def export_args(parent, target):
    return [
        "export",
        "--run",
        str(parent),
        "--out",
        str(target),
        "--agency-id",
        "agency",
        "--intake-run-id",
        "intake",
    ]


def test_export_partial_write_cleans_up_and_can_retry(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    import bob_resolve.broker_workflow.__main__ as cli

    parent = run(tmp_path)
    target = tmp_path / "context.json"
    original = cli.tempfile.NamedTemporaryFile

    class PartialWriter:
        def __init__(self, *args, **kwargs):
            self.file = original(*args, **kwargs)

        def __enter__(self):
            self.file.__enter__()
            return self

        def write(self, content):
            self.file.write(content[:10])
            self.file.flush()
            raise OSError("Synthetic partial write")

        def __exit__(self, *args):
            return self.file.__exit__(*args)

    with monkeypatch.context() as patch:
        patch.setattr(cli.tempfile, "NamedTemporaryFile", PartialWriter)
        result = CliRunner().invoke(cli.app, export_args(parent, target))
    assert result.exit_code == 1 and "partial write" in result.output
    assert not target.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["parent"]
    result = CliRunner().invoke(cli.app, export_args(parent, target))
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text()) == initial(parent, "agency", "intake")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["context.json", "parent"]


def test_export_fsync_failure_cleans_up_and_can_retry(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    import bob_resolve.broker_workflow.__main__ as cli

    parent = run(tmp_path)
    target = tmp_path / "context.json"

    def fail(_fd):
        raise OSError("Synthetic fsync failure")

    with monkeypatch.context() as patch:
        patch.setattr(cli.os, "fsync", fail)
        result = CliRunner().invoke(cli.app, export_args(parent, target))
    assert result.exit_code == 1 and "fsync failure" in result.output
    assert not target.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["parent"]
    assert CliRunner().invoke(cli.app, export_args(parent, target)).exit_code == 0
    assert json.loads(target.read_text()) == initial(parent, "agency", "intake")


def test_export_concurrent_winner_preserved(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    import bob_resolve.broker_workflow.__main__ as cli

    parent = run(tmp_path)
    target = tmp_path / "context.json"
    original = cli.os.link

    def collision(source, destination):
        target.write_text("Synthetic winning context")
        original(source, destination)

    monkeypatch.setattr(cli.os, "link", collision)
    result = CliRunner().invoke(cli.app, export_args(parent, target))
    assert result.exit_code == 1
    assert target.read_text() == "Synthetic winning context"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["context.json", "parent"]


@pytest.mark.parametrize("symlink", [False, True])
def test_export_existing_output_preserved(tmp_path, symlink):
    from typer.testing import CliRunner

    from bob_resolve.broker_workflow.__main__ import app

    parent = run(tmp_path)
    existing = tmp_path / "existing.json"
    existing.write_text("Synthetic existing context")
    target = existing
    if symlink:
        target = tmp_path / "context.json"
        target.symlink_to(existing)
    before = sorted(p.name for p in tmp_path.iterdir())
    result = CliRunner().invoke(app, export_args(parent, target))
    assert result.exit_code == 1
    assert existing.read_text() == "Synthetic existing context"
    assert not symlink or target.is_symlink()
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize("alias", [False, True])
def test_native_review_refuses_private_workflow_in_public_output(tmp_path, alias):
    from typer.testing import CliRunner

    from bob_resolve.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--enrollment",
            "hard-cases",
            "--out",
            str(tmp_path),
            "--run-id",
            "base",
            "--mask-mbi",
            "--llm-mode",
            "off",
            "--no-parquet",
        ],
    )
    assert result.exit_code == 0, result.output
    draft = initial(tmp_path / "base", "agency", "intake")
    key = next(iter(draft["identities"]))
    draft["events"] = [event("request", item_id=key, text="Synthetic private evidence")]
    parent = tmp_path / "workflow"
    apply(tmp_path / "base", draft, parent, agency_id="agency", intake_run_id="intake")
    before = {p.name: p.read_bytes() for p in parent.iterdir()}
    decisions = tmp_path / "decisions.jsonl"
    decisions.write_text(
        json.dumps(
            dict(
                item_id=key,
                decision="different_people",
                reviewer="Synthetic",
                decided_at="2026-10-07T12:00:00Z",
            )
        )
    )
    public = tmp_path / "dashboard/public"
    public.mkdir(parents=True)
    destination = public
    if alias:
        destination = tmp_path / "alias"
        destination.symlink_to(public, target_is_directory=True)
    result = runner.invoke(
        app,
        [
            "review",
            "apply",
            "--run",
            str(parent),
            "--decisions",
            str(decisions),
            "--out",
            str(destination),
            "--run-id",
            "review-child",
            "--no-parquet",
        ],
    )
    assert result.exit_code == 1 and "public" in result.output and "workflow" in result.output
    assert list(public.iterdir()) == []
    assert {p.name: p.read_bytes() for p in parent.iterdir()} == before
