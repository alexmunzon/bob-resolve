"""Command line entry point for bob-resolve. More commands arrive in later PRs."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from bob_resolve import __version__
from bob_resolve.block import candidate_pairs, dropped_blocks, evaluate
from bob_resolve.block.data import EnrollmentSide, load_normalized
from bob_resolve.cluster import split_on_conflict
from bob_resolve.config import DEFAULT_AS_OF, SCORE_HIGH, SCORE_LOW, SHARED_IDS_DEFAULT
from bob_resolve.run import RunOptions, RunRefused, RunSide, apply_review, execute
from bob_resolve.score import evaluate_scores, score_candidates
from bob_resolve.truth.derive import derive_clean_enrollment

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
AgencyASide = Literal["snapshot", "derived", "hard-cases"]
World = Literal["agency-a", "multi-a-b"]
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
    _, kept, _ = split_on_conflict(
        records, [p for p in scored if p.decision == "AUTO_MATCH"], shared_ids=shared_ids
    )
    rep = evaluate_scores(scored, key, shared_ids, kept=kept)  # final edges (Review 2, F8)
    label = " (derived from the answer key)" if enrollment == "derived" else ""
    typer.echo(f"enrollment: {enrollment}{label}; shared ids: {'on' if shared_ids else 'off'}")
    typer.echo(f"cutoffs: high {SCORE_HIGH}, low {SCORE_LOW}")
    typer.echo(f"auto-merge precision: {rep.auto_merge_precision:.4f}")
    typer.echo(f"auto-merge count: {rep.auto_match} (after cluster splits)")
    typer.echo(f"auto-matches cut by a cluster conflict: {rep.cut_by_cluster}")
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


def _now(now: str | None) -> tuple[datetime, bool]:
    """A fixed --now freezes every timestamp and leaves timings out, so reruns are identical."""
    return (datetime.fromisoformat(now), True) if now else (datetime.now(UTC), False)


AsOf = Annotated[
    datetime, typer.Option(formats=["%Y-%m-%d"], help="Date ages and future DOBs are judged on")
]
Now = Annotated[str | None, typer.Option(help="Fixed ISO time for a repeatable run")]
Parquet = Annotated[bool, typer.Option("--parquet/--no-parquet", help="Also write people.parquet")]
MaskMbi = Annotated[
    bool, typer.Option("--mask-mbi", help="Mask the MBI in people.csv to its last 4 characters")
]


@app.command("run")
def run_command(
    out: Annotated[Path, typer.Option(help="Runs folder; the run is written to <out>/<run-id>")],
    run_id: Annotated[str, typer.Option(help="Run folder name")],
    enrollment: Annotated[
        AgencyASide | None,
        typer.Option(help="Agency A world: snapshot, derived (from the answer key), or hard-cases"),
    ] = None,
    world: Annotated[
        World, typer.Option(help="agency-a (pick --enrollment) or multi-a-b (seen, commons)")
    ] = "agency-a",
    shared_ids: Annotated[
        bool, typer.Option("--shared-ids/--no-shared-ids", help="Use MBI in blocking and scoring")
    ] = SHARED_IDS_DEFAULT,
    overwrite: Annotated[bool, typer.Option(help="Replace an existing run folder")] = False,
    as_of: AsOf = _AS_OF_DEFAULT,
    now: Now = None,
    parquet: Parquet = True,
    mask_mbi: MaskMbi = False,
    fixtures: Annotated[Path, typer.Option(help="Repo fixtures folder")] = FIXTURES,
) -> None:
    """Resolve one fixture side end to end and write an immutable run folder. Jev and LLM off."""
    if (world == "multi-a-b") == (enrollment is not None):
        typer.echo("Pass --enrollment for --world agency-a, and no --enrollment for multi-a-b.")
        raise typer.Exit(2)
    side: RunSide = enrollment or "multi-a-b"
    t, frozen = _now(now)
    opts = RunOptions(
        fixtures.resolve(), side, shared_ids, out, run_id, as_of.date(), t, frozen,
        overwrite, parquet, mask_mbi,
    )  # fmt: skip
    try:
        folder = execute(opts)
    except RunRefused as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    sc = json.loads((folder / "scorecard.json").read_text())
    typer.echo(f"run {run_id}: {sc['people']} people, {sc['households']} households")
    typer.echo(f"world: {sc['enrollment_side_label']}")
    typer.echo(f"review queue: {sc['review_queue']}")
    for name, m in sc["metrics"].items():
        typer.echo(f"{name}: {m['value']:.4f} (target {m['target']})")
    typer.echo("measured on synthetic data")


review_app = typer.Typer(help="Human review of the queue. Labels are stored, never learned from.")
app.add_typer(review_app, name="review")


@review_app.command("apply")
def review_apply(
    run: Annotated[Path, typer.Option(help="Existing run folder (never changed)")],
    decisions: Annotated[Path, typer.Option(help="Decisions file (JSONL)")],
    out: Annotated[Path, typer.Option(help="Runs folder for the new run")],
    run_id: Annotated[str, typer.Option(help="New run folder name")],
    overwrite: Annotated[bool, typer.Option(help="Replace an existing new run folder")] = False,
    now: Now = None,
    parquet: Parquet = True,
    fixtures: Annotated[Path, typer.Option(help="Repo fixtures folder")] = FIXTURES,
) -> None:
    """Write a new run with the decisions applied; the merge log only gains new lines."""
    t, frozen = _now(now)
    opts = RunOptions(
        fixtures.resolve(), "snapshot", True, out, run_id, date.min, t, frozen, overwrite, parquet
    )
    try:
        folder, applied, cut, stored = apply_review(run, decisions, opts)
    except (RunRefused, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"new run {folder.name}: {applied} decisions applied, {stored} stored only, "
               f"{cut} cut by the cluster check")  # fmt: skip
