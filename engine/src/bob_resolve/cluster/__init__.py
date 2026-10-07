"""Clusters (SPEC 6 step 6): connected components over auto-matches, split on any conflict.

Nickname links are not transitive: Patrick and Pat match, Pat and Patricia match, Patrick and
Patricia do not. So after the components are built every record pair inside one is re-checked,
and for a conflicting pair every auto-match link on any path between them is held for review.
No link is kept by score or by record id order (PR 21a).
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache

import polars as pl

from bob_resolve.cluster.blocks import biconnected_blocks, edges_between
from bob_resolve.config import CLUSTER_CONFLICT_LEVELS
from bob_resolve.normalize.names import NICKNAMES_CSV, normalize_name
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.compare import compare
from bob_resolve.score.rules import ScoredPair, guard_rails

Pair = tuple[str, str]


def components(nodes: Iterable[str], edges: Iterable[Pair]) -> list[tuple[str, ...]]:
    """Connected components, each sorted, listed by smallest id."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    groups: dict[str, list[str]] = defaultdict(list)
    for n in parent:
        groups[find(n)].append(n)
    return sorted(tuple(sorted(g)) for g in groups.values())


@cache
def _formal_names() -> frozenset[str]:
    names = pl.read_csv(NICKNAMES_CSV, infer_schema=False)["canonical"]
    return frozenset(n for n in (normalize_name(x) for x in names) if n)


def conflict_reasons(
    a: NormalizedRecord, b: NormalizedRecord, shared_ids: bool = True
) -> tuple[str, ...]:
    """Field names that conflict. Two different formal names (Patrick, Patricia) conflict even
    when Jaro-Winkler calls them close: a typo is not another known name. Review 2: so do any
    close first names that are not a typo by GR-005's test (Mario and Maria, Jon and Jan)."""
    c = compare(a, b, shared_ids=shared_ids)
    out = [f for f, levels in CLUSTER_CONFLICT_LEVELS.items() if getattr(c, f) in levels]
    formal = _formal_names()
    both_formal = a.first_name in formal and b.first_name in formal
    if c.first == "close" and (both_formal or not c.first_typo):
        out.insert(0, "first")
    if "GR-006" in guard_rails(c):
        out.append("dob")
    return tuple(out)


@dataclass(frozen=True)
class ClusterSplit:
    """One component that held a conflicting pair: its records, those pairs, the edges held.
    `cut` keeps its old name, but since PR 21a it means held for review, not cut at one link."""

    records: tuple[str, ...]
    conflicts: tuple[Pair, ...]
    cut: tuple[Pair, ...]


def split_on_conflict(
    records: Sequence[NormalizedRecord], matches: Sequence[ScoredPair], *, shared_ids: bool = True
) -> tuple[list[tuple[str, ...]], set[Pair], list[ClusterSplit]]:
    """Return final clusters, the kept match edges, and one ClusterSplit per conflicted
    component. `cut` holds every edge on any simple path between a conflicting pair, sorted."""
    by_id = {r.record_id: r for r in records}
    kept = {(p.a, p.b) for p in matches}
    splits = []
    while True:
        found = False
        for comp in components(by_id, kept):
            bad = [
                (a, b)
                for a, b in _pairs(comp)
                if conflict_reasons(by_id[a], by_id[b], shared_ids=shared_ids)
            ]
            if not bad:
                continue
            inside = set(comp)
            blocks = biconnected_blocks(e for e in kept if e[0] in inside)
            held = set().union(*(edges_between(u, v, blocks) for u, v in bad))
            kept -= held
            splits.append(ClusterSplit(comp, tuple(bad), tuple(sorted(held))))
            found = True
        if not found:
            return components(by_id, kept), kept, splits


def _pairs(comp: tuple[str, ...]) -> list[Pair]:
    return [(a, b) for i, a in enumerate(comp) for b in comp[i + 1 :]]


__all__ = ["ClusterSplit", "components", "conflict_reasons", "split_on_conflict"]
