"""`bob-resolve run`: load, normalize, block, score, cluster, golden, queue, and write one
immutable run folder (SPEC section 7). With --now and --as-of two runs are byte-identical.

A run folder is never changed after it is written. `review apply` reads one and writes a new
one whose merge log starts with the old log's bytes and only appends (SPEC 6 step 8).
"""

import hashlib
import json
import platform
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import polars as pl

from bob_resolve import __version__
from bob_resolve.block import candidate_pairs, dropped_blocks, evaluate
from bob_resolve.cluster import components
from bob_resolve.config import (
    GRAY_SAME_PERSON_MIN,
    MAX_BLOCK_SIZE,
    PUBLIC_FOLDER_NAMES,
    RUN_JEV_MODE,
    RUN_LLM_MODE,
    SCORE_HIGH,
    SCORE_LOW,
    TARGET_AUTO_MERGE_PRECISION,
    TARGET_BLOCKING_RECALL,
    TARGET_RECALL_AFTER_REVIEW,
)
from bob_resolve.golden import GOLDEN_FIELDS, Resolution, resolve
from bob_resolve.golden.data import load_people
from bob_resolve.load import read_enrollment
from bob_resolve.mergelog import append_entries
from bob_resolve.normalize.record import normalize_record
from bob_resolve.queue import QueueItem, ReviewDecision, build_queue, mask_mbi, read_decisions
from bob_resolve.score import evaluate_scores, score_candidates
from bob_resolve.truth import AnswerKey, build_snapshot_answer_key, load_hard_case_key

RunSide = Literal["snapshot", "derived", "hard-cases"]
LABEL = "measured on synthetic data"
SIDE_LABEL = {
    "snapshot": "snapshot",
    "derived": "derived from the answer key",
    "hard-cases": "hand-written hard cases",
}


class RunRefused(Exception):
    """The run cannot start: the folder exists without --overwrite, or inputs changed."""


@dataclass(frozen=True)
class RunOptions:
    fixtures: Path
    side: RunSide
    shared_ids: bool
    out: Path  # the runs folder; the run folder is out / run_id
    run_id: str
    as_of: date
    now: datetime
    frozen_clock: bool  # True with --now: timings are not recorded, so output is byte-identical
    overwrite: bool = False
    parquet: bool = True
    mask_mbi: bool = False  # mask the MBI in people.csv to its last 4 (required under public/)


@dataclass(frozen=True)
class Parent:
    """What `review apply` carries from the old run into the new one."""

    run_id: str
    log: bytes
    decisions: tuple[ReviewDecision, ...]
    forced: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    new: frozenset[tuple[str, str]] = field(default_factory=frozenset)  # this apply's pairs


def input_files(fixtures: Path, side: RunSide) -> dict[str, Path]:
    if side == "hard-cases":
        hc = fixtures / "hard-cases"
        return {
            "crm": hc / "clients.csv",
            "enrollment": hc / "enrollment_export.csv",
            "answer_key": hc / "expected.json",
        }
    snap = fixtures / "agency-a-snapshot"
    enr = fixtures / "agency-a-derived/enrollment_clean.csv"
    return {
        "crm": snap / "clients.csv",
        "enrollment": enr if side == "derived" else snap / "enrollment_export.csv",
        "policies": snap / "policies.csv",
        "answer_key": snap / "ground_truth.json",
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_policy_owners(files: dict[str, Path], as_of: date) -> dict[str, str]:
    """Records whose merge would move coverage, each mapped to the client id that owns the
    policy: a CRM client with an ACTIVE policy in policies.csv owns it; an approved enrollment
    row is owned by the client whose policy id matches its policy number, or by the row itself
    when no policies file names one (so it counts as a different owner)."""
    enr = read_enrollment(files["enrollment"], as_of)
    owner_of: dict[str, str] = {}
    out: dict[str, str] = {}
    if "policies" in files:
        pol = pl.read_csv(files["policies"], infer_schema=False)
        owner_of = dict(pol.select("policy_id", "client_id").rows())
        out |= {f"crm:{c}": c for c in pol.filter(pl.col("status") == "ACTIVE")["client_id"]}
    for n, s, pn in enr.select("row_number", "application_status", "policy_number").rows():
        if s == "Approved":
            out[f"enrollment:{n}"] = owner_of.get(pn or "", f"enrollment:{n}")
    return out


def households(res: Resolution, crm_household: dict[str, str]) -> list[dict[str, Any]]:
    """People linked through the agency's own CRM household ids. A person with no CRM household
    (enrollment rows only) is a household of one."""
    hh_people: dict[str, list[str]] = defaultdict(list)
    for p in res.people:
        for r in p.record_ids:
            if h := crm_household.get(r):
                hh_people[h].append(p.person_id)
    edges = [(ps[0], q) for ps in hh_people.values() for q in ps[1:]]
    out = []
    for comp in components((p.person_id for p in res.people), edges):
        src = sorted({h for h, ps in hh_people.items() if ps[0] in comp})
        out.append({"household_id": f"household:{comp[0]}", "person_ids": list(comp),
                    "source_household_ids": src})  # fmt: skip
    return out


def people_frame(res: Resolution, household_of: dict[str, str], mask: bool) -> pl.DataFrame:
    rows = []
    for p in res.people:
        row: dict[str, Any] = {
            "person_id": p.person_id,
            "household_id": household_of[p.person_id],
            "record_ids": ";".join(p.record_ids),
            "aliases": ";".join(p.aliases) or None,
            "review_reasons": ";".join(p.review_reasons) or None,
        }
        for f in GOLDEN_FIELDS:
            s = p.fields[f]
            row |= {f: s.value, f"{f}_source": s.record_id, f"{f}_source_file": s.source_file,
                    f"{f}_row": s.row_number, f"{f}_rule": s.rule, f"{f}_tier": s.tier}  # fmt: skip
        if mask:
            row["mbi"] = mask_mbi(row["mbi"])
        rows.append(row)
    schema = {k: pl.Int64 if k.endswith("_row") else pl.String for k in rows[0]} if rows else None
    return pl.DataFrame(rows, schema=schema)


def metric(value: float, target: float, o: RunOptions) -> dict[str, Any]:
    return {"value": round(value, 6), "target": target, "meets_target": value >= target,
            "label": LABEL, "enrollment_side": o.side, "shared_ids": o.shared_ids}  # fmt: skip


def scorecard(o: RunOptions, key: AnswerKey, c: dict[str, Any]) -> dict[str, Any]:
    res: Resolution = c["res"]
    golden_of = {r: p.person_id for p in res.people for r in p.record_ids}
    pieces: dict[str, set[str]] = defaultdict(set)
    for rec, person in key.person_of.items():
        if rec in golden_of:
            pieces[person].add(golden_of[rec])
    truth = key.person_of
    tiers = Counter(e.tier for e in res.log if e.action == "merge")
    queue: list[QueueItem] = c["queue"]
    return {
        "label": LABEL,
        "enrollment_side": o.side,
        "enrollment_side_label": SIDE_LABEL[o.side],
        "shared_ids": o.shared_ids,
        "records_in": c["n_records"],
        "people": len(res.people),
        "households": len(c["households"]),
        "unidentifiable": len(res.unidentifiable),
        "people_left_split": sum(len(v) - 1 for v in pieces.values()),
        "people_holding_two_true_people": sum(
            len({truth.get(r) for r in p.record_ids}) > 1 for p in res.people
        ),
        "true_pairs": len(key.pairs),
        "candidate_pairs": c["blocking"].candidate_pairs,
        "metrics": {
            "blocking_recall": metric(c["blocking"].recall, TARGET_BLOCKING_RECALL, o),
            "auto_merge_precision": metric(
                c["scores"].auto_merge_precision, TARGET_AUTO_MERGE_PRECISION, o
            ),
            "recall_after_review": metric(
                c["scores"].recall_after_review, TARGET_RECALL_AFTER_REVIEW, o
            ),
        },
        "merges": {
            "auto": tiers["rules"],
            "review": tiers["review"],
            "splits": sum(e.action == "split" for e in res.log),
        },  # fmt: skip
        "per_tier": {
            "rules": {
                "auto_match": c["scores"].auto_match,
                "gray": c["scores"].gray,
                "auto_reject": c["scores"].auto_reject,
            },  # fmt: skip
            "jev": {"mode": RUN_JEV_MODE, "calls": 0},
            "llm": {"mode": RUN_LLM_MODE, "calls": 0},
        },
        "guard_rail_hits": c["scores"].guard_rail_hits,
        "review_queue": {
            "size": len(queue),
            "by_severity": {s: sum(i.severity == s for i in queue) for s in ("high", "medium")},
            "by_reason": dict(sorted(Counter(i.reason for i in queue).items())),
        },
    }


def compute(o: RunOptions, parent: Parent | None) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    def lap(stage: str) -> None:
        nonlocal t0
        timings[stage] = round((time.perf_counter() - t0) * 1000, 1)
        t0 = time.perf_counter()

    files = input_files(o.fixtures, o.side)
    records, recency = load_people(files["crm"], files["enrollment"], files.get("policies"),
                                   o.as_of)  # fmt: skip
    norm = [normalize_record(r) for r in records]
    lap("load_and_normalize")
    pairs = candidate_pairs(norm, o.shared_ids)
    lap("block")
    scored = score_candidates(norm, pairs, o.shared_ids)
    lap("score")
    forced = parent.forced if parent else frozenset()
    final = [p.model_copy(update={"decision": "AUTO_MATCH"}) if (p.a, p.b) in forced else p
             for p in scored]  # fmt: skip
    res = resolve(records, final, recency, run_id=o.run_id, clock=lambda: o.now,
                  review_pairs=forced)  # fmt: skip
    lap("cluster_and_golden")
    skip = {d.item_id for d in parent.decisions} if parent else set()
    by_id = {r.record_id: r for r in records}
    queue = build_queue(res, scored, by_id, {r.record_id: r for r in norm},
                        active_policy_owners(files, o.as_of), o.shared_ids, skip)  # fmt: skip
    lap("review_queue")
    if o.side == "hard-cases":
        key = load_hard_case_key(files["answer_key"])
    else:
        snap = o.fixtures / "agency-a-snapshot"
        enr = files["enrollment"] if o.side == "derived" else None
        key = build_snapshot_answer_key(snap, enr, as_of=o.as_of)
    crm_hh = {r.record_id: r.household_id for r in records if r.household_id}
    c: dict[str, Any] = {
        "files": files,
        "res": res,
        "queue": queue,
        "n_records": len(records),
        "households": households(res, crm_hh),
        "blocking": evaluate(
            pairs, key, len(norm), o.shared_ids, tuple(dropped_blocks(norm, o.shared_ids))
        ),  # fmt: skip
        "scores": evaluate_scores(scored, key, o.shared_ids),
    }
    lap("scorecard")
    c["scorecard"] = scorecard(o, key, c)
    c["timings"] = None if o.frozen_clock else timings
    return c


def _json(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_folder(o: RunOptions, c: dict[str, Any], d: Path, parent: Parent | None) -> None:
    res: Resolution = c["res"]
    hh = c["households"]
    household_of = {p: h["household_id"] for h in hh for p in h["person_ids"]}
    people = people_frame(res, household_of, o.mask_mbi)
    people.write_csv(d / "people.csv")
    if o.parquet:
        people.write_parquet(d / "people.parquet")
    _json({"label": LABEL, "count": len(hh), "households": hh}, d / "households.json")
    log = d / "merge_log.jsonl"
    log.write_bytes(parent.log if parent else b"")
    seen = {(e["action"], e["a"], e["b"]) for e in map(json.loads, log.read_text().splitlines())}
    append_entries(log, [e for e in res.log if (e.action, e.a, e.b) not in seen])
    (d / "review_queue.jsonl").write_text(
        "".join(i.model_dump_json() + "\n" for i in c["queue"]), encoding="utf-8"
    )
    if parent:
        (d / "decisions.jsonl").write_text(
            "".join(x.model_dump_json() + "\n" for x in parent.decisions), encoding="utf-8"
        )
    _json(c["scorecard"], d / "scorecard.json")
    off = {"mode": "off", "calls": 0, "cost_usd": 0.0}
    human = {(e.a, e.b) for e in res.log if e.action == "merge" and e.tier == "review"}
    new = parent.new if parent else frozenset()
    files: dict[str, Path] = c["files"]
    _json(
        {
            "label": LABEL,
            "run_id": o.run_id,
            "parent_run_id": parent.run_id if parent else None,
            "decisions_applied": len(new & human),
            "decisions_cut": [list(p) for p in sorted(new - human)],
            "review_pairs": [list(p) for p in sorted(human)],
            "created_at": o.now.isoformat(),
            "as_of": o.as_of.isoformat(),
            "args": {"enrollment": o.side, "shared_ids": o.shared_ids, "mask_mbi": o.mask_mbi},
            "inputs": [
                {"role": role, "path": p.relative_to(o.fixtures).as_posix(), "sha256": sha256(p)}
                for role, p in files.items()
            ],
            "versions": {
                "engine": __version__,
                "polars": pl.__version__,
                "python": ".".join(platform.python_version_tuple()[:2]),
            },  # fmt: skip
            "thresholds": {
                "score_high": SCORE_HIGH,
                "score_low": SCORE_LOW,
                "gray_same_person_min": GRAY_SAME_PERSON_MIN,
                "max_block_size": MAX_BLOCK_SIZE,
            },  # fmt: skip
            "modes": {"rules": "on", "jev": RUN_JEV_MODE, "llm": RUN_LLM_MODE},
            "jev": off,
            "llm": off,
            "timings_ms": c["timings"],
            "outputs": {p.name: sha256(p) for p in sorted(d.iterdir())},
        },
        d / "manifest.json",
    )


def execute(o: RunOptions, parent: Parent | None = None) -> Path:
    """Write into a temp folder, then rename into place, so a failed run leaves nothing behind
    and --overwrite keeps the old run until the new one is complete."""
    final = o.out / o.run_id
    if not o.mask_mbi and PUBLIC_FOLDER_NAMES & set(o.out.resolve().parts):
        raise RunRefused(f"{o.out} is a public folder; pass --mask-mbi so no full MBI lands there.")
    if final.exists() and not o.overwrite:
        raise RunRefused(
            f"{final} already exists. Runs are immutable; pass --overwrite to redo it."
        )
    c = compute(o, parent)
    o.out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{o.run_id}-", dir=o.out))
    tmp.chmod(0o755)
    old = o.out / f".{o.run_id}-replaced"
    try:
        write_folder(o, c, tmp, parent)
        if final.exists():
            final.rename(old)
        tmp.rename(final)
    finally:
        for leftover in (tmp, old):
            if leftover.exists():
                shutil.rmtree(leftover)
    return final


def verify_folder(run: Path) -> dict[str, Any]:
    """Return the manifest after checking every output still has its recorded hash."""
    m: dict[str, Any] = json.loads((run / "manifest.json").read_text())
    for name, digest in m["outputs"].items():
        if sha256(run / name) != digest:
            raise RunRefused(f"{run.name}/{name} changed after the run was written.")
    return m


def refuse_parent_overlap(old: Path, new: Path, old_id: str, new_id: str) -> None:
    """The new run may never replace or sit inside the old one: compare real paths (symlinks
    followed), so --overwrite can never remove the parent run or a folder that holds it."""
    a, b = old.resolve(), new.resolve()
    if a == b or b in a.parents or a in b.parents:
        raise RunRefused(f"The new run folder {new} overlaps its parent run {old}. Pick another.")
    if new_id == old_id:
        raise RunRefused(f"The new run id equals its parent's ({old_id}). Pick another.")


def apply_review(old: Path, decisions: Path, o: RunOptions) -> tuple[Path, int, int, int]:
    """New run from an old run plus human labels. A "same person" label on a gray pair becomes
    a merge with tier "review"; every other label is stored in decisions.jsonl, not applied.
    Earlier review merges and labels carry forward. Returns the new folder, merges kept, merges
    cut again by the cluster check, labels stored only."""
    m = verify_folder(old)
    refuse_parent_overlap(old, o.out / o.run_id, m["run_id"], o.run_id)
    for i in m["inputs"]:
        if sha256(o.fixtures / i["path"]) != i["sha256"]:
            raise RunRefused(f"Input {i['path']} changed since run {m['run_id']}.")
    items = {
        i.item_id: i
        for i in map(QueueItem.model_validate_json, (old / "review_queue.jsonl").open())
    }
    labels = read_decisions(decisions)
    if unknown := [d.item_id for d in labels if d.item_id not in items]:
        raise RunRefused(f"Decisions name items not in run {m['run_id']}: {unknown[:5]}")
    new = frozenset(
        (items[d.item_id].pairs[0].a, items[d.item_id].pairs[0].b)
        for d in labels
        if d.decision == "same_person" and items[d.item_id].kind == "gray_pair"
    )
    earlier = old / "decisions.jsonl"
    carried = tuple(read_decisions(earlier)) if earlier.exists() else ()
    kept_before = frozenset((a, b) for a, b in m.get("review_pairs", []))
    parent = Parent(m["run_id"], (old / "merge_log.jsonl").read_bytes(),
                    (*carried, *labels), kept_before | new, new)  # fmt: skip
    side: RunSide = m["args"]["enrollment"]
    opts = RunOptions(o.fixtures, side, m["args"]["shared_ids"], o.out, o.run_id,
                      date.fromisoformat(m["as_of"]), o.now, o.frozen_clock, o.overwrite,
                      o.parquet, m["args"].get("mask_mbi", False))  # fmt: skip
    folder = execute(opts, parent)
    nm = json.loads((folder / "manifest.json").read_text())
    kept, cut = nm["decisions_applied"], len(nm["decisions_cut"])
    return folder, kept, cut, len(labels) - len(new)


__all__ = ["RunOptions", "RunRefused", "RunSide", "apply_review", "execute", "verify_folder"]
