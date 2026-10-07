"""PR 21a: a conflict found inside a chain of auto-matches holds every link between the two
conflicting records for review. No survivor is picked by score or by record id order."""

from datetime import UTC, date, datetime
from itertools import combinations, permutations
from typing import Any

import pytest

from bob_resolve.cluster import split_on_conflict
from bob_resolve.cluster.blocks import biconnected_blocks
from bob_resolve.golden import resolve
from bob_resolve.load.records import Lineage, PersonRecord
from bob_resolve.normalize.record import NormalizedRecord, normalize_record
from bob_resolve.score import ScoredPair, score_pair

SAME = {"last_name": "Wrenfield", "dob": date(1948, 7, 9)}
EQUAL = 0.998498817743263


def _rec(rid: str, first: str | None, **kw: Any) -> PersonRecord:
    base: dict[str, Any] = {"first_name": first, "mbi": None, **SAME, **kw}
    lin = Lineage(source_file="synthetic/crm.csv", row_number=1, raw_sha256="0" * 64)
    return PersonRecord(record_id=rid, source="crm", lineage=lin, **base)


def _norm(rid: str, first: str | None) -> NormalizedRecord:
    return normalize_record(_rec(rid, first))


def _edge(x: NormalizedRecord, y: NormalizedRecord, score: float = EQUAL) -> ScoredPair:
    a, b = sorted((x, y), key=lambda r: r.record_id)
    return score_pair(a, b).model_copy(update={"score": score, "decision": "AUTO_MATCH"})


def _bridge(
    ids: tuple[str, str, str] = ("crm:A", "crm:B", "crm:C"),
    s_ab: float = EQUAL,
    s_bc: float = EQUAL,
) -> tuple[list[NormalizedRecord], list[ScoredPair]]:
    a, b, c = _norm(ids[0], "Patrick"), _norm(ids[1], "Pat"), _norm(ids[2], "Patricia")
    return [a, b, c], [_edge(a, b, s_ab), _edge(b, c, s_bc)]


def _edges(pairs: Any) -> set[frozenset[str]]:
    return {frozenset(p) for p in pairs}


def _check_accounting(recs: list[NormalizedRecord], clusters: list[tuple[str, ...]]) -> None:
    flat = [r for c in clusters for r in c]
    assert sorted(flat) == sorted(r.record_id for r in recs)


def test_equal_score_bridge_keeps_no_survivor() -> None:
    recs, matches = _bridge()
    clusters, kept, splits = split_on_conflict(recs, matches)
    assert clusters == [("crm:A",), ("crm:B",), ("crm:C",)]
    assert kept == set()
    assert len(splits) == 1
    assert _edges(splits[0].cut) == {frozenset({"crm:A", "crm:B"}), frozenset({"crm:B", "crm:C"})}
    assert list(splits[0].cut) == sorted(splits[0].cut)
    _check_accounting(recs, clusters)


@pytest.mark.parametrize("s_ab,s_bc", [(0.9999, 0.9991), (0.9991, 0.9999)])
def test_unequal_scores_still_pick_no_survivor(s_ab: float, s_bc: float) -> None:
    recs, matches = _bridge(s_ab=s_ab, s_bc=s_bc)
    clusters, kept, _ = split_on_conflict(recs, matches)
    assert kept == set() and all(len(c) == 1 for c in clusters)


RENAMES = [
    ("crm:A", "crm:B", "crm:C"),
    ("crm:z9", "crm:a1", "crm:m5"),
    ("crm:m5", "crm:z9", "crm:a1"),
    ("crm:a1", "crm:m5", "crm:z9"),
]


@pytest.mark.parametrize("ids", RENAMES)
def test_result_ignores_row_order_and_id_names(ids: tuple[str, str, str]) -> None:
    role = {ids[0]: "patrick", ids[1]: "pat", ids[2]: "patricia"}
    seen = set()
    recs, matches = _bridge(ids)
    for rp in permutations(recs):
        for mp in permutations(matches):
            clusters, kept, splits = split_on_conflict(list(rp), list(mp))
            part = frozenset(frozenset(role[r] for r in c) for c in clusters)
            cut = frozenset(frozenset(role[r] for r in e) for s in splits for e in s.cut)
            seen.add((part, cut, frozenset(kept)))
    assert len(seen) == 1
    part, cut, kept = seen.pop()
    assert part == {frozenset({"patrick"}), frozenset({"pat"}), frozenset({"patricia"})}
    assert cut == {frozenset({"patrick", "pat"}), frozenset({"pat", "patricia"})} and not kept


def test_longer_chain_holds_every_link() -> None:
    a, b, b2, c = (_norm("crm:A", "Patrick"), _norm("crm:B", "Pat"),
                   _norm("crm:B2", "Pat"), _norm("crm:C", "Patricia"))  # fmt: skip
    clusters, kept, _ = split_on_conflict([a, b, b2, c], [_edge(a, b), _edge(b, b2), _edge(b2, c)])
    assert kept == set() and len(clusters) == 4


def test_cycle_with_alternative_paths_holds_every_link() -> None:
    a, b, b2, c = (_norm("crm:A", "Patrick"), _norm("crm:B", "Pat"),
                   _norm("crm:B2", "Pat"), _norm("crm:C", "Patricia"))  # fmt: skip
    edges = [_edge(a, b), _edge(a, b2), _edge(b, c, 0.9999), _edge(b2, c, 0.9999), _edge(b, b2)]
    clusters, kept, splits = split_on_conflict([a, b, b2, c], edges)
    assert kept == set() and len(clusters) == 4
    assert len(splits[0].cut) == 5


def test_second_patricia_on_the_chain_is_also_held() -> None:
    """Patricia2 conflicts with Patrick too, so her link to Patricia is on a disputed path."""
    recs, matches = _bridge()
    d = _norm("crm:D", "Patricia")
    clusters, kept, _ = split_on_conflict([*recs, d], [*matches, _edge(recs[2], d)])
    assert kept == set() and len(clusters) == 4


def test_off_path_record_keeps_its_own_link() -> None:
    """A record with no first name conflicts with no one and hangs off Patricia alone."""
    recs, matches = _bridge()
    d = _norm("crm:D", None)
    clusters, kept, splits = split_on_conflict([*recs, d], [*matches, _edge(recs[2], d)])
    assert kept == {("crm:C", "crm:D")}
    assert sorted(clusters) == [("crm:A",), ("crm:B",), ("crm:C", "crm:D")]
    assert _edges(splits[0].cut) == {frozenset({"crm:A", "crm:B"}), frozenset({"crm:B", "crm:C"})}
    _check_accounting([*recs, d], clusters)


def test_positive_controls_still_merge() -> None:
    rob = normalize_record(_rec("crm:R1", "Robert", last_name="Oakhurst", dob=date(1951, 1, 2)))
    bob = normalize_record(_rec("crm:R2", "Bob", last_name="Oakhurst", dob=date(1951, 1, 2)))
    p1, p2, p3 = _norm("crm:P1", "Pat"), _norm("crm:P2", "Pat"), _norm("crm:P3", "Pat")
    recs = [rob, bob, p1, p2, p3]
    matches = [_edge(rob, bob), _edge(p1, p2), _edge(p2, p3)]
    clusters, kept, splits = split_on_conflict(recs, matches)
    assert sorted(clusters) == [("crm:P1", "crm:P2", "crm:P3"), ("crm:R1", "crm:R2")]
    assert len(kept) == 3 and splits == []


def test_blocks_of_a_bowtie_and_a_bridge() -> None:
    edges = [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("d", "f")]
    blocks = {frozenset(b) for b in biconnected_blocks(edges)}
    assert blocks == {
        frozenset({("a", "b"), ("b", "c"), ("a", "c")}),
        frozenset({("c", "d")}),
        frozenset({("d", "e"), ("e", "f"), ("d", "f")}),
    }


def _clock() -> datetime:
    return datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _e2e_records() -> list[PersonRecord]:
    return [
        _rec("crm:A", "Patrick", email="pw@example.com"),
        _rec("crm:B", "Pat", email="pw@example.com", phone="5555550142"),
        _rec("crm:C", "Patricia", phone="5555550142"),
    ]


def _e2e(review_pairs: frozenset[tuple[str, str]] = frozenset()) -> Any:
    recs = _e2e_records()
    norm = [normalize_record(r) for r in recs]
    scored = [score_pair(a, b) for a, b in combinations(norm, 2)]
    assert sum(p.decision == "AUTO_MATCH" for p in scored) == 2
    return resolve(recs, scored, {}, run_id="q", clock=_clock, review_pairs=review_pairs)


def test_resolve_sends_every_disputed_link_to_review_and_logs_no_merge() -> None:
    res = _e2e()
    assert sorted(p.record_ids for p in res.people) == [("crm:A",), ("crm:B",), ("crm:C",)]
    item = next(i for i in res.review if i.reason == "CLUSTER_CONFLICT")
    assert item.record_ids == ("crm:A", "crm:B", "crm:C")
    assert set(item.pairs) == {("crm:A", "crm:B"), ("crm:A", "crm:C"), ("crm:B", "crm:C")}
    assert "weakest" not in item.detail and chr(0x2014) not in item.detail
    assert not any(e.action == "merge" for e in res.log)
    splits = [(e.a, e.b) for e in res.log if e.action == "split"]
    assert sorted(splits) == [("crm:A", "crm:B"), ("crm:B", "crm:C")]
    assert all(e.rule_ids == ("CLUSTER_CONFLICT",) for e in res.log)


def test_a_human_confirmed_link_on_a_disputed_path_is_held_not_merged() -> None:
    res = _e2e(frozenset({("crm:A", "crm:B")}))
    assert not any(e.action == "merge" for e in res.log)
    human = next(e for e in res.log if (e.a, e.b) == ("crm:A", "crm:B"))
    assert human.action == "split" and human.tier == "review"
    assert human.rule_ids == ("CLUSTER_CONFLICT",)
    assert all(len(p.record_ids) == 1 for p in res.people)
