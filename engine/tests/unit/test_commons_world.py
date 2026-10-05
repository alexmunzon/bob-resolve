"""PR 10: the agency-data-commons pin, the generated multi-a-b world, and its answer key."""

import tomllib
from collections import Counter
from datetime import date
from pathlib import Path

import synth_agency_data

from bob_resolve.load.commons import EXPECTED_SHA256, HELD_OUT_LABEL, ensure_multi_a_b
from bob_resolve.run import input_files, load_world
from bob_resolve.run import sha256 as file_sha256
from bob_resolve.truth.multi import build_multi_truth

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
ENGINE = Path(__file__).resolve().parents[2]
PIN = "agency-data-commons @ git+file:///Users/alexmunzon/Data%20intake/agency-data-commons@v0.2.0"
AS_OF = date(2026, 10, 1)


def test_commons_pin_resolves_and_imports() -> None:
    deps = tomllib.loads((ENGINE / "pyproject.toml").read_text())["project"]["dependencies"]
    assert PIN in deps
    lock = (ENGINE / "uv.lock").read_text()
    assert "agency-data-commons?rev=v0.2.0#a9a670fbd9ebced6f2201177d20716fb9944a4c0" in lock
    assert synth_agency_data.__version__ == "0.2.0"
    assert "agency-data-commons v0.2.0" in HELD_OUT_LABEL and "never used to tune" in HELD_OUT_LABEL


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
