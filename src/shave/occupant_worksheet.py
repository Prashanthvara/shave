"""The occupant worksheet: which rows need an operating business, and the
research drafted for each, waiting for a person to verify it.

The assessor records the owner of record, which for leased commercial property
is a realty trust or a holding company. The operating business is what a
reader checks first, and there is no public dataset that maps one to the
other. So candidates are drafted -- one name, one source, one sentence of
evidence -- and nothing reaches data/occupants.csv until a person marks the
row verified and initials it.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pandas as pd

from shave import occupants, towns

CANDIDATES_PATH = Path("data/occupant_candidates.csv")

FIELDS: tuple[str, ...] = (
    "loc_id", "town", "list", "rank", "site_addr", "owner", "use_desc", "sqft",
    "annual_savings_usd",
    # research, drafted by the agent
    "candidate_occupant", "candidate_source", "evidence",
    # verification, by a person
    "status", "reviewer", "reviewer_note",
)
RESEARCH_FIELDS: tuple[str, ...] = (
    "candidate_occupant", "candidate_source", "evidence", "status", "reviewer", "reviewer_note",
)
STATUSES: tuple[str, ...] = ("pending", "verified", "rejected")


def select_rows(
    scored: pd.DataFrame, parcels: pd.DataFrame, existing: set[str], top_n: int = 50
) -> pd.DataFrame:
    """The top `top_n` kept rows by dollars across every town, plus each town's
    rank-1 row on each list, less the rows already resolved.

    Rank is within town and list, which is what the page shows.
    """
    detail = pd.DataFrame(parcels)[["loc_id", "town_id", "site_addr", "owner", "use_desc", "sqft"]]
    kept = scored[scored["keep"].astype(bool)].merge(detail, on="loc_id", how="left")
    kept = kept.assign(
        rank=kept.groupby(["town_id", "source"])["annual_savings_usd"]
        .rank(ascending=False, method="first").astype(int)
    )
    top = kept.nlargest(top_n, "annual_savings_usd")
    heads = kept[kept["rank"] == 1]
    rows = (
        pd.concat([top, heads])
        .drop_duplicates("loc_id")
        .loc[lambda f: ~f["loc_id"].isin(existing)]
        .sort_values("annual_savings_usd", ascending=False)
    )
    out = pd.DataFrame({
        "loc_id": rows["loc_id"].astype(str),
        "town": [towns.by_id(int(t)).name for t in rows["town_id"]],
        "list": rows["source"].astype(str),
        "rank": rows["rank"].astype(int),
        "site_addr": rows["site_addr"].fillna("").astype(str),
        "owner": rows["owner"].fillna("").astype(str),
        "use_desc": rows["use_desc"].fillna("").astype(str),
        "sqft": rows["sqft"].round(0),
        "annual_savings_usd": rows["annual_savings_usd"].round(0),
    })
    for field in RESEARCH_FIELDS:
        out[field] = "pending" if field == "status" else ""
    return out.reset_index(drop=True)[list(FIELDS)]


def _read(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["loc_id"]: row for row in csv.DictReader(fh)}


def write_worksheet(rows: pd.DataFrame, path: Path | str = CANDIDATES_PATH) -> int:
    """Write the worksheet, keeping every research cell already in the file."""
    path = Path(path)
    previous = _read(path)
    records = rows.to_dict("records")
    for record in records:
        old = previous.get(str(record["loc_id"]))
        if old:
            for field in RESEARCH_FIELDS:
                record[field] = old.get(field, record[field])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(records)
    return len(records)
