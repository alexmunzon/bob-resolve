"""Command line entry point for bob-resolve. More commands arrive in later PRs."""

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from bob_resolve import __version__
from bob_resolve.block import candidate_pairs, dropped_blocks, evaluate
from bob_resolve.block.data import EnrollmentSide, load_normalized
from bob_resolve.config import DEFAULT_AS_OF, SCORE_HIGH, SCORE_LOW, SHARED_IDS_DEFAULT
from bob_resolve.score import evaluate_scores, score_candidates
from bob_resolve.truth.derive import derive_clean_enrollment

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_AS_OF_DEFAULT = datetime.combine(DEFAULT_AS_OF, datetime.min.time())
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


@app.command()
def block(
    enrollment: Annotated[EnrollmentSide, typer.Option(help="Enrollment side to block against")],
    shared_ids: Annotated[
        bool, typer.Option("--shared-ids/--no-shared-ids", help="Use MBI as a blocking key")
    ] = SHARED_IDS_DEFAULT,
    fixtures: Annotated[Path, typer.Option(help="Repo fixtures folder")] = FIXTURES,
    as_of: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%d"], help="Date ages and future DOBs are judged on")
    ] = _AS_OF_DEFAULT,
) -> None:
    """Build candidate pairs and print blocking recall against the pair answer key."""
    day: date = as_of.date()
    records, key = load_normalized(fixtures, enrollment, as_of=day)
    dropped = dropped_blocks(records, shared_ids)
    rep = evaluate(candidate_pairs(records, shared_ids), key, len(records), shared_ids, dropped)
    label = " (derived from the answer key)" if enrollment == "derived" else ""
    typer.echo(f"enrollment: {enrollment}{label}; shared ids: {'on' if shared_ids else 'off'}")
    typer.echo(f"records: {rep.n_records}; all pairs: {rep.all_pairs}")
    typer.echo(f"candidate pairs: {rep.candidate_pairs}; reduction: {rep.reduction_ratio:.4%}")
    typer.echo(f"blocking recall: {rep.recall:.4f} ({rep.found_pairs} of {rep.true_pairs})")
    typer.echo("recall per key:")
    for name, recall in rep.recall_per_key.items():
        typer.echo(f"  {name}: {recall:.4f}")
    for a, b in rep.missed_examples[:10]:
        typer.echo(f"  missed: {a} {b}")
    typer.echo(f"as of: {day.isoformat()}; blocks over the size cap: {len(rep.dropped_blocks)}")
    for d in rep.dropped_blocks:
        typer.echo(f"  dropped: {d.key} value {d.value_masked} shared by {d.size} records")
    typer.echo("measured on synthetic data")


@app.command()
def score(
    enrollment: Annotated[EnrollmentSide, typer.Option(help="Enrollment side to score against")],
    shared_ids: Annotated[
        bool, typer.Option("--shared-ids/--no-shared-ids", help="Use MBI in blocking and scoring")
    ] = SHARED_IDS_DEFAULT,
    fixtures: Annotated[Path, typer.Option(help="Repo fixtures folder")] = FIXTURES,
    as_of: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%d"], help="Date ages and future DOBs are judged on")
    ] = _AS_OF_DEFAULT,
) -> None:
    """Score candidate pairs with the rules arm and print the SPEC decision 2 targets."""
    day: date = as_of.date()
    records, key = load_normalized(fixtures, enrollment, as_of=day)
    scored = score_candidates(records, candidate_pairs(records, shared_ids), shared_ids)
    rep = evaluate_scores(scored, key, shared_ids)
    label = " (derived from the answer key)" if enrollment == "derived" else ""
    typer.echo(f"enrollment: {enrollment}{label}; shared ids: {'on' if shared_ids else 'off'}")
    typer.echo(f"cutoffs: high {SCORE_HIGH}, low {SCORE_LOW}")
    typer.echo(f"auto-merge precision: {rep.auto_merge_precision:.4f}")
    typer.echo(f"auto-merge count: {rep.auto_match}")
    typer.echo(f"gray count: {rep.gray}")
    typer.echo(f"reject count: {rep.auto_reject}")
    typer.echo(f"recall after review: {rep.recall_after_review:.4f} of {rep.true_pairs} true pairs")
    typer.echo(f"auto-matches touching an unresolved row: {rep.unresolved_auto_matched}")
    for rule, n in rep.guard_rail_hits.items():
        typer.echo(f"  {rule} hits: {n}")
    for a, b in rep.false_merges[:10]:
        typer.echo(f"  false merge: {a} {b}")
    typer.echo(f"as of: {day.isoformat()}")
    typer.echo("measured on synthetic data")
