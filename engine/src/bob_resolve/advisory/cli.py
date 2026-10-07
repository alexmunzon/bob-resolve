"""An explicitly offline, non-overwriting advisory sidecar command."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from bob_resolve.adapters.contract import Packet, canonical_json
from bob_resolve.advisory.sidecar import build_sidecar
from bob_resolve.integration_cli import _write_new

app = typer.Typer(help="Offline second opinions. Never approves a match.")


class Mode(StrEnum):
    OFF = "off"
    REPLAY = "replay"


@app.command("sidecar")
def sidecar(
    source_packet: Annotated[Path, typer.Option(help="Original synthetic Intake packet.")],
    resolution: Annotated[Path, typer.Option(help="Saved native integration resolution.")],
    intake_root: Annotated[Path, typer.Option(help="Hash-pinned source artifacts.")],
    out: Annotated[Path, typer.Option(help="New sidecar file, outside source directory.")],
    mode: Annotated[Mode, typer.Option()] = Mode.OFF,
    responses: Annotated[
        Path | None, typer.Option(help="Local hand-written fixture directory.")
    ] = None,
) -> None:
    try:
        if out.resolve().is_relative_to(intake_root.resolve()):
            raise ValueError("sidecar must be outside immutable source directory")
        source = Packet.model_validate_json(source_packet.read_bytes())
        result = build_sidecar(
            source,
            resolution.read_bytes(),
            intake_root,
            mode=mode.value,
            responses=responses,
        )
        _write_new(out, canonical_json(result))
    except (OSError, ValueError):
        typer.echo("Advisory refused: invalid/stale source or output. No inputs changed.", err=True)
        raise typer.Exit(2) from None
    typer.echo(
        f"wrote {out}; {len(result.entries)} review items; no model called or matches approved"
    )
