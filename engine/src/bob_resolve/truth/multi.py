"""Answer key for the held-out multi-a-b world, built by code from commons' truth files.

People come from commons' cluster_truth.json (every client id of both agencies, A's copies and
B's stale copies included). Each enrollment row joins the person whose client owns its policy
number in that agency's policies file, as in the snapshot key; a row that does not resolve is
reported. pair_truth.jsonl (320 client pairs) and must_not_merge.jsonl (164) are kept as given.
"""

import json
from datetime import date
from pathlib import Path

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.load import read_enrollment
from bob_resolve.load.commons import ensure_multi_a_b
from bob_resolve.truth.answer_key import AnswerKey, UnresolvedReason, UnresolvedRow

Pair = tuple[str, str]


class MustNotMerge(BaseModel):
    model_config = ConfigDict(frozen=True)

    a: str
    b: str
    defect_type: str
    reason: str


class MultiTruth(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: AnswerKey
    commons_clusters: int
    commons_pairs: dict[Pair, tuple[str, ...]]  # (smaller id, larger id) to its defect types
    pair_scope: dict[Pair, str]
    must_not_merge: tuple[MustNotMerge, ...]


def _pair(a: str, b: str) -> Pair:
    x, y = sorted((f"crm:{a}", f"crm:{b}"))
    return x, y


def _attach(
    people: dict[str, list[str]],
    client_person: dict[str, str],
    enrollment_csv: Path,
    policies_csv: Path,
    prefix: str,
    as_of: date,
) -> list[UnresolvedRow]:
    enr = read_enrollment(enrollment_csv, as_of)
    owners = pl.read_csv(policies_csv, infer_schema=False).group_by("policy_id").agg("client_id")
    owner_of = dict(zip(owners["policy_id"], owners["client_id"].to_list(), strict=True))
    unresolved = []
    for row, pn in enr.select("row_number", "policy_number").rows():
        rid, found = f"enrollment:{prefix}{row}", owner_of.get(pn, [])
        client = found[0] if len(set(found)) == 1 else None
        if client is not None and client in client_person:
            people[client_person[client]].append(rid)
            continue
        reason: UnresolvedReason = (
            "policy_not_found"
            if not found
            else "policy_ambiguous"
            if client is None
            else "client_not_in_crm"
        )
        unresolved.append(
            UnresolvedRow(record_id=rid, policy_number=pn, client_id=client, reason=reason)
        )
    return unresolved


def build_multi_truth(fixtures: Path, *, as_of: date) -> MultiTruth:
    world = ensure_multi_a_b(fixtures)
    snap = fixtures / "agency-a-snapshot"
    clusters: dict[str, list[str]] = json.loads((world / "cluster_truth.json").read_text())
    client_person = {c: p for p, cs in clusters.items() for c in cs}
    people = {p: [f"crm:{c}" for c in cs] for p, cs in clusters.items()}
    unresolved = _attach(
        people, client_person, snap / "enrollment_export.csv", snap / "policies.csv", "", as_of
    )
    b = world / "agency-b"
    unresolved += _attach(
        people,
        client_person,
        b / "drop" / "enrollment_export.csv",
        b / "canonical" / "policies.csv",
        "B-",
        as_of,
    )
    key = AnswerKey(
        clusters={p: tuple(sorted(r)) for p, r in sorted(people.items())},
        unresolved=tuple(unresolved),
    )
    lines = (world / "pair_truth.jsonl").read_text().splitlines()
    pairs = [json.loads(x) for x in lines]
    mnm = [json.loads(x) for x in (world / "must_not_merge.jsonl").read_text().splitlines()]
    return MultiTruth(
        key=key,
        commons_clusters=len(clusters),
        commons_pairs={_pair(p["left"], p["right"]): tuple(p["defect_types"]) for p in pairs},
        pair_scope={_pair(p["left"], p["right"]): p["scope"] for p in pairs},
        must_not_merge=tuple(
            MustNotMerge(
                a=f"crm:{m['left']}",
                b=f"crm:{m['right']}",
                defect_type=m["defect_type"],
                reason=m["reason"],
            )
            for m in mnm
        ),
    )
