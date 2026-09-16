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
    # The real pipeline frame also carries town_id, so the merge would make
    # town_id_x/town_id_y and the groupby below would fail. Keep scored's.
    kept = scored[scored["keep"].astype(bool)].merge(detail, on="loc_id", how="left", suffixes=("", "_parcel"))
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


#: The only cells the agent may write. `status`, `reviewer` and `reviewer_note`
#: belong to a person and are absent from this tuple on purpose: they are what
#: `promote` reads to decide whether a row may be published.
AGENT_FIELDS: tuple[str, ...] = ("candidate_occupant", "candidate_source", "evidence")


def update_research(
    path: Path | str, findings: dict[str, dict[str, str]]
) -> int:
    """Write drafted research into pending, unreviewed rows. Returns the count.

    A person's judgment outranks a re-run, so a row that is verified or
    rejected, or that anyone has initialled, is left exactly as it is even
    when a finding is supplied for it. The agent can therefore be re-run over
    the whole worksheet at any time without costing a reviewer their work.
    """
    path = Path(path)
    rows = list(_read(path).values())
    written = 0
    for row in rows:
        found = findings.get(row["loc_id"])
        if found is None:
            continue
        if (row.get("status") or "").strip().lower() != "pending":
            continue
        if (row.get("reviewer") or "").strip():
            continue
        for field in AGENT_FIELDS:
            row[field] = found.get(field, "")
        written += 1

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows([{k: row.get(k, "") for k in FIELDS} for row in rows])
    return written


def promote(
    candidates_path: Path | str, occupants_path: Path | str, today: str
) -> int:
    """Append every verified, initialled, sourced worksheet row to the occupant
    table. Validates everything first and writes nothing if any verified row is
    incomplete. Rows already in the table are skipped."""
    dt.date.fromisoformat(today)
    occupants_path = Path(occupants_path)
    existing = set(occupants.load(occupants_path))
    occupants.load.cache_clear()

    rows = list(_read(Path(candidates_path)).values())
    # A reviewer editing a CSV will type "Verified" or mistype it. Normalise
    # case and whitespace, and refuse anything that is not a known status
    # before writing a single row, so a typo is an error rather than a row
    # that silently never reaches the table.
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in STATUSES:
            raise occupants.OccupantError(
                f"worksheet row {row['loc_id']} has status {row.get('status')!r}; "
                f"expected one of {', '.join(STATUSES)}"
            )

    new_rows = []
    for row in rows:
        if (row.get("status") or "").strip().lower() != "verified" or row["loc_id"] in existing:
            continue
        where = f"worksheet row {row['loc_id']}"
        if not row.get("reviewer", "").strip():
            raise occupants.OccupantError(f"{where} is verified but has no reviewer")
        if not row.get("candidate_occupant", "").strip():
            raise occupants.OccupantError(f"{where} is verified but has no candidate_occupant")
        source = row.get("candidate_source", "").strip()
        if not source.startswith(("http://", "https://")):
            raise occupants.OccupantError(f"{where} is verified but its source is not a web address: {source!r}")
        note = f"Verified by {row['reviewer'].strip()}. Evidence: {row.get('evidence', '').strip()}"
        if row.get("reviewer_note", "").strip():
            note += f" {row['reviewer_note'].strip()}"
        new_rows.append({
            "loc_id": row["loc_id"], "occupant": row["candidate_occupant"].strip(),
            "occupant_source": source, "verified_on": today, "note": note,
        })

    if new_rows:
        with occupants_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(occupants.FIELDS))
            writer.writerows(new_rows)
    occupants.load.cache_clear()
    occupants.load(occupants_path)  # the loader's own validation, on the result
    return len(new_rows)
