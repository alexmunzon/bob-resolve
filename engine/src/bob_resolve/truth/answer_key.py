"""The pair answer key: which records are the same real person. Built by code, never hand-edited.

Snapshot rules (SPEC section 5): an enrollment row is the same person as the CRM client its
policy_number resolves to through policies.csv (policy_number matches policies.policy_id); a
copied client (near_duplicate_client or name_dob_collision, via `copy_of`) is the same person as
its original. The person id is the original client_id. Rows that do not resolve are reported.
"""

import json
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Literal

import polars as pl
from pydantic import BaseModel, ConfigDict

from bob_resolve.load import read_crm, read_enrollment

UnresolvedReason = Literal["policy_not_found", "policy_ambiguous", "client_not_in_crm"]


class UnresolvedRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str
    policy_number: str | None
    client_id: str | None
    reason: UnresolvedReason


class PairLabel(BaseModel):
    model_config = ConfigDict(frozen=True)

    example: int
    a: str
    b: str
    reason: str


class AnswerKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    clusters: dict[str, tuple[str, ...]]
    unresolved: tuple[UnresolvedRow, ...] = ()
    must_not_merge: tuple[PairLabel, ...] = ()
    # Enrollment rows whose raw line hash repeats an earlier row. Reported only: the hash stays in
    # lineage and is never a matching feature (it is not on NormalizedRecord).
    exact_duplicate_rows: int = 0

    @property
    def unresolved_ids(self) -> frozenset[str]:
        """Record ids with no person. Metrics exclude these instead of looking them up."""
        return frozenset(u.record_id for u in self.unresolved)

    def summary(self) -> dict[str, int]:
        return {
            "people": len(self.clusters),
            "records": sum(len(r) for r in self.clusters.values()),
            "pairs": len(self.pairs),
            "unresolved_rows": len(self.unresolved),
            "exact_duplicate_rows": self.exact_duplicate_rows,
        }

    @property
    def person_of(self) -> dict[str, str]:
        return {rec: person for person, recs in self.clusters.items() for rec in recs}

    @property
    def pairs(self) -> frozenset[tuple[str, str]]:
        """Every same-person pair, each as (smaller id, larger id)."""
        return frozenset(
            pair for recs in self.clusters.values() for pair in combinations(sorted(recs), 2)
        )


def _key_from_people(
    people: dict[str, list[str]], unresolved: list[UnresolvedRow], mnm: list[PairLabel]
) -> AnswerKey:
    clusters = {p: tuple(sorted(r)) for p, r in sorted(people.items())}
    return AnswerKey(clusters=clusters, unresolved=tuple(unresolved), must_not_merge=tuple(mnm))


def _copy_roots(ground_truth: Path, client_ids: set[str]) -> dict[str, str]:
    """Map every CRM client_id to its original by following `copy_of` to the end."""
    copy_of: dict[str, str] = {}
    for d in json.loads(ground_truth.read_text())["defects"]:
        cid, src = d["record_key"].get("client_id"), d["injected_values"].get("copy_of")
        if cid and src:
            copy_of[cid] = src
    roots = {}
    for cid in client_ids:
        seen, root = {cid}, cid
        while root in copy_of:
            root = copy_of[root]
            if root in seen:
                raise ValueError(f"copy_of cycle at {cid}")
            seen.add(root)
        if root not in client_ids:
            raise ValueError(f"{cid} is a copy of {root}, which is not in clients.csv")
        roots[cid] = root
    return roots


def build_snapshot_answer_key(
    snapshot_dir: Path, enrollment_csv: Path | None = None, *, as_of: date
) -> AnswerKey:
    """Build the key. `enrollment_csv` swaps in another enrollment side with the same rows, such
    as fixtures/agency-a-derived/enrollment_clean.csv; the default is the snapshot export."""
    crm = read_crm(snapshot_dir / "clients.csv", as_of)
    enr = read_enrollment(enrollment_csv or snapshot_dir / "enrollment_export.csv", as_of)
    policies = pl.read_csv(snapshot_dir / "policies.csv", infer_schema=False)
    owners = policies.group_by("policy_id").agg(pl.col("client_id").unique())
    owner_of = dict(zip(owners["policy_id"], owners["client_id"].to_list(), strict=True))
    roots = _copy_roots(snapshot_dir / "ground_truth.json", set(crm["client_id"]))

    people: dict[str, list[str]] = {}
    for cid, root in roots.items():
        people.setdefault(root, []).append(f"crm:{cid}")
    unresolved = []
    for row, pn in zip(enr["row_number"], enr["policy_number"], strict=True):
        rid, found = f"enrollment:{row}", owner_of.get(pn, [])
        client = found[0] if len(found) == 1 else None
        if client is not None and client in roots:
            people[roots[client]].append(rid)
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
    key = _key_from_people(people, unresolved, [])
    dupes = enr.height - enr["raw_sha256"].n_unique()
    return key.model_copy(update={"exact_duplicate_rows": dupes})


def load_hard_case_key(expected_json: Path) -> AnswerKey:
    """Load fixtures/hard-cases/expected.json into the same structures as the snapshot key."""
    raw = json.loads(expected_json.read_text())
    key = _key_from_people(
        raw["people"], [], [PairLabel.model_validate(m) for m in raw["must_not_merge"]]
    )
    person_of = key.person_of
    for label in raw["same_person"]:
        if person_of[label["a"]] != person_of[label["b"]]:
            raise ValueError(f"same_person pair split across people: {label}")
    return key
