"""Fetch and cache one measured profile per ComStock archetype Worcester needs.

Run once. Later stages read only the local cache, so the pipeline is
reproducible offline and a re-run costs nothing.

    uv run python scripts/warm_comstock_cache.py
"""

from __future__ import annotations

import sys
import time

from shave import comstock
from shave.ingest import load_municipality

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"


def main() -> int:
    parcels = load_municipality(WORCESTER, town_id=348)
    wanted = sorted(
        parcels.loc[parcels["source"] == "comstock", "archetype"].dropna().unique()
    )
    print(f"{len(wanted)} ComStock archetypes in Worcester: {', '.join(wanted)}\n")

    failures = []
    for name in wanted:
        started = time.perf_counter()
        try:
            a = comstock.build_archetype(name, sqft=10_000.0)
            peak = a.monthly_peaks().max()
            # cohort_size/widened come from select_representative and mark
            # shapes resting on a thin sample (e.g. Hospital, 2 buildings in
            # Worcester County) -- surfaced here rather than only living in
            # the cached parquet, so whoever runs this can see it directly.
            flag = "  ** WIDENED **" if a.widened else ""
            print(f"  {name:26s} bldg {a.profile.bldg_id:>7}  "
                  f"{a.profile.sqft:>9,.0f} sqft  peak {peak:7.1f} kW  "
                  f"cohort {a.cohort_size:>4}{flag}  "
                  f"{time.perf_counter() - started:5.1f}s")
        except Exception as exc:  # noqa: BLE001 - report every failure, fail at the end
            failures.append((name, exc))
            print(f"  {name:26s} FAILED: {exc}")

    if failures:
        print(f"\n{len(failures)} archetype(s) failed", file=sys.stderr)
        return 1
    print(f"\ncache warm: {len(wanted)} archetypes in {comstock.CACHE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
