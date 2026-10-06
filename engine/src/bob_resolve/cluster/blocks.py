"""Biconnected blocks (Tarjan), used to find every link that lies on some path between two
conflicting records. A link is on a simple path from u to v exactly when its block lies on the
path from u to v in the block-cut tree. The blocks depend only on the graph, not on edge order."""

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence

Pair = tuple[str, str]


def biconnected_blocks(edges: Iterable[Pair]) -> list[list[Pair]]:
    """Each block is a list of the given edges. Iterative, so deep chains cannot overflow."""
    es = sorted({e for e in edges if e[0] != e[1]})
    adj: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for i, (a, b) in enumerate(es):
        adj[a].append((b, i))
        adj[b].append((a, i))
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    blocks: list[list[Pair]] = []
    for root in sorted(adj):
        if root in disc:
            continue
        disc[root] = low[root] = len(disc)
        stack = [(root, -1, iter(adj[root]))]
        held: list[int] = []
        while stack:
            v, via, it = stack[-1]
            for w, i in it:
                if i == via:
                    continue
                if w not in disc:
                    disc[w] = low[w] = len(disc)
                    held.append(i)
                    stack.append((w, i, iter(adj[w])))
                    break
                if disc[w] < disc[v]:
                    low[v] = min(low[v], disc[w])
                    held.append(i)
            else:
                stack.pop()
                if stack:
                    u = stack[-1][0]
                    low[u] = min(low[u], low[v])
                    if low[v] >= disc[u]:
                        block = []
                        while (i := held.pop()) != via:
                            block.append(es[i])
                        blocks.append([*block, es[via]])
    return blocks


def edges_between(u: str, v: str, blocks: Sequence[Sequence[Pair]]) -> set[Pair]:
    """Every edge on any simple path from u to v: the blocks on their block-cut tree path."""
    member: dict[str, list[int]] = defaultdict(list)
    for i, block in enumerate(blocks):
        for x in {x for e in block for x in e}:
            member[x].append(i)

    def node(x: str) -> tuple[str, str | int]:
        # Callers pass ends of a conflicting pair inside one component, so each has an edge.
        if not member[x]:
            raise ValueError(f"{x} is in no block: it has no edge")
        return ("v", x) if len(member[x]) > 1 else ("b", member[x][0])

    Node = tuple[str, str | int]
    start, goal = node(u), node(v)
    prev = {start: start}
    queue = deque([start])
    while queue and goal not in prev:
        kind, key = n = queue.popleft()
        nxt: list[Node]
        if kind == "v":
            nxt = [("b", i) for i in member[str(key)]]
        else:
            nxt = [node(x) for x in {x for e in blocks[int(key)] for x in e} if len(member[x]) > 1]
        for m in nxt:
            if m not in prev:
                prev[m] = n
                queue.append(m)
    out: set[Pair] = set()
    n = goal
    while True:
        if n[0] == "b":
            out.update(blocks[int(n[1])])
        if n == start:
            return out
        n = prev[n]
