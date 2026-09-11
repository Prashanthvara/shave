"""Emit the blank occupant worksheet for the top N ranked parcels.

    uv run python scripts/occupant_worksheet.py > /tmp/worksheet.csv

Fill `occupant` and `occupant_source` by hand -- Google Maps, the business's
own site, a Secretary of the Commonwealth corporate filing -- then merge the
completed rows into data/occupants.csv. The spec budgets about 90 minutes for
50 rows and calls the result non-deferrable: it is the demo.

Rules that matter more than speed:
  - If the operating business cannot be identified confidently, LEAVE THE ROW
    OUT. A blank is honest; a guess on a published list is not.
  - If the parcel is genuinely owner-occupied and the owner name IS the
    business, record it with the assessor record as the source and a note
    saying owner-occupied.
  - `occupant_source` must be a URL or a citable record, not "Google".
  - `verified_on` is the date you looked, in yyyy-mm-dd.
"""

from __future__ import annotations

import argparse
import csv
import sys

from shave import ingest, pipeline

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
COLUMNS = [
    "loc_id", "occupant", "occupant_source", "verified_on", "note",
    "_site_addr", "_city", "_owner", "_use_desc", "_sqft", "_annual_savings_usd",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=WORCESTER)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--sweet-spot", action="store_true",
                        help="rank within the sweet-spot view instead of all kept rows")
    args = parser.parse_args()

    parcels = ingest.load_municipality(args.dir, town_id=args.town_id)
    scored = pipeline.score_parcels(parcels)

    detail = parcels.drop(columns="geometry")
    merged = scored.merge(detail, on="loc_id", how="left", suffixes=("", "_parcel"))
    rows = merged[merged["keep"]]
    if args.sweet_spot:
        rows = rows[rows["sweet_spot"]]
    rows = rows.nlargest(args.top, "annual_savings_usd")

    writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows.to_dict("records"):
        writer.writerow({
            "loc_id": row["loc_id"],
            "occupant": "",
            "occupant_source": "",
            "verified_on": "",
            "note": "",
            "_site_addr": row.get("site_addr", ""),
            "_city": row.get("city", ""),
            "_owner": row.get("owner", ""),
            "_use_desc": row.get("use_desc", ""),
            "_sqft": row.get("sqft", ""),
            "_annual_savings_usd": round(float(row["annual_savings_usd"]), 2),
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
