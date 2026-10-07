"""Offline identity resolution and packet extraction, without mutable outputs."""

import os
import tempfile
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from bob_resolve.adapters.contract import Packet, canonical_json
from bob_resolve.adapters.intake import IntakeResolution, resolve_intake

app = typer.Typer(help="Resolve synthetic Intake evidence offline.", no_args_is_help=True)


class DataKind(StrEnum):
    SYNTHETIC = "synthetic"


def _required(value: str) -> None:
    if not value.strip():
        raise ValueError("an explicit nonempty ID is required")


def _unused(out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise FileExistsError("output already exists")


def _write_new(out: Path, content: str) -> None:
    """Stage complete bytes, then publish without replacing any concurrent winner."""
    _unused(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".integration-", dir=out.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, out)
    finally:
        os.unlink(temporary)


@app.command("resolve")
def resolve_command(
    packet: Annotated[Path, typer.Option(help="Canonical Intake packet JSON.")],
    intake_root: Annotated[Path, typer.Option(help="Original Intake output directory.")],
    agency_id: Annotated[str, typer.Option(help="Expected explicit synthetic agency ID.")],
    intake_run_id: Annotated[str, typer.Option(help="Expected Intake run ID.")],
    run_id: Annotated[str, typer.Option(help="Explicit new Bob producer run ID.")],
    as_of: Annotated[str, typer.Option(help="Required frozen date, YYYY-MM-DD.")],
    data_kind: Annotated[DataKind, typer.Option(help="Explicit synthetic input attestation.")],
    out: Annotated[Path, typer.Option(help="New native resolution envelope JSON.")],
    shared_ids: Annotated[bool, typer.Option("--shared-ids/--no-shared-ids")] = True,
) -> None:
    """Write native Bob resolution, scored evidence, and its canonical integration packet."""
    try:
        _unused(out)
        for value in (agency_id, intake_run_id, run_id):
            _required(value)
        day = date.fromisoformat(as_of)
        if day.isoformat() != as_of:
            raise ValueError("expected YYYY-MM-DD")
        source = Packet.model_validate_json(packet.read_bytes())
        if (source.agency_id, source.intake_run_id, source.run_id) != (
            agency_id,
            intake_run_id,
            intake_run_id,
        ):
            raise ValueError("packet identity mismatch")
        result = resolve_intake(
            source, intake_root, run_id=run_id, as_of=day, shared_ids=shared_ids
        )
        _write_new(out, canonical_json(result))
    except (OSError, ValueError):
        typer.echo(
            "Integration resolution refused: invalid or stale input, IDs, or output.", err=True
        )
        raise typer.Exit(2) from None
    typer.echo(f"wrote {out}; use integration packet to extract the downstream packet")


@app.command("packet")
def packet_command(
    resolution: Annotated[Path, typer.Option(help="Saved native integration resolution envelope.")],
    agency_id: Annotated[str, typer.Option(help="Expected explicit agency ID.")],
    run_id: Annotated[str, typer.Option(help="Expected Bob producer run ID.")],
    data_kind: Annotated[DataKind, typer.Option(help="Explicit synthetic input attestation.")],
    out: Annotated[Path, typer.Option(help="New canonical resolved packet file.")],
) -> None:
    """Extract the validated packet while retaining native evidence in the original envelope."""
    try:
        _unused(out)
        _required(agency_id)
        _required(run_id)
        result = IntakeResolution.model_validate_json(resolution.read_bytes())
        if (result.packet.agency_id, result.packet.run_id) != (agency_id, run_id):
            raise ValueError("resolution identity mismatch")
        _write_new(out, canonical_json(result.packet))
    except (OSError, ValueError):
        typer.echo(
            "Integration packet refused: invalid resolution, IDs, or existing output.", err=True
        )
        raise typer.Exit(2) from None
    typer.echo(f"wrote {out}")
