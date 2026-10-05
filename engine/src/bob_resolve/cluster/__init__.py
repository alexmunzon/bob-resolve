"""Clusters (SPEC 6 step 6): connected components over auto-matches, split on any conflict.

Nickname links are not transitive: Patrick and Pat match, Pat and Patricia match, Patrick and
Patricia do not. So after the components are built every record pair inside one is re-checked,
and a conflicting pair is cut apart at the weakest auto-match link on the path between them.
"""

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache

import polars as pl

from bob_resolve.config import CLUSTER_CONFLICT_LEVELS
from bob_resolve.normalize.names import NICKNAMES_CSV, normalize_name
from bob_resolve.normalize.record import NormalizedRecord
from bob_resolve.score.compare import compare
from bob_resolve.score.rules import ScoredPair

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


def conflict_reasons(a: NormalizedRecord, b: NormalizedRecord) -> tuple[str, ...]:
    """Field names that conflict. Two different formal names (Patrick, Patricia) conflict even
    when Jaro-Winkler calls them close: a typo is not another known name. Review 2: so do any
    close first names that are not a typo by GR-005's test (Mario and Maria, Jon and Jan)."""
    c = compare(a, b, shared_ids=False)
    out = [f for f, levels in CLUSTER_CONFLICT_LEVELS.items() if getattr(c, f) in levels]
    formal = _formal_names()
    both_formal = a.first_name in formal and b.first_name in formal
    if c.first == "close" and (both_formal or not c.first_typo):
        out.insert(0, "first")
    return tuple(out)


def _path(u: str, v: str, edges: set[Pair]) -> list[Pair]:
    """Edges on a shortest path from u to v (BFS), or [] when they are not connected."""
    adj: dict[str, list[str]] = defaultdict(list)
    for a, b in sorted(edges):
        adj[a].append(b)
        adj[b].append(a)
    prev: dict[str, str] = {u: u}
    queue = deque([u])
    while queue and v not in prev:
        x = queue.popleft()
        for y in adj[x]:
            if y not in prev:
                prev[y] = x
                queue.append(y)
    out: list[Pair] = []
    while v in prev and v != u:
        out.append((min(v, prev[v]), max(v, prev[v])))
        v = prev[v]
    return out


@dataclass(frozen=True)
class ClusterSplit:
    """One component that held a conflicting pair: its records, those pairs, the edges cut."""

    records: tuple[str, ...]
    conflicts: tuple[Pair, ...]
    cut: tuple[Pair, ...]


def split_on_conflict(
    records: Sequence[NormalizedRecord], matches: Sequence[ScoredPair]
) -> tuple[list[tuple[str, ...]], set[Pair], list[ClusterSplit]]:
    """Return final clusters, the kept match edges, and one ClusterSplit per conflicted
    component. Every cut edge is the weakest (lowest score, then ids) on a conflicting path."""
    by_id = {r.record_id: r for r in records}
    score = {(p.a, p.b): p.score for p in matches}
    kept = set(score)
    splits = []
    for comp in components(by_id, kept):
        bad = [(a, b) for a, b in _pairs(comp) if conflict_reasons(by_id[a], by_id[b])]
        if not bad:
            continue
        cut: list[Pair] = []
        for u, v in bad:
            while path := _path(u, v, kept):
                weakest = min(path, key=lambda e: (score[e], e))
                kept.discard(weakest)
                cut.append(weakest)
        splits.append(ClusterSplit(comp, tuple(bad), tuple(cut)))
    return components(by_id, kept), kept, splits


def _pairs(comp: tuple[str, ...]) -> list[Pair]:
    return [(a, b) for i, a in enumerate(comp) for b in comp[i + 1 :]]


__all__ = ["ClusterSplit", "components", "conflict_reasons", "split_on_conflict"]
