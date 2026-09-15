"""Move verified worksheet rows into data/occupants.csv.

    uv run python scripts/promote_occupants.py

Only rows a person marked `verified`, with a reviewer and a web source.
"""

from __future__ import annotations

import datetime as dt
import sys

from shave import occupant_worksheet, occupants


def main() -> int:
    added = occupant_worksheet.promote(
        occupant_worksheet.CANDIDATES_PATH, occupants.OCCUPANTS_PATH, today=dt.date.today().isoformat()
    )
    print(f"promoted {added} verified row(s) into {occupants.OCCUPANTS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
