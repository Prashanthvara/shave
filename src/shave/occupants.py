"""Owner of record is not the operating business.

MassGIS L3 carries the assessor's owner, which for leased commercial property
is a realty trust or an LLC: `RK WORCESTER CROSSING LLC`, `440 LINCOLN STREET
HOLDING`. Measured on the current top 50, 25 of 50 are of that shape. A ranked
list whose first row names a holding company is correct and useless -- the
spec's success criterion is a real, named, checkable business.

There is no public dataset that maps a Massachusetts parcel to its operating
tenant. This is hand-resolved, one row at a time, and the CSV is committed so
the work is visible and auditable rather than living in someone's notes.

Every row carries a source URL and a verification date. An unsourced name is a
guess, and a guess on the top row is the first thing a domain expert checks.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

OCCUPANTS_PATH = Path(__file__).resolve().parents[2] / "data" / "occupants.csv"

FIELDS = ("loc_id", "occupant", "occupant_source", "verified_on", "note")


class OccupantError(ValueError):
    """The occupant table is malformed or internally inconsistent."""


@dataclass(frozen=True)
class Occupant:
    loc_id: str
    occupant: str
    occupant_source: str
    verified_on: str
    note: str = ""


def _require(value: str, field: str, where: str) -> str:
    text = (value or "").strip()
    if not text:
        raise OccupantError(f"{where} {field} is blank")
    return text


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict[str, Occupant]:
    """Read and validate the occupant table. Cached; call `load.cache_clear()`."""
    src = Path(path) if path is not None else OCCUPANTS_PATH
    if not src.exists():
        raise OccupantError(f"occupant table not found at {src}")

    rows: dict[str, Occupant] = {}
    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise OccupantError(f"{src} is missing columns {sorted(missing)}")
        for lineno, raw in enumerate(reader, start=2):
            where = f"{src.name}:{lineno}"
            loc_id = _require(raw.get("loc_id", ""), "loc_id", where)
            if loc_id in rows:
                raise OccupantError(f"{where} duplicate loc_id {loc_id!r}")
            occupant = _require(raw.get("occupant", ""), "occupant", where)
            source = _require(raw.get("occupant_source", ""), "occupant_source", where)
            verified = _require(raw.get("verified_on", ""), "verified_on", where)
            try:
                dt.date.fromisoformat(verified)
            except ValueError as exc:
                raise OccupantError(
                    f"{where} verified_on must be ISO yyyy-mm-dd, got {verified!r}"
                ) from exc
            rows[loc_id] = Occupant(
                loc_id=loc_id,
                occupant=occupant,
                occupant_source=source,
                verified_on=verified,
                note=(raw.get("note") or "").strip(),
            )
    return rows


def attach(scored: pd.DataFrame, path: Path | None = None) -> pd.DataFrame:
    """Add `occupant` and `occupant_source`. Unresolved rows get empty strings.

    Empty rather than the owner name: showing the holding company in a column
    labelled "occupant" would assert something the table does not know.
    """
    table = load(path)
    out = scored.copy()
    out["occupant"] = out["loc_id"].map(lambda k: table[k].occupant if k in table else "")
    out["occupant_source"] = out["loc_id"].map(
        lambda k: table[k].occupant_source if k in table else ""
    )
    return out


def coverage(
    scored: pd.DataFrame, top_n: int = 50, path: Path | None = None
) -> dict[str, int]:
    """How much of the head of the ranking is resolved. For the method page."""
    table = load(path)
    kept = scored[scored["keep"]] if "keep" in scored else scored
    top = kept.nlargest(top_n, "annual_savings_usd")
    return {
        "resolved_total": len(table),
        "top_n": int(len(top)),
        "top_n_resolved": int(top["loc_id"].isin(table).sum()),
    }
