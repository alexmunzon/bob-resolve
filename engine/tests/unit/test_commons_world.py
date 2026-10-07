"""PR 10: the agency-data-commons pin, the generated multi-a-b world, and its answer key."""

import tomllib
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import synth_agency_data

from bob_resolve.golden import GoldenPerson, Resolution
from bob_resolve.load.commons import EXPECTED_SHA256, TWO_AGENCY_LABEL, ensure_multi_a_b
from bob_resolve.mergelog import MergeLogEntry
from bob_resolve.run import held_out_report, input_files, load_world
from bob_resolve.run import sha256 as file_sha256
from bob_resolve.score.rules import ScoredPair
from bob_resolve.truth import AnswerKey
from bob_resolve.truth.multi import MultiTruth, build_multi_truth

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
ENGINE = Path(__file__).resolve().parents[2]
PIN = "agency-data-commons @ git+https://github.com/alexmunzon/agency-data-commons@v0.2.0"
AS_OF = date(2026, 10, 1)


def test_commons_pin_resolves_and_imports() -> None:
    deps = tomllib.loads((ENGINE / "pyproject.toml").read_text())["project"]["dependencies"]
    assert PIN in deps
    lock = (ENGINE / "uv.lock").read_text()
    assert "agency-data-commons?rev=v0.2.0#a9a670fbd9ebced6f2201177d20716fb9944a4c0" in lock
    assert synth_agency_data.__version__ == "0.2.0"
    assert "agency-data-commons v0.2.0" in TWO_AGENCY_LABEL and TWO_AGENCY_LABEL.startswith("seen")
    assert "never used to tune" not in TWO_AGENCY_LABEL and "held-out" not in TWO_AGENCY_LABEL
    assert "tuned on it" in TWO_AGENCY_LABEL


def test_generated_world_matches_commons_committed_hashes() -> None:
    folder = ensure_multi_a_b(FIXTURES)
    assert folder == FIXTURES / "generated" / "multi-a-b"
    for rel, digest in EXPECTED_SHA256.items():
        assert file_sha256(folder / rel) == digest, rel
    assert "fixtures/generated/" in (FIXTURES.parent / ".gitignore").read_text()


def test_answer_key_counts_match_the_commons_readme() -> None:
    t = build_multi_truth(FIXTURES, as_of=AS_OF)
    assert len(t.commons_pairs) == 320
    assert Counter(s for s in t.pair_scope.values()) == {"cross": 312, "within_b": 8}
    assert t.commons_clusters == 3252
    assert len(t.must_not_merge) == 164
    assert Counter(m.defect_type for m in t.must_not_merge) == {
        "shared_household_contact": 42,
        "child_on_parent_policy": 36,
        "father_son_same_name": 36,
        "twin_lookalike": 32,
        "name_dob_lookalike": 18,
    }
    # Every client id of both agencies is in exactly one person; enrollment rows join by policy.
    assert len(t.key.clusters) == 3252
    records = {r for rs in t.key.clusters.values() for r in rs}
    world, _ = load_world(input_files(FIXTURES, "multi-a-b"), AS_OF)
    ids = [r.record_id for r in world]
    assert len(ids) == len(set(ids))  # no id collision between the agencies
    assert records | t.key.unresolved_ids == set(ids)
    assert not records & t.key.unresolved_ids
    for a, b in t.commons_pairs:
        assert t.key.person_of[a] == t.key.person_of[b]
    for m in t.must_not_merge:
        assert t.key.person_of[m.a] != t.key.person_of[m.b]


def test_run_needs_exactly_one_of_world_or_enrollment(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from bob_resolve.cli import app

    base = ["run", "--out", str(tmp_path), "--run-id", "x"]
    both = CliRunner().invoke(app, [*base, "--world", "multi-a-b", "--enrollment", "snapshot"])
    neither = CliRunner().invoke(app, base)
    assert both.exit_code == 2 and neither.exit_code == 2
    assert not (tmp_path / "x").exists()


def _held_out_case() -> dict[str, Any]:
    """PR 18: four commons pairs. A1-A2 auto-merged, G1-G2 gray with a same-person suggestion
    that a reviewer confirmed (a human merge, not an automatic one), C1-C2 auto-matched but cut
    by a cluster conflict, M1-M2 rejected."""
    pairs = {("crm:A1", "crm:A2"): ("maiden_name",), ("crm:G1", "crm:G2"): ("maiden_name",),
             ("crm:C1", "crm:C2"): (), ("crm:M1", "crm:M2"): ()}  # fmt: skip
    key = AnswerKey(clusters={f"P{x}": (f"crm:{x}1", f"crm:{x}2") for x in "AGCM"})
    truth = MultiTruth.model_construct(key=key, commons_clusters=4, commons_pairs=pairs,
                                       pair_scope={}, must_not_merge=())  # fmt: skip
    decision = {"A": "AUTO_MATCH", "G": "GRAY", "C": "AUTO_MATCH", "M": "AUTO_REJECT"}
    scored = [ScoredPair.model_construct(a=a, b=b, decision=decision[a[4]],
                                         suggestion="same_person" if a[4] == "G" else None)
              for a, b in pairs]  # fmt: skip
    merged = {"A": "rules", "G": "review"}
    log = tuple(MergeLogEntry.model_construct(action="merge", a=f"crm:{x}1", b=f"crm:{x}2",
                                              tier=tier) for x, tier in merged.items())  # fmt: skip
    people = tuple(GoldenPerson.model_construct(person_id=f"g{x}", record_ids=(f"crm:{x}1",
                                                f"crm:{x}2")) for x in merged)  # fmt: skip
    res = Resolution.model_construct(people=people, log=log)
    missed = (("crm:C1", "crm:C2"), ("crm:M1", "crm:M2"))
    return held_out_report(truth, res, scored, missed)


def test_held_out_automatic_recall_excludes_suggestions_and_human_merges() -> None:
    ho = _held_out_case()
    assert ho["commons_pairs"] == {
        "pairs": 4, "found_automatically": 1, "automatic_recall": 0.25,
        "suggested_same_person": 1, "recall_if_suggestions_confirmed": 0.5, "one_person": 2,
        "missed_examples": [["crm:C1", "crm:C2"], ["crm:M1", "crm:M2"]],
    }  # fmt: skip
    maiden = ho["recall_by_injector"]["maiden_name"]
    assert (maiden["automatic_recall"], maiden["recall_if_suggestions_confirmed"]) == (0.5, 1.0)
    assert ho["recall_by_injector"]["none"]["automatic_recall"] == 0.0


def test_held_out_pair_blocks_have_no_plain_recall_or_found_key() -> None:
    ho = _held_out_case()
    for block in [ho["commons_pairs"], *ho["recall_by_injector"].values()]:
        assert not {"recall", "found"} & set(block), block
