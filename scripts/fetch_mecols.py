"""Download National Grid's MECOLS class average load shapes.

    uv run python scripts/fetch_mecols.py

Writes data/raw/mecols/MECOLS.xlsx (gitignored). Downloads through curl for the
same reason as scripts/fetch_structures.py: a python.org Python on macOS may
have no certificate store, and curl uses the system's.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from shave import calibration
from shave.assumptions import MECOLS_URL


def main() -> int:
    if shutil.which("curl") is None:
        print("curl is required", file=sys.stderr)
        return 1
    calibration.MECOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "120",
         "--output", str(calibration.MECOLS_PATH), MECOLS_URL],
        check=True,
    )
    size = calibration.MECOLS_PATH.stat().st_size
    print(f"{MECOLS_URL}\n{size:,} bytes -> {calibration.MECOLS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
