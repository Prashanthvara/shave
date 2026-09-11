"""Ingest, score, export. The one command.

    uv run python scripts/run_pipeline.py
    uv run python scripts/run_pipeline.py --dir data/raw/... --town-id 348 --out public/ranked.json
"""

from __future__ import annotations

import argparse
import sys
import time

from shave import export, ingest, pipeline

DEFAULT_DIR = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
DEFAULT_TOWN_ID = 348
DEFAULT_NAME = "Worcester"
DEFAULT_OUT = "public/ranked.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DEFAULT_DIR, help="MassGIS L3 extract directory")
    ap.add_argument("--town-id", type=int, default=DEFAULT_TOWN_ID)
    ap.add_argument("--town-name", default=DEFAULT_NAME)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--top-n", type=int, default=export.TOP_N)
    args = ap.parse_args(argv)

    started = time.perf_counter()

    parcels = ingest.load_municipality(args.dir, args.town_id)
    print(f"ingested {len(parcels):,} scoreable parcels", file=sys.stderr)

    scored = pipeline.score_parcels(parcels)
    print(f"scored {int(scored['unscored_reason'].isna().sum()):,}, "
          f"kept {int(scored['keep'].astype(bool).sum()):,}", file=sys.stderr)

    # Centroids for the map. Projected coordinates go to WGS84 here and
    # nowhere else, so nothing downstream has to know about EPSG:26986.
    parcels = parcels.copy()
    centroids = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = centroids.x
    parcels["lat"] = centroids.y

    assess_fy = parcels["assess_fy"].dropna()
    town = {
        "name": args.town_name,
        "town_id": args.town_id,
        "assess_fy": int(assess_fy.iloc[0]) if len(assess_fy) else None,
    }

    payload = export.build_export(scored, parcels, town=town, top_n=args.top_n)
    path = export.write_export(payload, args.out)

    elapsed = time.perf_counter() - started
    size_kb = path.stat().st_size / 1024
    print(f"wrote {path} ({size_kb:,.0f} KB) in {elapsed:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
