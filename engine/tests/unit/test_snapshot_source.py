import hashlib
import re
from pathlib import Path

SNAPSHOT_FILES = {
    "clients.csv",
    "households.csv",
    "policies.csv",
    "enrollment_export.csv",
    "ground_truth.json",
}


def test_source_md_hashes_match_the_files(snapshot_dir: Path) -> None:
    source = (snapshot_dir / "SOURCE.md").read_text()
    assert "9064b4e5fa45e54c9ddff0d180c901d51ca2a439" in source
    listed = dict(re.findall(r"\| `([\w.]+)` \| `([0-9a-f]{64})` \|", source))
    assert set(listed) == SNAPSHOT_FILES
    for name, expected in listed.items():
        assert hashlib.sha256((snapshot_dir / name).read_bytes()).hexdigest() == expected, name
