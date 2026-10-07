"""Standalone CLI, leaving shared command registration to Session 7."""

import os
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from bob_resolve.broker_workflow import apply, canonical, initial, load_json, refuse_public_output
from bob_resolve.run import RunRefused

PathOption = Annotated[Path, typer.Option()]
TextOption = Annotated[str, typer.Option()]

app = typer.Typer(help="Synthetic offline broker workflow. No messages or identity merges.")


@app.command()
def export(
    run: PathOption, agency_id: TextOption, intake_run_id: TextOption, out: PathOption
) -> None:
    """Export a bound browser context; existing files are never overwritten."""
    try:
        refuse_public_output(out)
        draft = initial(run, agency_id, intake_run_id)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out.parent, prefix=".workflow-context-"
        ) as f:
            f.write(canonical(draft))
            f.flush()
            os.fsync(f.fileno())
            os.link(f.name, out)
    except (OSError, ValueError, KeyError, RunRefused) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command(name="apply")
def apply_command(
    run: PathOption,
    draft: PathOption,
    out: PathOption,
    agency_id: TextOption,
    intake_run_id: TextOption,
) -> None:
    """Apply a browser draft to a new immutable child folder."""
    try:
        result = apply(
            run,
            load_json(draft.read_text(encoding="utf-8")),
            out,
            agency_id=agency_id,
            intake_run_id=intake_run_id,
        )
    except (OSError, ValueError, KeyError, RunRefused) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Created {result['run_id']}; identity changes: 0; reviewer names unauthenticated")


if __name__ == "__main__":
    app()
