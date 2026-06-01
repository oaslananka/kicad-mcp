"""Workflow security wrapper around zizmor."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-severity",
        default="high",
        choices=["unknown", "informational", "low", "medium", "high"],
    )
    args = parser.parse_args()

    binary = shutil.which("zizmor")
    if binary is None:
        print(
            "zizmor is required for workflow security checks. Install with "
            "`uv tool install zizmor` or see https://docs.zizmor.sh/installation/.",
            file=sys.stderr,
        )
        raise SystemExit(127)

    command = [
        binary,
        "--offline",
        "--min-severity",
        args.min_severity,
        str(REPO_ROOT / ".github" / "workflows"),
    ]
    raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
