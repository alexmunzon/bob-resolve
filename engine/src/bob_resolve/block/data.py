"""Load one fixture side (snapshot or derived enrollment) as normalized records plus its key."""

from datetime import date
from pathlib import Path
from typing import Literal

from bob_resolve.load import read_crm, read_enrollment, to_records
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
    snapshot, enr_csv = fixtures / "agency-a-snapshot", enrollment_path(fixtures, side)
    crm = to_records(read_crm(snapshot / "clients.csv", as_of), "crm")
    enr = to_records(read_enrollment(enr_csv, as_of), "enrollment")
    key = build_snapshot_answer_key(snapshot, enr_csv, as_of=as_of)
    return [normalize_record(r) for r in crm + enr], key
