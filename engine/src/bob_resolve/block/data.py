"""Load one fixture side (snapshot or derived enrollment) as normalized records plus its key."""

from datetime import date
from pathlib import Path
from typing import Literal

from bob_resolve.normalize.record import NormalizedRecord, normalize_record
from bob_resolve.truth import AnswerKey, build_snapshot_answer_key

EnrollmentSide = Literal["snapshot", "derived"]


def enrollment_path(fixtures: Path, side: EnrollmentSide) -> Path:
    if side == "derived":
        return fixtures / "agency-a-derived" / "enrollment_clean.csv"
    return fixtures / "agency-a-snapshot" / "enrollment_export.csv"


def load_normalized(
    fixtures: Path, side: EnrollmentSide, as_of: date
) -> tuple[list[NormalizedRecord], AnswerKey]:
    """CRM clients plus the chosen enrollment side, normalized, with the matching answer key."""
    from bob_resolve.golden.data import load_people  # late: golden imports this module

    snapshot, enr_csv = fixtures / "agency-a-snapshot", enrollment_path(fixtures, side)
    recs, _ = load_people(snapshot / "clients.csv", enr_csv, snapshot / "policies.csv", as_of)
    key = build_snapshot_answer_key(snapshot, enr_csv, as_of=as_of)
    return [normalize_record(r) for r in recs], key
