"""Build everything the page loads, for every covered town.

    uv run python scripts/build_site.py

Writes, under public/data:
  index.json                     the towns, their counts, the default
  towns/<slug>/ranked.json       one enriched export per town, in its own map frame
  method.json                    one method payload over all towns
  addresses.json                 one address index over all towns
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from shave import (
    addresses, calibration, ingest, method, pipeline, regression, siting, site_build, towns,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"  {str(path):48s} {path.stat().st_size / 1024:8.1f} KB", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="public/data")
    args = parser.parse_args()
    out = Path(args.out)
    started = time.perf_counter()

    payloads, all_parcels, all_scored = [], [], []
    for town in towns.TOWNS:
        parcels = ingest.load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        scored = pipeline.score_parcels(parcels)
        payload = site_build.town_payload(town, parcels, scored)
        _write(site_build.town_data_path(out, town.slug), payload)
        payloads.append(payload)
        all_parcels.append(parcels)
        all_scored.append(scored)

    parcels = pd.concat(all_parcels, ignore_index=True)
    scored = pd.concat(all_scored, ignore_index=True)
    index = site_build.index_payload(payloads)
    method_payload = method.method_payload(
        scored,
        regression=regression.run(scored),
        calibration=calibration.run(scored),
        towns=index["towns"],
    )
    lists = {
        source: [row for p in payloads for row in p["lists"][source]]
        for source in ("comstock", "modeled")
    }
    address_index = addresses.build_index(
        parcels, scored, lists, towns=[t.name for t in towns.TOWNS]
    )

    _write(out / "index.json", index)
    _write(out / "method.json", method_payload)
    _write(out / "addresses.json", address_index)
    print(f"built {len(payloads)} towns in {time.perf_counter() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
