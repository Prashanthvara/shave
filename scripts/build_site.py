"""Build the two JSON files the page loads.

    uv run python scripts/build_site.py

Calls the same `export.build_export` that `scripts/run_pipeline.py` calls, so
there is one implementation of the ranked contract and no chance of the site
and the raw export disagreeing. Writes public/data/ranked.json (the enriched
export), public/data/method.json and public/data/addresses.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from shave import addresses, calibration, export, ingest, mapgeo, pipeline, regression, siting, site_data

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=WORCESTER)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--town-name", default="Worcester")
    parser.add_argument("--top-n", type=int, default=export.TOP_N)
    parser.add_argument("--out", default="public/data")
    args = parser.parse_args()

    started = time.perf_counter()
    parcels = ingest.load_municipality(
        args.dir, town_id=args.town_id,
        structures_path=siting.structures_path(args.town_id),
    )
    scored = pipeline.score_parcels(parcels)

    parcels = parcels.copy()
    # representative_point, not centroid: a centroid of an L-shaped or ring
    # parcel can land outside it, which puts a marker in someone else's yard.
    centroids = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = centroids.x
    parcels["lat"] = centroids.y

    assess_fy = parcels["assess_fy"].dropna()
    town = {
        "name": args.town_name,
        "town_id": args.town_id,
        "assess_fy": int(assess_fy.iloc[0]) if len(assess_fy) else None,
    }

    raw = export.build_export(scored, parcels, town=town, top_n=args.top_n)
    raw["regression"] = regression.run(scored)
    raw["calibration"] = calibration.run(scored)
    frame = mapgeo.frame_for(parcels)
    enriched = site_data.enrich(
        raw, scored,
        paths=mapgeo.paths_for(parcels, frame),
        view_box=frame.view_box,
        walls=mapgeo.walls_for(parcels, frame),
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ranked = {k: v for k, v in enriched.items() if k != "method"}
    (out / "ranked.json").write_text(
        json.dumps(ranked, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    (out / "method.json").write_text(
        json.dumps(enriched["method"], separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    # Loaded by the page only on first search, so the ranked list's first
    # paint never waits for it.
    index = addresses.build_index(
        parcels, scored, enriched["lists"], towns=[args.town_name]
    )
    (out / "addresses.json").write_text(
        json.dumps(index, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )

    for name in ("ranked.json", "method.json", "addresses.json"):
        print(f"{name:14s} {(out / name).stat().st_size / 1024:8.1f} KB", file=sys.stderr)
    print("lists: " + ", ".join(
        f"{k} {len(v)}" for k, v in enriched["lists"].items()), file=sys.stderr)
    print(f"built in {time.perf_counter() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
