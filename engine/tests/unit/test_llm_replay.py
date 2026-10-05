import json

import pytest

from bob_resolve.llm.replay import request_key, review_pair

FIELDS = {"first_name": ("Alex", "Alec"), "dob": ("1960-01-01", "1960-01-01")}


def test_off_default_and_missing_replay(tmp_path):
    assert review_pair(FIELDS, cassette_dir=tmp_path).status == "off"
    result = review_pair(FIELDS, mode="replay", cassette_dir=tmp_path)
    assert result.status == "pending"
    assert result.model == "sonnet"
    assert result.requires_human_review
    assert result.cost_usd == 0


def test_replay_advisory_preserves_rails_and_zero_spend(tmp_path):
    key = request_key(FIELDS, guardrail_ids=("GR-007",), high_stakes=True)
    (tmp_path / f"{key}.json").write_text(
        json.dumps(
            {
                "request_key": key,
                "model": "opus",
                "rationale": "The names need human review.",
                "provenance": "synthetic-test",
                "cost_usd": 0.002,
            }
        )
    )
    result = review_pair(
        FIELDS, mode="replay", cassette_dir=tmp_path, guardrail_ids=("GR-007",), high_stakes=True
    )
    assert result.status == "replayed"
    assert result.guardrail_ids == ("GR-007",)
    assert result.requires_human_review
    assert result.rationale == "The names need human review."
    assert result.cost_usd == 0
    assert result.recorded_cost_usd == 0.002


def test_only_uncertain_gray_pairs_are_eligible(tmp_path):
    assert (
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path, jev_uncertain=False).status
        == "ineligible"
    )
    assert (
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path, gray_zone=False).status
        == "ineligible"
    )


def test_key_minimizes_fields_and_is_order_independent():
    with pytest.raises(ValueError, match="compared fields"):
        request_key({**FIELDS, "notes": ("secret", "secret")})
    assert request_key(FIELDS) == request_key(dict(reversed(list(FIELDS.items()))))
    assert request_key(FIELDS) != request_key(FIELDS, high_stakes=True)
    assert request_key(FIELDS) != request_key(FIELDS, guardrail_ids=("GR-007",))


@pytest.mark.parametrize("mode", ["live", "record", "other"])
def test_paid_modes_unavailable(tmp_path, mode):
    with pytest.raises(ValueError, match="off or replay"):
        review_pair(FIELDS, mode=mode, cassette_dir=tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"model": "sonnet"},
        {"request_key": "wrong"},
        {"rationale": ""},
        {"cost_usd": -1},
        {"provenance": ""},
        {"decision": "merge"},
    ],
)
def test_invalid_cassettes_fail_closed(tmp_path, change):
    key = request_key(FIELDS, high_stakes=True)
    payload = {
        "request_key": key,
        "model": "opus",
        "rationale": "Review needed.",
        "provenance": "test",
        "cost_usd": 0.001,
    }
    payload.update(change)
    (tmp_path / f"{key}.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path, high_stakes=True)


@pytest.mark.parametrize("budget", [-1, float("inf"), float("nan")])
def test_invalid_budget_rejected(tmp_path, budget):
    with pytest.raises(ValueError, match="Budget"):
        review_pair(FIELDS, cassette_dir=tmp_path, budget_usd=budget)


def test_guardrail_order_and_duplicate_ids_are_canonical():
    assert request_key(FIELDS, guardrail_ids=("GR-007", "GR-001", "GR-007")) == request_key(
        FIELDS, guardrail_ids=("GR-001", "GR-007")
    )
    with pytest.raises(ValueError, match="guardrail"):
        request_key(FIELDS, guardrail_ids=("GR-999",))


def test_corrupt_json_is_rejected(tmp_path):
    key = request_key(FIELDS)
    (tmp_path / f"{key}.json").write_text("{broken")
    with pytest.raises(ValueError, match="Unreadable"):
        review_pair(FIELDS, mode="replay", cassette_dir=tmp_path)


def test_ids_off_request_cannot_depend_on_shared_identifiers():
    with_ids = {**FIELDS, "mbi": ("synthetic-a", "synthetic-a")}
    other_ids = {**FIELDS, "mbi": ("synthetic-b", "synthetic-c")}
    assert request_key(with_ids, shared_ids=False) == request_key(other_ids, shared_ids=False)
    assert request_key(with_ids, shared_ids=False) == request_key(FIELDS, shared_ids=False)
    assert request_key(with_ids) != request_key(other_ids)
