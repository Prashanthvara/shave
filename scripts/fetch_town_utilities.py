"""Snapshot MassGIS's electricity provider for every municipality.

    uv run python scripts/fetch_town_utilities.py

Writes data/town_utilities.csv, which IS committed: it is the evidence that
each covered town is National Grid territory.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys

from shave import towns

QUERY = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "ElectricityProviders/FeatureServer/0/query"
    "?where=1%3D1&outFields=TOWN,TOWN_ID,ELEC&returnGeometry=false&f=json"
)


def main() -> int:
    raw = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "60", QUERY],
        check=True, capture_output=True,
    ).stdout
    features = json.loads(raw)["features"]
    rows = sorted(
        ({"town_id": f["attributes"]["TOWN_ID"], "town": f["attributes"]["TOWN"],
          "elec": f["attributes"]["ELEC"]} for f in features),
        key=lambda r: r["town_id"],
    )
    fetched = dt.date.today().isoformat()
    with towns.UTILITIES_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["town_id", "town", "elec", "fetched_on"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "fetched_on": fetched})
    print(f"{len(rows)} municipalities -> {towns.UTILITIES_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
