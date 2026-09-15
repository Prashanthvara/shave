"""Fetch and cache one measured profile per ComStock archetype, per covered town.

Run once per new town. Later stages read only the local cache, so the pipeline
is reproducible offline and a re-run costs nothing.

    uv run python scripts/warm_comstock_cache.py
"""

from __future__ import annotations

import sys
import time

from shave import comstock, siting, towns
from shave.ingest import load_municipality


def main() -> int:
    failures = []
    for town in towns.TOWNS:
        parcels = load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        wanted = sorted(
            parcels.loc[parcels["source"] == "comstock", "archetype"].dropna().unique()
        )
        print(f"\n{town.name} ({town.county_gisjoin}): {len(wanted)} ComStock archetypes")
        for name in wanted:
            started = time.perf_counter()
            try:
                a = comstock.build_archetype(
                    name, sqft=10_000.0, county_gisjoin=town.county_gisjoin
                )
                flag = "  ** WIDENED **" if a.widened else ""
                print(f"  {name:26s} bldg {a.profile.bldg_id:>7}  "
                      f"cohort {a.cohort_size:>4}{flag}  {time.perf_counter() - started:5.1f}s")
            except Exception as exc:  # noqa: BLE001 - report every failure, fail at the end
                failures.append((town.name, name, exc))
                print(f"  {name:26s} FAILED: {exc}")
    if failures:
        print(f"\n{len(failures)} archetype(s) failed", file=sys.stderr)
        return 1
    print(f"\ncache warm in {comstock.CACHE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
