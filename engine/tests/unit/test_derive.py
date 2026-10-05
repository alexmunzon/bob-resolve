import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bob_resolve.cli import app
from bob_resolve.load import read_crm, read_enrollment
from bob_resolve.truth import build_snapshot_answer_key
from bob_resolve.truth.derive import DERIVED_DEFECTS, DeriveResult, derive_clean_enrollment

AS_OF = date(2026, 10, 5)


@pytest.fixture(scope="module")
def derived(tmp_path_factory: pytest.TempPathFactory) -> tuple[DeriveResult, Path]:
    snapshot = Path(__file__).resolve().parents[3] / "fixtures" / "agency-a-snapshot"
    out = tmp_path_factory.mktemp("derived")
    return derive_clean_enrollment(snapshot, out), out


def _lines(path: Path) -> list[bytes]:
    return path.read_bytes().split(b"\n")


def test_regeneration_is_byte_identical_to_the_committed_file(
    derived: tuple[DeriveResult, Path], derived_dir: Path
) -> None:
    _, out = derived
    committed = derived_dir / "enrollment_clean.csv"
    assert (out / "enrollment_clean.csv").read_bytes() == committed.read_bytes()


def test_cli_writes_the_same_file(snapshot_dir: Path, derived_dir: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["fixtures", "derive", "--snapshot", str(snapshot_dir), "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "rows changed" in result.output
    committed = (derived_dir / "enrollment_clean.csv").read_bytes()
    assert (tmp_path / "enrollment_clean.csv").read_bytes() == committed


def test_changed_rows_each_undo_exactly_one_defect(
    derived: tuple[DeriveResult, Path], snapshot_dir: Path
) -> None:
    result, out = derived
    defects = json.loads((snapshot_dir / "ground_truth.json").read_text())["defects"]
    by_client = {
        d["record_key"]["client_id"]: d for d in defects if d["defect_type"] in DERIVED_DEFECTS
    }
    old = _lines(snapshot_dir / "enrollment_export.csv")
    new = _lines(out / "enrollment_clean.csv")
    assert len(old) == len(new) and old[0] == new[0] and old[-1] == new[-1] == b""
    changed = {c.row_number: c for c in result.changes}
    for i, (a, b) in enumerate(zip(old[1:-1], new[1:-1], strict=True), start=1):
        if i not in changed:
            assert a == b, f"row {i} changed without a defect"
            continue
        c = changed[i]
        d = by_client[c.client_id]
        assert d["defect_type"] == c.defect_type
        before, after = a.decode().split(";"), b.decode().split(";")
        diff = [k for k in range(len(before)) if before[k] != after[k]]
        assert len(diff) == 1, f"row {i} changed {len(diff)} fields"
        frm = d["injected_values"]["from"]
        if d["injected_values"]["field"] == "dob":
            y, m, dd = frm.split("-")
            frm = f"{m}/{dd}/{y[2:]}"
        assert after[diff[0]] == frm


def test_reachable_defect_counts(derived: tuple[DeriveResult, Path]) -> None:
    result, _ = derived
    assert result.rows_changed == {
        "nickname": 46,
        "name_typo": 38,
        "dob_transposition": 18,
        "dob_month_day_swap": 10,
    }
    assert len(result.changes) == 112
    assert result.defects_total == 130
    assert result.defects_with_rows == 97
    assert len(result.defects_without_rows) == 33


def test_nickname_shows_on_crm_and_original_on_derived(
    derived: tuple[DeriveResult, Path], snapshot_dir: Path, derived_dir: Path
) -> None:
    result, _ = derived
    crm = read_crm(snapshot_dir / "clients.csv", as_of=AS_OF)
    enr = read_enrollment(derived_dir / "enrollment_clean.csv", as_of=AS_OF)
    nick = next(c for c in result.changes if c.defect_type == "nickname")
    crm_first = crm.filter(crm["client_id"] == nick.client_id)["first_name"].item()
    enr_first = enr.filter(enr["row_number"] == nick.row_number)["first_name"].item()
    assert crm_first == nick.was and enr_first == nick.now and crm_first != enr_first
    assert enr["source_file"][0] == "agency-a-derived/enrollment_clean.csv"


def test_answer_key_pairs_are_the_same_on_the_derived_side(
    snapshot_dir: Path, derived_dir: Path
) -> None:
    snap = build_snapshot_answer_key(snapshot_dir, as_of=AS_OF)
    clean = build_snapshot_answer_key(
        snapshot_dir, derived_dir / "enrollment_clean.csv", as_of=AS_OF
    )
    assert clean.pairs == snap.pairs and len(clean.pairs) == 2167
    assert clean.unresolved == snap.unresolved


def test_source_md_reports_hashes_and_counts(derived_dir: Path, snapshot_dir: Path) -> None:
    source = (derived_dir / "SOURCE.md").read_text()
    assert "derived from the answer key" in source
    assert "bob-resolve fixtures derive" in source
    for name in ("enrollment_export.csv", "ground_truth.json", "policies.csv"):
        assert hashlib.sha256((snapshot_dir / name).read_bytes()).hexdigest() in source
    out = hashlib.sha256((derived_dir / "enrollment_clean.csv").read_bytes()).hexdigest()
    assert out in source
    assert chr(0x2014) not in source
