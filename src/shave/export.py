"""The versioned contract between the Python half and whatever renders it.

One file, one schema version. A stale deploy against a changed schema fails
loudly here rather than rendering wrong numbers quietly.

Two lists, never merged. The modelled-industrial magnitude runs through a
published intensity and a derived load factor; ComStock's runs through a
measured timeseries. Ranking them against each other in dollars would claim a
comparability the data does not support, so each is ranked within itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from shave.assumptions import published_rows

#: Bump the MINOR for an added field, the MAJOR for a removed or retyped one.
#: `docs/ranked-json-schema.md` is the written contract; change both together.
SCHEMA_VERSION = "1.1.0"

#: Rows per list. Cloudflare caps a Pages asset at 25 MiB and the page has to
#: render in under three seconds on a cold load; 250 rows per list keeps the
#: payload in the hundreds of kilobytes with room for geometry later.
TOP_N = 250

#: Hard ceiling, well under Cloudflare's 25 MiB, checked at write time.
MAX_BYTES = 5 * 1024 * 1024

#: Columns lifted from the parcel frame onto every exported row.
PARCEL_FIELDS = (
    "prop_id", "site_addr", "city", "zip", "owner", "use_code", "use_desc",
    "icp_sector", "assess_fy", "confidence", "confidence_reasons",
    "lon", "lat",
)

_SOURCE_PHRASE = {
    "comstock": (
        "measured, from the NREL ComStock building most typical of its type in "
        "Worcester County by peak intensity"
    ),
    "modeled": (
        "modelled, not measured: a synthesised shift profile scaled to published "
        "EIA electricity intensity"
    ),
}


def reason_sentence(row: dict) -> str:
    """The one sentence a domain expert can check.

    Templated. No agent exists yet, and a template that states the arithmetic
    is more checkable than prose that summarises it.
    """
    shave = float(np.mean(row["monthly_shaveable_kw"]))
    return (
        f"A {row['sqft']:,.0f} sq ft {row.get('use_desc') or row['archetype']} "
        f"on rate {row['rate_class']} at ${row['demand_charge_per_kw']:.2f}/kW. "
        f"Estimated 12-month average demand {row['avg_12mo_kw']:,.0f} kW, peaking "
        f"at {row['peak_kw']:,.0f} kW; a 250 kW / 522 kWh Powerblock holds about "
        f"{shave:,.0f} kW off the billed peak in an average month, worth "
        f"${row['annual_savings_usd']:,.0f} a year in distribution demand charges "
        f"alone. Load shape is {_SOURCE_PHRASE.get(row['source'], row['source'])}."
    )


def _jsonable(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.ndarray, tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def build_export(
    scored: pd.DataFrame,
    parcels: pd.DataFrame,
    town: dict,
    top_n: int = TOP_N,
) -> dict:
    """The whole payload: counts, assumptions, and the two ranked lists."""
    columns = [c for c in PARCEL_FIELDS if c in parcels.columns] + ["loc_id"]
    detail = pd.DataFrame(parcels)[columns]
    merged = scored.merge(detail, on="loc_id", how="left")

    lists: dict[str, list[dict]] = {}
    for source in ("comstock", "modeled"):
        subset = merged[(merged["source"] == source) & merged["keep"].astype(bool)]
        subset = subset.nlargest(top_n, "annual_savings_usd")
        rows = []
        for rank, record in enumerate(subset.to_dict("records"), start=1):
            record = {k: _jsonable(v) for k, v in record.items()}
            record["rank"] = rank
            record["reason"] = reason_sentence(record)
            rows.append(record)
        lists[source] = rows

    unscored = scored["unscored_reason"].dropna()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "town": town,
        "counts": {
            "parcels_in": int(len(scored)),
            "scored": int(scored["unscored_reason"].isna().sum()),
            "unscored": {str(k): int(v) for k, v in unscored.value_counts().items()},
            "kept": int(scored["keep"].astype(bool).sum()),
            "sweet_spot": int(scored["sweet_spot"].astype(bool).sum()),
            "exported": {k: len(v) for k, v in lists.items()},
        },
        "assumptions": published_rows(),
        "lists": lists,
    }


def write_export(payload: dict, path: str | Path) -> Path:
    """Write the payload, refusing to write one the CDN cannot serve well."""
    path = Path(path)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise ValueError(
            f"export is {size / 1e6:.1f} MB, over the {MAX_BYTES / 1e6:.0f} MB "
            f"ceiling; reduce TOP_N or drop a field"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
