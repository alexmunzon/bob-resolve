"""Load raw records plus their recency, and resolve one fixture side end to end."""

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import polars as pl

from bob_resolve.block import candidate_pairs
from bob_resolve.block.data import EnrollmentSide, enrollment_path
from bob_resolve.golden.resolve import Resolution, resolve
from bob_resolve.load import read_crm, read_enrollment, to_records
from bob_resolve.load.records import PersonRecord
from bob_resolve.normalize.record import normalize_record
from bob_resolve.score import score_candidates


def load_people(
    crm_csv: Path,
    enrollment_csv: Path,
    policies_csv: Path | None,
    as_of: date,
    row_prefix: str = "",
) -> tuple[list[PersonRecord], dict[str, date]]:
    """Records plus "most recent" dates: an enrollment row's own effective date; a CRM client's
    latest policy effective date in policies.csv. A record with neither has no date."""
    crm, enr = read_crm(crm_csv, as_of), read_enrollment(enrollment_csv, as_of)
    recency = {
        f"enrollment:{row_prefix}{row}": d
        for row, d in enr.select("row_number", "effective_date").iter_rows()
        if d is not None
    }
    if policies_csv is not None:
        latest = (
            pl.read_csv(policies_csv, infer_schema=False)
            .group_by("client_id")
            .agg(pl.col("effective_date").str.to_date("%Y-%m-%d", strict=False).max())
        )
        recency |= {f"crm:{c}": d for c, d in latest.iter_rows() if d is not None}
    records = to_records(crm, "crm") + to_records(enr, "enrollment", row_prefix)
    if policies_csv is not None:
        keys = policy_keys(policies_csv, enr, row_prefix)
        records = [r.model_copy(update={"policy_keys": keys.get(r.record_id, ())}) for r in records]
    return records, recency


def policy_keys(policies_csv: Path, enr: pl.DataFrame, prefix: str) -> dict[str, tuple[str, ...]]:
    """PR 10b: each CRM client's policy ids and carrier member ids from policies.csv; each
    enrollment row's policy number and that policy's carrier member id. Policy ids get the
    agency prefix, so two agencies never share one by accident."""
    pol = pl.read_csv(policies_csv, infer_schema=False)
    out: dict[str, set[str]] = {}
    by_policy: dict[str, set[str]] = {}
    for pid, cid, carrier, member in pol.select(
        "policy_id", "client_id", "carrier", "carrier_member_id"
    ).rows():
        keys = {f"policy:{prefix}{pid}"} | ({f"member:{carrier}:{member}"} if member else set())
        out.setdefault(f"crm:{cid}", set()).update(keys)
        by_policy.setdefault(pid, set()).update(keys)
    for row, pn in enr.select("row_number", "policy_number").rows():
        if pn:
            out[f"enrollment:{prefix}{row}"] = by_policy.get(pn, {f"policy:{prefix}{pn}"})
    return {r: tuple(sorted(k)) for r, k in out.items()}


def resolve_side(
    fixtures: Path,
    side: EnrollmentSide,
    shared_ids: bool,
    as_of: date,
    *,
    run_id: str,
    clock: Callable[[], datetime],
) -> Resolution:
    snapshot = fixtures / "agency-a-snapshot"
    records, recency = load_people(
        snapshot / "clients.csv", enrollment_path(fixtures, side), snapshot / "policies.csv", as_of
    )
    norm = [normalize_record(r) for r in records]
    scored = score_candidates(norm, candidate_pairs(norm, shared_ids), shared_ids)
    return resolve(records, scored, recency, run_id=run_id, clock=clock, shared_ids=shared_ids)
