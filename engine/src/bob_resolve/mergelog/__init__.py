"""Append-only merge log (SPEC 6 step 8): one JSON line per merge, split, or correction."""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

Action = Literal["merge", "split", "correction"]


class MergeLogEntry(BaseModel):
    """One decision. `time` comes from the caller's clock, so tests can freeze it."""

    model_config = ConfigDict(frozen=True)

    action: Action
    a: str
    b: str
    tier: str
    score: float | None
    rule_ids: tuple[str, ...]
    run_id: str
    time: str
    corrects_line: int | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _correction_names_its_line(self) -> Self:
        if (self.action == "correction") != (self.corrects_line is not None):
            raise ValueError("a correction, and only a correction, names the line it corrects")
        return self


def append_entries(path: Path, entries: Iterable[MergeLogEntry]) -> int:
    """Append lines; never truncate or rewrite. A log with a cut-off last line is refused,
    because appending to it would glue two records into one broken line."""
    if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n"):
        raise ValueError(f"{path.name} does not end with a newline; refusing to append")
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e.model_dump(mode="json"), sort_keys=True) + "\n")
            n += 1
    return n


def read_entries(path: Path) -> list[MergeLogEntry]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [MergeLogEntry.model_validate_json(line) for line in lines]


__all__ = ["Action", "MergeLogEntry", "append_entries", "read_entries"]
