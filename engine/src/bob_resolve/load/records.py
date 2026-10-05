"""The typed person-record that every later stage works on."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["crm", "enrollment"]
DobIssue = Literal["missing", "invalid", "future", "placeholder", "implausible"]


class Lineage(BaseModel):
    """Where a record came from: file, 1-based data row (header not counted), raw row hash."""

    model_config = ConfigDict(frozen=True)

    source_file: str
    row_number: int = Field(ge=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PersonRecord(BaseModel):
    """One row from one source. Free-text notes are dropped at load and never carried."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: Source
    client_id: str | None = None
    policy_number: str | None = None
    first_name: str | None
    last_name: str | None
    dob: date | None
    dob_issue: DobIssue | None = None
    mbi: str | None
    phone: str | None = None
    email: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    household_id: str | None = None
    lineage: Lineage
