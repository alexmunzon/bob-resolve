from typer.testing import CliRunner

from bob_resolve import __version__
from bob_resolve.cli import app


def test_version_prints_the_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__
