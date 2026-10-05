from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture
def snapshot_dir() -> Path:
    return FIXTURES / "agency-a-snapshot"


@pytest.fixture
def hard_cases_dir() -> Path:
    return FIXTURES / "hard-cases"


@pytest.fixture
def derived_dir() -> Path:
    return FIXTURES / "agency-a-derived"
