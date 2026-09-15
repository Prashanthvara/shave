"""The municipalities this tool covers, and why each qualifies.

A town qualifies only if National Grid (Massachusetts Electric) serves it: the
G-2/G-3 tariff, the rate-class test and every dollar figure are National
Grid's. The design doc named Worcester, New Bedford and Chicopee, and its own
"confirm none is a municipal light plant" step fails for two of them:
MassGIS's electricity-provider layer (Department of Public Utilities, October
2025) lists New Bedford as Eversource and Chicopee as a municipal light plant.
Fall River and Lowell replace them -- a harbour mill city and a mill city,
both National Grid -- and `data/town_utilities.csv` is the checkable record.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

L3_BASE_URL = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
    "shapefiles/l3parcels"
)
NATIONAL_GRID = "National Grid (Massachusetts Electric)"
UTILITIES_PATH = Path(__file__).resolve().parents[2] / "data" / "town_utilities.csv"


@dataclass(frozen=True)
class Town:
    town_id: int
    name: str
    slug: str
    #: NHGIS GISJOIN of the county, the partition ComStock metadata uses.
    county_gisjoin: str
    #: MassGIS's file name for the L3 extract.
    l3_zip: str
    #: Where that extract unzips.
    l3_dir: str

    @property
    def l3_url(self) -> str:
        return f"{L3_BASE_URL}/{self.l3_zip}"


TOWNS: tuple[Town, ...] = (
    Town(348, "Worcester", "worcester", "G2500270",
         "L3_SHP_M348_WORCESTER.zip", "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"),
    Town(95, "Fall River", "fall-river", "G2500050",
         "L3_SHP_M095_FALLRIVER.zip", "data/raw/M095_FALLRIVER/L3_SHP_M095_FallRiver"),
    Town(160, "Lowell", "lowell", "G2500170",
         "L3_SHP_M160_LOWELL.zip", "data/raw/M160_LOWELL/L3_SHP_M160_Lowell"),
)

DEFAULT_TOWN_ID = 348


def by_id(town_id) -> Town:
    tid = int(town_id)
    for town in TOWNS:
        if town.town_id == tid:
            return town
    raise KeyError(f"town {tid} is not covered; covered: {[t.town_id for t in TOWNS]}")


def county_for(town_id) -> str:
    """ComStock county for a parcel's town. A parcel built without a town --
    the synthetic test frames -- takes Worcester's, which is what every
    parcel used before towns existed."""
    if town_id is None or pd.isna(town_id):
        return by_id(DEFAULT_TOWN_ID).county_gisjoin
    return by_id(town_id).county_gisjoin


def utilities(path: Path | str = UTILITIES_PATH) -> dict[int, str]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return {int(row["town_id"]): row["elec"] for row in csv.DictReader(fh)}
