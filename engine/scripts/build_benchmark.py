"""Build a deterministic benchmark JSON file from immutable run folders."""

import argparse
from pathlib import Path

from bob_resolve.benchmark import write_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", type=Path, required=True, dest="runs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    write_benchmark(args.runs, args.out)


if __name__ == "__main__":
    main()
