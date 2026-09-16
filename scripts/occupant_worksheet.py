"""Write the occupant worksheet for every covered town.

    uv run python scripts/occupant_worksheet.py

Rows: the top 50 kept parcels by dollars across all towns, plus each town's
rank-1 row on each list, less anything already in data/occupants.csv.
Research already in data/occupant_candidates.csv is kept on every re-run.

Rules that matter more than speed:
  - If the operating business cannot be identified confidently, leave the
    candidate blank and say in `evidence` what was checked. A blank is honest;
    a guess on a published list is not.
  - `candidate_source` is one URL a reader can open, never a search page.
  - Only a person sets `status` to verified or rejected, and initials `reviewer`.
"""

from __future__ import annotations

import sys

import pandas as pd

from shave import ingest, occupant_worksheet, occupants, pipeline, siting, towns


def main() -> int:
    all_parcels, all_scored = [], []
    for town in towns.TOWNS:
        parcels = ingest.load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        all_parcels.append(pd.DataFrame(parcels.drop(columns=["geometry", "wall_segment"])))
        all_scored.append(pipeline.score_parcels(parcels))
    parcels = pd.concat(all_parcels, ignore_index=True)
    scored = pd.concat(all_scored, ignore_index=True)

    rows = occupant_worksheet.select_rows(scored, parcels, existing=set(occupants.load()))
    n = occupant_worksheet.write_worksheet(rows)
    print(f"{n} rows -> {occupant_worksheet.CANDIDATES_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
