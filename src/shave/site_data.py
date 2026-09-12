"""What the page reads, adapted from the one export contract.

`export.build_export` is the single implementation of the ranked payload. This
module does not re-derive it: it takes that payload, adds the three things the
page needs and the export has no business carrying -- the hand-resolved
occupant, a normalised sparkline series, and the method payload -- and returns
the result. A second derivation here would be a second place for the schema to
drift, which is the failure the versioned contract exists to prevent.

THE TWO LISTS ARE NEVER MERGED. The modelled-industrial magnitude runs through
a published intensity and a load factor derived from a declared shape; the
ComStock magnitude runs through a measured timeseries. Ranking them against
each other in dollars would claim a comparability the data does not support,
so each is ranked within itself and the page says why.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping

import pandas as pd

from shave import method, occupants

#: Bumped when the page's contract changes. The page refuses to render a
#: payload whose major version it does not recognise, so a stale deploy fails
#: loudly instead of drawing wrong numbers.
SITE_SCHEMA_VERSION = "1.0.0"

#: What this module adds on top of an exported row.
ADDED_ROW_FIELDS: tuple[str, ...] = (
    "occupant", "occupant_source", "window_kw", "shaveable_kw", "path",
)

#: What the page reads off every row. Everything but ADDED_ROW_FIELDS comes
#: from `export.build_export`; the test asserts all of it is present, so a
#: rename in the pipeline or the export breaks the build, not the browser.
REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "loc_id", "rank", "reason", "archetype", "source", "sqft", "avg_12mo_kw",
    "peak_kw", "peak_to_avg", "rate_class", "demand_charge_per_kw",
    "annual_savings_usd", "shaved_fraction", "confidence", "flags",
    "sweet_spot", "site_addr", "city", "owner", "use_desc",
) + ADDED_ROW_FIELDS


def window_series(row: Mapping) -> list[float]:
    """The twelve monthly billed peaks, normalised to the year's own maximum.

    The page scales this to pixels and does no other arithmetic, which is what
    keeps the drawing provably the scorer's numbers rather than a second
    opinion about them.
    """
    values = [float(v) for v in row["monthly_billed_demand_kw"]]
    top = max(values) if values else 0.0
    if top <= 0.0:
        return [0.0] * len(values)
    return [round(v / top, 4) for v in values]


def enrich(
    export_payload: dict,
    scored: pd.DataFrame,
    paths: dict[str, str] | None = None,
    view_box: str | None = None,
) -> dict:
    """The export, plus the occupant, the sparkline series and the method.

    Does not mutate its argument: the caller may still want to write the raw
    export, and a function that quietly edits its input is a trap.
    """
    payload = copy.deepcopy(export_payload)
    table = occupants.load()

    for rows in payload["lists"].values():
        for row in rows:
            resolved = table.get(row["loc_id"])
            row["occupant"] = resolved.occupant if resolved else ""
            row["occupant_source"] = resolved.occupant_source if resolved else ""
            row["window_kw"] = window_series(row)
            # The export carries twelve monthly figures; the row shows the
            # best month, which is the number the reason sentence quotes.
            row["shaveable_kw"] = max(
                float(v) for v in row["monthly_shaveable_kw"]
            )
            # Empty string, not a missing key: a parcel with no polygon still
            # belongs in the table, and the page checks truthiness once.
            row["path"] = (paths or {}).get(row["loc_id"], "")

    if view_box:
        payload["map"] = {"view_box": view_box}
    payload["site_schema_version"] = SITE_SCHEMA_VERSION
    # The export already ran the regression and carries it. Passing it through
    # rather than dropping it is the difference between a method page that
    # reports R-squared and one that says "not yet run" while the figures sit
    # in the very payload it was handed.
    payload["method"] = method.method_payload(
        scored, regression=export_payload.get("regression")
    )
    return payload
