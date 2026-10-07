"""Actual Intake clean clients into Bob's existing deterministic resolution pipeline."""

from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from bob_resolve.adapters.contract import ContractModel, Identity, Issue, Packet, verify
from bob_resolve.block.candidates import DroppedBlock, candidate_pairs, dropped_blocks
from bob_resolve.golden.resolve import Resolution, resolve
from bob_resolve.load.readers import check_dob
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import normalize_record
from bob_resolve.score.evaluate import score_candidates
from bob_resolve.score.rules import ScoredPair


class IntakeResolution(ContractModel):
    packet: Packet
    resolution: Resolution
    scored_pairs: tuple[ScoredPair, ...]
    dropped_blocks: tuple[DroppedBlock, ...]
    as_of: date
    shared_ids: bool


def resolve_intake(
    packet: Packet, root: Path, *, run_id: str, as_of: date, shared_ids: bool = True
) -> IntakeResolution:
    """No truth, model calls, synthetic enrollment derivation, or implicit wall clock."""
    packet = Packet.model_validate_json(packet.model_dump_json())
    verify(root, packet)
    if packet.identities:
        raise ValueError("expected an Intake packet without prior identity decisions")
    counts = Counter(c.client_id for c in packet.clients)
    policy_counts = Counter(p.policy_id for p in packet.policies)
    records = []
    identities: list[Identity] = []
    recency: dict[str, date] = {}
    dob_review: set[str] = set()
    issues = list(packet.issues) + [Issue(code="ENROLLMENT_NOT_SUPPLIED")]
    for c in sorted(packet.clients, key=lambda c: c.record_id):
        if counts[c.client_id] != 1:
            identities.append(
                Identity(
                    person_id=None,
                    record_ids=(c.record_id,),
                    client_ids=(c.client_id,),
                    state="ambiguous",
                    review_state="needs_review",
                    reasons=("DUPLICATE_CLIENT_ID",),
                )
            )
            continue
        policies = [
            p
            for p in packet.policies
            if p.client_id == c.client_id and policy_counts[p.policy_id] == 1
        ]
        if policies:
            recency[c.record_id] = max(p.effective_date for p in policies)
        dob, dob_issue = check_dob(c.dob, as_of) if c.dob else (None, "missing")
        if dob_issue:
            dob_review.add(c.record_id)
            issues.append(Issue(code=f"DOB_{dob_issue.upper()}", record_ids=(c.record_id,)))
        values = c.model_dump(exclude={"record_id", "warnings", "provenance", "dob"})
        records.append(
            PersonRecord(
                **values,
                record_id=c.record_id,
                source="crm",
                dob=dob,
                dob_issue=dob_issue,
                policy_keys=tuple(sorted(f"policy:{p.policy_id}" for p in policies)),
                lineage=Lineage(
                    source_file=c.provenance.source_file,
                    row_number=c.provenance.row_number,
                    raw_sha256=c.provenance.raw_hash,
                ),
            )
        )
    normalized = [normalize_record(r) for r in records]
    dropped = (
        tuple(
            sorted(
                dropped_blocks(normalized, shared_ids=shared_ids),
                key=lambda block: (-block.size, block.key, block.value_masked),
            )
        )
        if records
        else ()
    )
    scored = (
        score_candidates(normalized, candidate_pairs(normalized, shared_ids=shared_ids), shared_ids)
        if records
        else []
    )
    scored.sort(key=lambda p: (p.a, p.b))
    resolution = resolve(
        records,
        scored,
        recency,
        run_id=run_id,
        clock=lambda: datetime.combine(as_of, datetime.min.time(), UTC),
        shared_ids=shared_ids,
    )
    pending = {r for p in resolution.pending_gray for r in (p.a, p.b)} | dob_review
    pending.update(r for item in resolution.review for r in item.record_ids)
    by_id = {c.record_id: c for c in packet.clients}
    for person in resolution.people:
        needs_review = bool(set(person.record_ids) & pending or person.review_reasons)
        matched = len(person.record_ids) > 1
        identities.append(
            Identity(
                person_id=person.person_id,
                record_ids=person.record_ids,
                client_ids=tuple(sorted({by_id[r].client_id for r in person.record_ids})),
                state="ambiguous" if needs_review else "resolved" if matched else "unresolved",
                review_state="needs_review" if needs_review or not matched else "not_reviewed",
                reasons=tuple(
                    sorted(
                        set(person.review_reasons)
                        | ({"PENDING_IDENTITY_REVIEW"} if needs_review else set())
                        | ({"SINGLE_SOURCE_RECORD"} if not matched else set())
                    )
                ),
            )
        )
    for record_id in resolution.unidentifiable:
        identities.append(
            Identity(
                person_id=None,
                record_ids=(record_id,),
                client_ids=(by_id[record_id].client_id,),
                state="unresolved",
                review_state="needs_review",
                reasons=("UNIDENTIFIABLE",),
            )
        )
    if dropped:
        issues.append(Issue(code="DROPPED_CANDIDATE_BLOCKS"))
    output = Packet(
        **(
            packet.model_dump()
            | {
                "run_id": run_id,
                "identities": tuple(sorted(identities, key=lambda i: i.record_ids)),
                "issues": tuple(issues),
            }
        )
    )
    return IntakeResolution(
        packet=output,
        resolution=resolution,
        scored_pairs=tuple(scored),
        dropped_blocks=dropped,
        as_of=as_of,
        shared_ids=shared_ids,
    )
