"""Download and unzip one covered town's MassGIS L3 parcel extract.

    uv run python scripts/fetch_l3.py --town-id 95
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from shave import towns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-id", type=int, required=True)
    args = parser.parse_args()
    town = towns.by_id(args.town_id)
    target = Path(town.l3_dir).parent
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / town.l3_zip
        subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location", "--retry", "3",
             "--max-time", "600", "--output", str(archive), town.l3_url],
            check=True,
        )
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    print(f"{town.l3_url} -> {town.l3_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
