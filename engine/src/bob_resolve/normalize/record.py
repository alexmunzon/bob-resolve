"""The frozen normalized record that blocking (PR 4) and scoring (PR 5) work on."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from bob_resolve.load.records import PersonRecord, Source
from bob_resolve.normalize import address as ad
from bob_resolve.normalize import names as nm
from bob_resolve.normalize.dob import dob_key
from bob_resolve.normalize.email import normalize_email
from bob_resolve.normalize.phone import normalize_phone


class NormalizedRecord(BaseModel):
    """Comparison-ready values for one source record. The raw record stays the source of truth.

    No household id: in the snapshot it is blank on exactly the copied clients, so it would leak
    the answer into scoring. Households are built later from accepted matches (PR 6)."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: Source
    first_name: str | None
    first_name_canonical: str | None
    last_name: str | None
    last_name_key: str | None
    suffix: str | None
    dob: date | None
    dob_key: str | None
    mbi: str | None
    phone: str | None
    email: str | None
    address_line1: str | None
    zip5: str | None
    zip3: str | None
    state: str | None = None  # two letters, uppercase; GR-007 location check (Review 2)


def normalize_record(r: PersonRecord) -> NormalizedRecord:
    first, last, suffix = nm.split_suffix(r.first_name, r.last_name)
    return NormalizedRecord(
        record_id=r.record_id,
        source=r.source,
        first_name=first,
        first_name_canonical=nm.canonical_first_name(first),
        last_name=last,
        last_name_key=nm.surname_key(last),
        suffix=suffix,
        dob=r.dob,
        dob_key=dob_key(r.dob),
        mbi="".join(c for c in (r.mbi or "").upper() if c.isalnum()) or None,
        phone=normalize_phone(r.phone),
        email=normalize_email(r.email),
        address_line1=ad.normalize_address(r.address_line1),
        zip5=ad.zip5(r.zip),
        zip3=ad.zip3(r.zip),
        state=(r.state or "").strip().upper() or None,
    )
