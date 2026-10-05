"""Derived clean enrollment side (SPEC section 5): undo the CRM identity defects in enrollment.

The intake kit writes its enrollment export after the identity injectors, so a nickname, name
typo, or DOB defect shows the same defected value in both files. This module rebuilds the
enrollment side from the answer key: for each row whose client (through policies.csv) carries a
nickname, name_typo, dob_transposition, or dob_month_day_swap defect, the recorded original
(`from`) goes back into that one field. Every other byte stays as it was. Deterministic.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict

DERIVED_DEFECTS = ("nickname", "name_typo", "dob_transposition", "dob_month_day_swap")
FIELD_TO_COLUMN = {
    "first_name": "member_first",
    "last_name": "member_last",
    "dob": "Birth Dt (mm/dd/yy)",
}
OUT_NAME = "enrollment_clean.csv"
SEPARATOR = ";"


class RowChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    row_number: int
    client_id: str
    defect_type: str
    column: str
    was: str
    now: str


class DeriveResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    changes: tuple[RowChange, ...]
    defects_total: int
    defects_without_rows: tuple[str, ...]
    out_sha256: str

    @property
    def defects_with_rows(self) -> int:
        return self.defects_total - len(self.defects_without_rows)

    @property
    def rows_changed(self) -> dict[str, int]:
        counts = Counter(c.defect_type for c in self.changes)
        return {t: counts[t] for t in DERIVED_DEFECTS}


def _mdy2(iso: str) -> str:
    """1951-12-10 becomes 12/10/51, the enrollment export's DOB format."""
    y, m, d = iso.split("-")
    return f"{m}/{d}/{y[2:]}"


def _policy_owner(policies_csv: Path) -> dict[str, str]:
    """policy_id to client_id, only for policy ids with exactly one owner."""
    owners = (
        pl.read_csv(policies_csv, infer_schema=False)
        .group_by("policy_id")
        .agg(pl.col("client_id").unique())
        .filter(pl.col("client_id").list.len() == 1)
    )
    return dict(zip(owners["policy_id"], owners["client_id"].list.first(), strict=True))


def derive_clean_enrollment(snapshot_dir: Path, out_dir: Path) -> DeriveResult:
    """Write out_dir/enrollment_clean.csv and return what changed."""
    defects = [
        d
        for d in json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]
        if d["defect_type"] in DERIVED_DEFECTS
    ]
    by_client: dict[str, dict[str, Any]] = {}
    for d in defects:
        cid = d["record_key"]["client_id"]
        if cid in by_client:
            raise ValueError(f"{cid} has more than one identity defect")
        by_client[cid] = d
    owner = _policy_owner(snapshot_dir / "policies.csv")

    text = (snapshot_dir / "enrollment_export.csv").read_bytes().decode("utf-8")
    lines = text.split("\n")
    header = lines[0].split(SEPARATOR)
    policy_col = header.index("policy_number")
    changes: list[RowChange] = []
    reached: set[str] = set()
    for i in range(1, len(lines)):
        if not lines[i]:
            continue
        cells = lines[i].split(SEPARATOR)
        cid = owner.get(cells[policy_col])
        d = by_client.get(cid) if cid else None
        if d is None or cid is None:
            continue
        iv = d["injected_values"]
        col = header.index(FIELD_TO_COLUMN[iv["field"]])
        was, now = (iv["to"], iv["from"])
        if iv["field"] == "dob":
            was, now = _mdy2(was), _mdy2(now)
        if cells[col] != was:
            raise ValueError(f"row {i}: expected {was!r} in {header[col]}, found {cells[col]!r}")
        cells[col] = now
        lines[i] = SEPARATOR.join(cells)
        reached.add(cid)
        changes.append(
            RowChange(
                row_number=i,
                client_id=cid,
                defect_type=d["defect_type"],
                column=header[col],
                was=was,
                now=now,
            )
        )
    data = "\n".join(lines).encode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUT_NAME).write_bytes(data)
    return DeriveResult(
        changes=tuple(changes),
        defects_total=len(defects),
        defects_without_rows=tuple(sorted(set(by_client) - reached)),
        out_sha256=hashlib.sha256(data).hexdigest(),
    )
