"""Download one town's MassGIS Building Structures (2-D) layer.

    uv run python scripts/fetch_structures.py --town-id 348

Writes data/raw/M<town_id>_STRUCTURES/structures_poly_<town_id>.shp and its
sidecar files. data/raw is gitignored: this is regenerable source data, and
the address it comes from is `siting.STRUCTURES_URL`.

The download goes through `curl` rather than urllib. A python.org build of
Python on macOS ships without a certificate store until its "Install
Certificates" step is run, and urllib then fails every HTTPS request with
CERTIFICATE_VERIFY_FAILED. curl uses the system trust store, needs no Python
dependency, and is present on macOS and Linux.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from shave import siting


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--root", default="data/raw")
    args = parser.parse_args()

    if shutil.which("curl") is None:
        print("curl is required to download the structures layer", file=sys.stderr)
        return 1

    url = siting.structures_url(args.town_id)
    target = siting.structures_path(args.town_id, root=args.root).parent
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / "structures.zip"
        subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location",
             "--max-time", "300", "--output", str(archive_path), url],
            check=True,
        )
        size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target)
    print(f"{url}\n{size / 1e6:.1f} MB -> {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
