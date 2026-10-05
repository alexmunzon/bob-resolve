"""Survivorship (SPEC decision 4): one golden record per cluster, every field naming its source.

Identity fields come from the most authoritative source (enrollment over CRM), then the most
recent record. Contact fields come from the most recent record that has a value. "Most recent"
is the record's policy effective date (docs/pr-6-notes.md). If two authoritative records disagree
on DOB or MBI the field is left empty, both candidates are listed, and the person is flagged.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from operator import attrgetter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bob_resolve.config import AUTHORITATIVE_SOURCES, SOURCE_AUTHORITY
from bob_resolve.load.records import PersonRecord
from bob_resolve.normalize.names import names_compatible, normalize_name, split_suffix

Rule = Literal["authoritative_source", "most_recent", "no_value", "identity_conflict"]
GOLDEN_FIELDS = (
    "first_name",
    "last_name",
    "suffix",
    "dob",
    "mbi",
    "address_line1",
    "city",
    "state",
    "zip",
    "phone",
    "email",
)


class FieldSource(BaseModel):
    """A golden value and where it came from. `tier` is how the source record joined the
    person: "rules" (rules-arm auto-match) or "single" (no merge)."""

    model_config = ConfigDict(frozen=True)

    value: str | None
    rule: Rule
    record_id: str | None = None
    source_file: str | None = None
    row_number: int | None = None
    tier: str | None = None
    candidates: tuple[tuple[str, str], ...] = ()


class GoldenPerson(BaseModel):
    model_config = ConfigDict(frozen=True)

    person_id: str
    record_ids: tuple[str, ...]
    fields: dict[str, FieldSource]
    aliases: tuple[str, ...]
    review_reasons: tuple[Literal["IDENTITY_CONFLICT"], ...]


def _strip_suffix(raw: str | None, suffix: str | None) -> str | None:
    tokens = (raw or "").split()
    if suffix and len(tokens) > 1 and normalize_name(tokens[-1]) == suffix:
        tokens = tokens[:-1]
    return " ".join(tokens) or None


def _names(r: PersonRecord) -> tuple[str | None, str | None, str | None]:
    """Display first and last name with any generational suffix moved to its own field."""
    _, _, suffix = split_suffix(r.first_name, r.last_name)
    return _strip_suffix(r.first_name, suffix), _strip_suffix(r.last_name, suffix), suffix


def build_golden(
    records: Sequence[PersonRecord], recency: Mapping[str, date], tier: Mapping[str, str]
) -> GoldenPerson:
    """`recency` maps record id to its policy effective date; `tier` maps record id to tier."""

    def newest(r: PersonRecord) -> int:
        return -recency.get(r.record_id, date.min).toordinal()

    identity = sorted(records, key=lambda r: (SOURCE_AUTHORITY[r.source], newest(r), r.record_id))
    contact = sorted(records, key=lambda r: (newest(r), SOURCE_AUTHORITY[r.source], r.record_id))

    def take(r: PersonRecord, value: str, rule: Rule) -> FieldSource:
        lin = r.lineage
        return FieldSource(
            value=value,
            rule=rule,
            record_id=r.record_id,
            source_file=lin.source_file,
            row_number=lin.row_number,
            tier=tier[r.record_id],
        )

    def first(
        order: list[PersonRecord], get: Callable[[PersonRecord], str | None], rule: Rule
    ) -> FieldSource:
        for r in order:
            if (v := get(r)) is not None:
                return take(r, v, rule)
        return FieldSource(value=None, rule="no_value")

    fields: dict[str, FieldSource] = {}
    namer = next((r for r in identity if all(_names(r)[:2])), None)
    for i, f in enumerate(("first_name", "last_name")):

        def partial_name(r: PersonRecord, index: int = i) -> str | None:
            return _names(r)[index]

        fields[f] = (
            take(namer, _names(namer)[i] or "", "authoritative_source")
            if namer
            else first(identity, partial_name, "authoritative_source")
        )
    fields["suffix"] = first(identity, lambda r: _names(r)[2], "authoritative_source")
    conflicts = False
    getters: dict[str, Callable[[PersonRecord], str | None]] = {
        "dob": lambda r: r.dob.isoformat() if r.dob else None,
        "mbi": lambda r: "".join(c for c in (r.mbi or "").upper() if c.isalnum()) or None,
    }
    for f, get in getters.items():
        auth = [
            (v, r.record_id)
            for r in identity
            if r.source in AUTHORITATIVE_SOURCES
            if (v := get(r)) is not None
        ]
        if len({v for v, _ in auth}) > 1:
            fields[f] = FieldSource(value=None, rule="identity_conflict", candidates=tuple(auth))
            conflicts = True
        else:
            fields[f] = first(identity, get, "authoritative_source")
    with_address = [r for r in contact if r.address_line1]
    for f in ("address_line1", "city", "state", "zip"):
        fields[f] = first(with_address[:1], attrgetter(f), "most_recent")
    fields["phone"] = first(contact, lambda r: r.phone, "most_recent")
    fields["email"] = first(contact, lambda r: r.email, "most_recent")

    golden_first = fields["first_name"].value
    aliases = sorted(
        {
            n
            for r in records
            if (n := _names(r)[0])
            and normalize_name(n) != normalize_name(golden_first)
            and names_compatible(n, golden_first)
        }
    )
    ids = tuple(sorted(r.record_id for r in records))
    return GoldenPerson(
        person_id=f"person:{ids[0]}",
        record_ids=ids,
        fields={f: fields[f] for f in GOLDEN_FIELDS},
        aliases=tuple(aliases),
        review_reasons=("IDENTITY_CONFLICT",) if conflicts else (),
    )
