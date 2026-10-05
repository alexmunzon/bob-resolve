"""Command line entry point for bob-resolve. More commands arrive in later PRs."""

from pathlib import Path
from typing import Annotated

import typer

from bob_resolve import __version__
from bob_resolve.truth.derive import derive_clean_enrollment

app = typer.Typer(help="bob-resolve. Synthetic data only.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Keep the app a command group so subcommands arrive cleanly in later PRs."""


@app.command()
def version() -> None:
    """Print the engine version."""
    typer.echo(__version__)


fixtures_app = typer.Typer(help="Build derived fixtures from the frozen snapshot.")
app.add_typer(fixtures_app, name="fixtures")


@fixtures_app.command("derive")
def fixtures_derive(
    snapshot: Annotated[Path, typer.Option(help="Snapshot folder (agency-a-snapshot)")],
    out: Annotated[Path, typer.Option(help="Output folder (agency-a-derived)")],
) -> None:
    """Write the derived clean enrollment side (derived from the answer key)."""
    result = derive_clean_enrollment(snapshot, out)
    for defect, n in result.rows_changed.items():
        typer.echo(f"{defect}: {n} rows changed")
    typer.echo(
        f"{result.defects_with_rows} of {result.defects_total} defects reached an enrollment row; "
        f"{len(result.defects_without_rows)} have none"
    )
    typer.echo(f"enrollment_clean.csv sha256 {result.out_sha256}")
