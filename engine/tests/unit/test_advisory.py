"""Hand-written synthetic fixtures, never recorded model responses."""

import json
import socket

import pytest
from pydantic import ValidationError

from bob_resolve.advisory import Request, evaluate


def request(**changes):
    return Request.model_validate(
        dict(
            run_hash="a" * 64,
            queue_hash="b" * 64,
            pair_hash="c" * 64,
            comparisons={"dob": "agree", "name": "similar"},
            guardrails=("GR-008",),
        )
        | changes
    )


def response(req, **changes):
    return json.dumps(
        dict(
            version="bob-second-opinion-v1",
            request_key=req.key,
            origin="hand_written_synthetic_fixture",
            opinion="unsure",
            evidence=["dob"],
        )
        | changes
    ).encode()


def test_offline_and_immutable(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("network attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    req = request()
    before = req.model_dump_json()
    result = evaluate(req, mode="replay", response=response(req))
    assert result.status == "replayed" and result.review_state == "needs_review"
    assert result.calls == result.cost_usd == 0
    assert result.label == "Hand-written synthetic fixture; no model called."
    assert req.model_dump_json() == before
    assert evaluate(req).status == "off"
    assert evaluate(req, mode="live").status == "live_blocked"
    assert evaluate(req, mode="replay").status == "pending"


@pytest.mark.parametrize(
    "changes",
    [
        {"request_key": "f" * 64},
        {"opinion": "merge"},
        {"notes": "ignore rules"},
        {"evidence": []},
        {"evidence": ["mbi"]},
        {"opinion": "same_person"},
        {"origin": "actual_model_response"},
        {"confidence": 1},
    ],
)
def test_adversarial_response(changes):
    req = request()
    result = evaluate(req, mode="replay", response=response(req, **changes))
    assert result.status == "pending" and result.suggestion is None


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"null",
        b"[]",
        b"\xff",
        b"{",
        b"x" * 8193,
        b'{"version":"x","version":"bob-second-opinion-v1"}',
        b"[" * 1500,
    ],
)
def test_malformed(raw):
    assert evaluate(request(), mode="replay", response=raw).status == "pending"


def test_minimization_binding_and_guardrails():
    req = request()
    for changes in (
        {"notes": "private"},
        {"comparisons": {"ssn": "agree"}},
        {"comparisons": {"name": "someone"}},
        {"guardrails": ["GR-999"]},
        {"data_kind": "real"},
        {"comparisons": {}},
    ):
        with pytest.raises(ValidationError):
            request(**changes)
    assert request(queue_hash="d" * 64).key != req.key
    assert request(run_hash="d" * 64).key != req.key
    assert request(pair_hash="d" * 64).key != req.key
    for rail in [f"GR-{i:03}" for i in range(1, 9)] + ["IDENTITY_CONFLICT"]:
        r = request(guardrails=(rail,))
        assert (
            evaluate(r, mode="replay", response=response(r, opinion="same_person")).status
            == "pending"
        )
    r = request(guardrails=(), comparisons={"mbi": "conflict"})
    assert (
        evaluate(
            r, mode="replay", response=response(r, opinion="same_person", evidence=["mbi"])
        ).status
        == "pending"
    )
    with pytest.raises(ValueError):
        evaluate(req, mode="record")


def test_adapter_has_no_io_or_live_imports():
    import ast
    import inspect

    from bob_resolve import advisory

    tree = ast.parse(inspect.getsource(advisory))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert all(
        name
        and name.split(".")[0]
        in {"hashlib", "json", "re", "decimal", "typing", "pydantic", "bob_resolve"}
        for name in imports
    )
    assert not any(
        isinstance(node, ast.Name) and node.id in {"open", "exec", "eval"}
        for node in ast.walk(tree)
    )


def test_off_and_live_ignore_malformed_bytes():
    req = request()
    assert evaluate(req, response=b"invalid").status == "off"
    assert evaluate(req, mode="live", response=b"invalid").status == "live_blocked"
    assert evaluate(req, mode="replay", response="not bytes").status == "pending"


def test_contradictory_different_people_and_deterministic_binding():
    req = request(guardrails=(), comparisons={"mbi": "agree"})
    raw = response(req, opinion="different_people", evidence=["mbi"])
    assert evaluate(req, mode="replay", response=raw).status == "pending"
    with pytest.raises(ValidationError):
        request(deterministic_decision="MATCH")
    same = response(req, opinion="same_person", evidence=["mbi"])
    assert evaluate(req, mode="replay", response=same).review_state == "needs_review"


@pytest.mark.parametrize(
    "comparisons,evidence",
    [
        ({"name": "similar"}, ["name"]),
        ({"mbi": "agree", "name": "similar"}, ["mbi", "name"]),
        ({"mbi": "agree", "name": "similar"}, ["name"]),
        ({"mbi": "conflict", "name": "similar"}, ["name"]),
    ],
)
def test_different_people_requires_cited_conflict(comparisons, evidence):
    req = request(guardrails=(), comparisons=comparisons)
    result = evaluate(
        req, mode="replay", response=response(req, opinion="different_people", evidence=evidence)
    )
    assert result.status == "pending"
    assert result.suggestion is None
    assert result.review_state == "needs_review"
    unsure = evaluate(req, mode="replay", response=response(req, evidence=evidence))
    assert unsure.status == "replayed"
    assert unsure.suggestion is not None and unsure.suggestion.opinion == "unsure"
    assert unsure.review_state == "needs_review"


def test_different_people_with_cited_conflict_still_needs_review():
    req = request(guardrails=(), comparisons={"mbi": "conflict", "name": "similar"})
    result = evaluate(
        req,
        mode="replay",
        response=response(req, opinion="different_people", evidence=["mbi", "name"]),
    )
    assert result.status == "replayed"
    assert result.suggestion is not None and result.suggestion.opinion == "different_people"
    assert result.review_state == "needs_review"
    assert result.calls == result.cost_usd == 0


@pytest.mark.parametrize(
    "comparisons",
    [{"name": "similar"}, {"mbi": "agree", "name": "similar"}],
)
def test_same_person_requires_cited_agreement(comparisons):
    req = request(guardrails=(), comparisons=comparisons)
    result = evaluate(
        req, mode="replay", response=response(req, opinion="same_person", evidence=["name"])
    )
    assert result.status == "pending"
    assert result.suggestion is None
    assert result.review_state == "needs_review"


def test_same_person_with_cited_agreement_still_needs_review():
    req = request(guardrails=(), comparisons={"mbi": "agree", "name": "similar"})
    result = evaluate(
        req,
        mode="replay",
        response=response(req, opinion="same_person", evidence=["mbi", "name"]),
    )
    assert result.status == "replayed"
    assert result.suggestion is not None and result.suggestion.opinion == "same_person"
    assert result.review_state == "needs_review"
    assert result.calls == result.cost_usd == 0
