"""A high match score does not make a guard-rail review a threshold close call."""

from datetime import UTC, date, datetime

from bob_resolve.config import SCORE_HIGH
from bob_resolve.golden import resolve
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import normalize_record
from bob_resolve.queue import QueueItem, build_queue
from bob_resolve.score import score_pair


def record(rid: str, dob: date, mbi: str | None = None) -> PersonRecord:
    return PersonRecord(
        record_id=rid,
        source="enrollment",
        first_name="Kevin",
        last_name="Khan",
        dob=dob,
        mbi=mbi,
        lineage=Lineage(source_file="synthetic.csv", row_number=1, raw_sha256="a" * 64),
    )


def queued(a: PersonRecord, b: PersonRecord) -> QueueItem:
    records = [a, b]
    norm = {r.record_id: normalize_record(r) for r in records}
    scored = [score_pair(norm[a.record_id], norm[b.record_id])]
    res = resolve(
        records,
        scored,
        {},
        run_id="review-explanation",
        clock=lambda: datetime(2026, 10, 1, tzinfo=UTC),
    )
    return build_queue(res, scored, {r.record_id: r for r in records}, norm, {}, True)[0]


def test_above_threshold_name_dob_pair_explains_the_guard_rail() -> None:
    item = queued(
        record("enrollment:1", date(1965, 8, 27)), record("enrollment:2", date(1965, 8, 27))
    )
    assert item.pairs[0].score > SCORE_HIGH
    assert item.pairs[0].decision == "GRAY" and item.suggestion == "unsure"
    assert item.rule_ids == ("GR-007",) and not item.already_one_person
    assert item.detail == "Guard rails GR-007 require human review regardless of the score."


def test_identity_conflict_stays_high_and_keeps_its_specific_explanation() -> None:
    item = queued(
        record("enrollment:1", date(1965, 8, 27), "9ZZ0ZZ0ZZ01"),
        record("enrollment:2", date(1940, 1, 1), "9ZZ0ZZ0ZZ01"),
    )
    assert item.reason == "IDENTITY_CONFLICT" and item.severity == "high"
    assert "GR-002" in item.detail and "not merged" in item.detail
