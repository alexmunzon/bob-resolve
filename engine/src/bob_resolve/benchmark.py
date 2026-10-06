"""Build an honest benchmark report from immutable, committed run folders."""

import json
import math
from pathlib import Path
from typing import Any

LABEL = "measured on synthetic data"
# The report's own labels, never the scorecard's: only a status can call a dataset held out.
SIDE_LABELS = {
    "snapshot": "snapshot",
    "derived": "derived from the answer key",
    "multi-a-b": "two-agency synthetic world",
    "hard-cases": "hand-written hard cases",
}
ALLOWED_STATUS = {
    "snapshot": ("snapshot",),
    "derived": ("derived",),
    "multi-a-b": ("seen", "held_out"),
    "hard-cases": ("seen",),
}
# Automatic results count only auto-merges. A same-person suggestion is not a resolution until a
# reviewer confirms it, so that figure is reported separately as a hypothetical.
COUNTS: tuple[str, ...] = ("true_pairs", "found_automatically", "suggested_same_person")
COUNTS += ("human_confirmed_merges", "awaiting_review")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _rate(scorecard: dict[str, Any], name: str) -> float | None:
    """A 0 to 1 scorecard metric. Missing is None; present but malformed is an error."""
    metrics = scorecard.get("metrics", {})
    if not isinstance(metrics, dict) or name not in metrics:
        return None
    entry = metrics[name]
    value = entry.get("value") if isinstance(entry, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number from 0 to 1")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a number from 0 to 1")
    return float(value)


def _resolution(scorecard: dict[str, Any]) -> dict[str, int] | None:
    """Counts of how true pairs were resolved, refusing impossible values."""
    block = scorecard.get("resolution")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ValueError("resolution must be an object")
    counts: dict[str, int] = {}
    for name in COUNTS:
        value = block.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"resolution.{name} must be a whole number of zero or more")
        counts[name] = value
    if counts["found_automatically"] + counts["suggested_same_person"] > counts["true_pairs"]:
        raise ValueError("resolution counts more found or suggested pairs than true pairs")
    return counts


def _metrics(scorecard: dict[str, Any]) -> dict[str, Any]:
    precision = _rate(scorecard, "auto_merge_precision")
    counts = _resolution(scorecard)
    recall = f1 = None
    if counts is not None and counts["true_pairs"]:
        recall = counts["found_automatically"] / counts["true_pairs"]
    if precision is not None and recall is not None:
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    suggested = _rate(scorecard, "recall_after_review")
    if suggested is not None and recall is not None and suggested < recall - 1e-6:
        raise ValueError("recall_after_review is below automatic recall")
    return {
        "automatic_precision": None if precision is None else round(precision, 6),
        "automatic_recall": None if recall is None else round(recall, 6),
        "automatic_f1": None if f1 is None else round(f1, 6),
        "recall_if_suggestions_confirmed": None if suggested is None else round(suggested, 6),
        "human_confirmed_merges": None if counts is None else counts["human_confirmed_merges"],
        "awaiting_review": None if counts is None else counts["awaiting_review"],
    }


def _model_tiers_used(manifest: dict[str, Any]) -> list[str]:
    """Model tiers that actually made calls. A mode left on with no recorded calls is not use."""
    modes = manifest.get("modes", {})
    used = []
    for name in ("jev", "llm"):
        tier = manifest.get(name)
        calls = tier.get("calls") if isinstance(tier, dict) else None
        mode = modes.get(name) if isinstance(modes, dict) else None
        if mode not in (None, "off") and _whole(calls) and isinstance(calls, int) and calls > 0:
            used.append(name)
    return used


def _dataset(manifest: dict[str, Any]) -> dict[str, str]:
    args = manifest.get("args", {})
    side = args.get("enrollment") if isinstance(args, dict) else None
    if side not in SIDE_LABELS:
        raise ValueError(f"run {manifest['run_id']} has an unknown dataset side: {side}")
    status = manifest.get("benchmark_status", ALLOWED_STATUS[side][0])
    if status not in ALLOWED_STATUS[side]:
        raise ValueError(f"run {manifest['run_id']}: benchmark_status {status!r} not allowed")
    return {"side": side, "label": SIDE_LABELS[side], "status": status}


def build_benchmark(run_dirs: list[Path]) -> dict[str, Any]:
    """Create one report row per run folder, in run id order."""
    if not run_dirs:
        raise ValueError("at least one run folder is required")
    runs: dict[str, dict[str, Any]] = {}
    for folder in (Path(p) for p in run_dirs):
        manifest_path, scorecard_path = folder / "manifest.json", folder / "scorecard.json"
        if not manifest_path.is_file() or not scorecard_path.is_file():
            raise ValueError(f"{folder} must contain manifest.json and scorecard.json")
        manifest, scorecard = _read_json(manifest_path), _read_json(scorecard_path)
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError(f"{manifest_path} must contain a run_id")
        if run_id in runs:
            raise ValueError(f"duplicate run id: {run_id}")
        args = manifest.get("args", {})
        candidates = scorecard.get("candidate_pairs")
        try:
            metrics = _metrics(scorecard)
        except ValueError as exc:
            raise ValueError(f"run {run_id}: {exc}") from exc
        runs[run_id] = {
            "run_id": run_id,
            "dataset": _dataset(manifest),
            "shared_ids": args.get("shared_ids") if isinstance(args, dict) else None,
            "candidate_pairs": candidates if _whole(candidates) else None,
            "model_tiers_used": _model_tiers_used(manifest),
            "metrics": metrics,
        }
    rows = [runs[k] for k in sorted(runs)]
    return {"schema_version": 1, "label": LABEL, "generated_at": None, "runs": rows}


def write_benchmark(run_dirs: list[Path], out: Path) -> None:
    """Write stable JSON suitable for the dashboard and code review."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(build_benchmark(run_dirs), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
