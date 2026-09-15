"""Fill monthly energy into every cached ComStock profile, identity preserved.

    uv run python scripts/refresh_comstock_energy.py

Re-reads each cached building's own timeseries from S3 (about 1.3 s each) and
refuses to overwrite any file whose billed shape would change.
"""

from __future__ import annotations

import sys
import time

from shave import comstock


def main() -> int:
    paths = sorted(comstock.CACHE_DIR.glob("*.parquet"))
    if not paths:
        print(f"no cached profiles in {comstock.CACHE_DIR}", file=sys.stderr)
        return 1
    for path in paths:
        started = time.perf_counter()
        prof = comstock.refresh_cached_profile(path)
        print(f"  {path.name:40s} bldg {prof.bldg_id:>7}  "
              f"annual {prof.monthly_energy_kwh.sum():>12,.0f} kWh  "
              f"{time.perf_counter() - started:4.1f}s")
    print(f"refreshed {len(paths)} profiles", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
