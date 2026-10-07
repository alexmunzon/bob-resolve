"""Contract inputs use Bob's real rules, and never invent an enrollment side."""

from datetime import date
from pathlib import Path

import pytest

from bob_resolve.adapters.contract import Client, Issue, Packet, Provenance, canonical_json, pin
from bob_resolve.adapters.intake import resolve_intake


def packet(root: Path, *, conflicting: bool = False) -> Packet:
    (root / "clients.csv").write_text("synthetic source bytes\n")
    artifact = pin(root, "clients.csv")
    rows = []
    for i in range(2):
        rows.append(
            Client(
                record_id=f"record-{i}",
                client_id=f"client-{i}",
                first_name="Taylor",
                last_name="Example",
                dob=date(1950, 1, 1),
                mbi=None,
                phone="2105550100",
                email=None,
                address_line1="2 Test Road" if i == 0 or not conflicting else "9 Else Rd",
                city="Test",
                state="TX",
                zip="78201",
                household_id=None,
                provenance=Provenance(
                    source_file="crm.csv",
                    sheet=None,
                    row_number=i + 2,
                    raw_hash="a" * 64,
                    run_id="intake-1",
                    mapping_version="1",
                    artifact="clients.csv",
                    artifact_row=i + 1,
                ),
            )
        )
    return Packet(
        agency_id="synthetic-a",
        run_id="intake-1",
        intake_run_id="intake-1",
        data_kind="synthetic",
        artifacts=(artifact,),
        clients=tuple(rows),
        policies=(),
    )


def test_real_rules_match_and_repeat(tmp_path: Path) -> None:
    p = packet(tmp_path)
    a = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    b = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert canonical_json(a) == canonical_json(b)
    assert len(a.resolution.people) == 1
    assert a.packet.identities[0].state == "resolved"
    assert a.packet.identities[0].review_state == "not_reviewed"
    assert any(i.code == "ENROLLMENT_NOT_SUPPLIED" for i in a.packet.issues)
    assert "benchmark" not in type(a).model_fields
    assert a.resolution.log
    assert all(line.time == "2026-10-01T00:00:00+00:00" for line in a.resolution.log)
    assert all(line.tier == "rules" for line in a.resolution.log)
    assert a.packet.clients == p.clients
    assert a.packet.policies == p.policies
    assert a.packet.artifacts == p.artifacts
    for field in a.resolution.people[0].fields.values():
        if field.record_id is not None:
            source = next(c for c in p.clients if c.record_id == field.record_id)
            assert field.source_file == source.provenance.source_file
            assert field.row_number == source.provenance.row_number


def test_duplicate_client_ids_stay_visible_without_matching(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={"clients": tuple(c.model_copy(update={"client_id": "same"}) for c in p.clients)}
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert not result.resolution.people
    assert len(result.packet.identities) == 2
    assert all(i.state == "ambiguous" for i in result.packet.identities)


def test_ambiguous_name_only_is_not_resolved(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"phone": None, "address_line1": None}) for c in p.clients
            )
        }
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert all(i.state != "resolved" for i in result.packet.identities)
    assert len(result.resolution.people) == 2


def test_stale_pin_refused_before_matching(tmp_path: Path) -> None:
    p = packet(tmp_path)
    (tmp_path / "clients.csv").write_text("changed")
    with pytest.raises(ValueError, match="stale"):
        resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))


def test_committed_real_intake_fixture() -> None:
    root = Path(__file__).resolve().parents[3] / "fixtures/integration-v1"
    p = Packet.model_validate_json((root / "intake-packet.json").read_text())
    result = resolve_intake(
        p, root / "intake-run", run_id="bob-synthetic-v1", as_of=date(2026, 10, 1)
    )
    assert len(p.clients) == 8
    assert sum(len(i.record_ids) for i in result.packet.identities) == len(p.clients)
    assert len(result.resolution.people) == 8
    assert all(i.state == "unresolved" for i in result.packet.identities)
    assert canonical_json(result) == (root / "bob-result.json").read_text()


@pytest.mark.parametrize(
    ("dob", "code"),
    [
        (date(2099, 1, 1), "DOB_FUTURE"),
        (date(1900, 1, 1), "DOB_PLACEHOLDER"),
        (date(2010, 1, 1), "DOB_IMPLAUSIBLE"),
        (None, "DOB_MISSING"),
    ],
)
def test_invalid_dob_is_visible_even_when_contact_evidence_matches(
    tmp_path: Path, dob: date | None, code: str
) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={"clients": tuple(c.model_copy(update={"dob": dob}) for c in p.clients)}
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert sum(i.code == code for i in result.packet.issues) == 2
    assert all(i.state != "resolved" for i in result.packet.identities)
    assert all(i.review_state == "needs_review" for i in result.packet.identities)
    assert result.packet.clients == p.clients


def test_native_identity_conflict_stays_pending(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"mbi": "1EG4TE5MK73", "dob": date(1950 + 5 * i, 1, 1)})
                for i, c in enumerate(p.clients)
            )
        }
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert len(result.resolution.people) == 2
    assert result.scored_pairs[0].guard_rails == ("GR-002",)
    assert result.resolution.pending_gray == result.scored_pairs
    assert result.resolution.review[0].reason == "IDENTITY_CONFLICT"
    assert all(i.state == "ambiguous" for i in result.packet.identities)
    assert all(i.review_state == "needs_review" for i in result.packet.identities)
    assert not result.resolution.log


def test_native_ambiguous_identity_key_stays_pending(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"mbi": mbi})
                for c, mbi in zip(p.clients, ("1EG4TE5MK73", "1EG4TE5MK74"), strict=True)
            )
        }
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert "GR-004" in result.scored_pairs[0].guard_rails
    assert result.resolution.pending_gray == result.scored_pairs
    assert len(result.resolution.people) == 2
    assert all(i.state == "ambiguous" for i in result.packet.identities)


def test_shared_ids_option_reaches_native_scoring(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"mbi": "1EG4TE5MK73", "phone": None, "address_line1": None})
                for c in p.clients
            )
        }
    )
    enabled = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    withheld = resolve_intake(
        p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1), shared_ids=False
    )
    assert enabled.packet.identities[0].state == "resolved"
    assert len(withheld.resolution.people) == 2
    assert withheld.scored_pairs[0].comparison.mbi is None
    assert "GR-007" in withheld.scored_pairs[0].guard_rails
    assert all(i.state == "ambiguous" for i in withheld.packet.identities)


def test_unidentifiable_records_and_intake_issues_stay_visible(tmp_path: Path) -> None:
    p = packet(tmp_path)
    issue = Issue(code="INTAKE_UNRESOLVED_EVIDENCE", artifact="clients.csv", artifact_row=1)
    p = p.model_copy(
        update={
            "clients": tuple(
                c.model_copy(update={"first_name": None, "last_name": None, "dob": None})
                for c in p.clients
            ),
            "issues": (issue,),
        }
    )
    result = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    assert not result.resolution.people
    assert result.resolution.unidentifiable == tuple(c.record_id for c in p.clients)
    assert len(result.packet.identities) == 2
    assert all(i.reasons == ("UNIDENTIFIABLE",) for i in result.packet.identities)
    assert result.packet.issues[0] == issue


def test_prior_identity_decisions_are_refused(tmp_path: Path) -> None:
    p = packet(tmp_path)
    prior = resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1))
    with pytest.raises(ValueError, match="without prior identity decisions"):
        resolve_intake(prior.packet, tmp_path, run_id="bob-2", as_of=date(2026, 10, 1))


def test_equal_size_dropped_blocks_have_stable_order_on_rerun(tmp_path: Path) -> None:
    p = packet(tmp_path)
    p = p.model_copy(
        update={
            "clients": tuple(
                client.model_copy(
                    update={
                        "record_id": f"record-{group}-{i:02}",
                        "client_id": f"client-{group}-{i:02}",
                        "last_name": "Example" if group == 0 else "Synthetic",
                        "dob": date(1950 + group, 1, 1),
                        "phone": f"210555010{group}",
                        "email": f"group-{group}@example.test",
                    }
                )
                for group, client in enumerate(p.clients)
                for i in range(51)
            )
        }
    )
    outputs = [
        resolve_intake(p, tmp_path, run_id="bob-1", as_of=date(2026, 10, 1)) for _ in range(4)
    ]
    blocks = outputs[0].dropped_blocks
    assert blocks
    assert len({block.value_masked for block in blocks if block.key == "phone"}) == 2
    assert blocks == tuple(
        sorted(blocks, key=lambda block: (-block.size, block.key, block.value_masked))
    )
    assert len({canonical_json(output) for output in outputs}) == 1
