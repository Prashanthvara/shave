"""A static address index, so a reader can check a building they already know.

Design review D5 calls this the verification moment: what a domain expert does
thirty seconds in is look up a site they know. It ships as a JSON file built
beside ranked.json, not a database, so it cannot break when a free tier sleeps.

Normalisation exists twice -- here, to build the keys, and in app.js, to read a
query -- because the page cannot import Python. Both are held to one set of
cases in tests/fixtures/address_cases.json, and the abbreviation table travels
inside the index so the page never keeps a copy of its own.

Every parcel the pipeline screened is indexed with what happened to it. A
building that was looked at and screened out is a finding, and answering "not
found" for it would be a silence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

import pandas as pd

from shave import method, pipeline
from shave.assumptions import MIN_AVG_DEMAND_KW, RATED_POWER_KW

INDEX_SCHEMA_VERSION = "1.0.0"

#: USPS-style suffixes and directionals. The assessor mostly abbreviates and
#: occasionally does not ("100 C STREET"), and readers paste either form.
ABBREVIATIONS: dict[str, str] = {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "DRIVE": "DR",
    "BOULEVARD": "BLVD", "PLACE": "PL", "LANE": "LN", "COURT": "CT",
    "PARKWAY": "PKWY", "HIGHWAY": "HWY", "SQUARE": "SQ", "TERRACE": "TER",
    "CIRCLE": "CIR", "TURNPIKE": "TPKE", "EXTENSION": "EXT",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
}

_SPLIT = re.compile(r"[^A-Z0-9]+")
_STATE = frozenset({"MA", "MASS", "MASSACHUSETTS"})
#: A ZIP or the +4 of a ZIP+4. Four or five digits only, so "ROUTE 9" survives.
_ZIPPISH = re.compile(r"^\d{4,5}$")

STATUS_SENTENCES: dict[str, str] = {
    "ranked": "On the ranked list.",
    "not_exported": (
        "Scored and above the demand floor, but outside the rows this page "
        "publishes. The saving shown is the scorer's own figure for it."
    ),
    "below_floor": (
        f"Screened out: its estimated 12-month average demand is under "
        f"{MIN_AVG_DEMAND_KW:.0f} kW, so a {RATED_POWER_KW:.0f} kW battery has no "
        f"peak worth shaving here. That is a finding, not a missing row."
    ),
    **{reason: method.FLAG_MEANINGS[reason] for reason in pipeline.UNSCORED_REASONS},
}


def _tokens(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text.upper()) if t]


def normalize(text) -> str:
    """Upper-case, punctuation to spaces, suffixes abbreviated. "" if absent."""
    if not isinstance(text, str):
        return ""
    return " ".join(ABBREVIATIONS.get(t, t) for t in _tokens(text))


def parse_query(query: str, towns: Sequence[str]) -> dict[str, str]:
    """Split a pasted address into a normalised street and a town.

    With a comma: everything before the first comma is the street, and what
    follows, less any state or ZIP, is the town. Without one: trailing state
    and ZIP tokens are peeled off, then a covered town name at the end is
    taken as the town. At least one street token always survives the peel, so
    a bare number is not erased.

    app.js `parseQuery` is the same function. Change both, and the cases file.
    """
    text = query if isinstance(query, str) else ""
    head, comma, tail = text.partition(",")
    street = _tokens(head)
    town: list[str] = []
    if comma:
        town = [t for t in _tokens(tail) if t not in _STATE and not _ZIPPISH.match(t)]
    else:
        while len(street) > 1 and (street[-1] in _STATE or _ZIPPISH.match(street[-1])):
            street.pop()
        for name in towns:
            words = _tokens(name)
            if len(street) > len(words) and street[-len(words):] == words:
                street, town = street[: -len(words)], words
                break
    return {
        "street": " ".join(ABBREVIATIONS.get(t, t) for t in street),
        "town": " ".join(town),
    }


def _number(value, digits: int):
    """A JSON-safe rounded number, or None for missing and NaN."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return round(f, digits) if digits else int(round(f))


def build_index(
    parcels: pd.DataFrame,
    scored: pd.DataFrame,
    lists: Mapping[str, list[dict]],
    towns: Sequence[str],
) -> dict:
    """One entry per screened parcel that has an address.

    `lists` is the export's two ranked lists. Their ranks are copied, never
    recomputed, and the lists stay separate: an entry names which list it is
    on, and there is no cross-list rank.
    """
    exported = {
        row["loc_id"]: (name, row["rank"])
        for name, rows in lists.items()
        for row in rows
    }
    detail = pd.DataFrame(parcels)[["loc_id", "site_addr", "confidence"]]
    merged = scored.merge(detail, on="loc_id", how="left")

    entries = []
    for rec in merged.to_dict("records"):
        key = normalize(rec.get("site_addr"))
        if not key:
            continue
        loc_id = str(rec["loc_id"])
        unscored = rec.get("unscored_reason")
        list_name, rank = "", None
        if loc_id in exported:
            status = "ranked"
            list_name, rank = exported[loc_id]
        elif isinstance(unscored, str) and unscored:
            status = unscored
        elif not bool(rec.get("keep")):
            status = "below_floor"
        else:
            status = "not_exported"
        entries.append({
            "key": key,
            "addr": str(rec["site_addr"]),
            "loc_id": loc_id,
            "status": status,
            "list": list_name,
            "rank": rank,
            "source": str(rec.get("source") or ""),
            "archetype": str(rec.get("archetype") or ""),
            "sqft": _number(rec.get("sqft"), 0),
            "avg_12mo_kw": _number(rec.get("avg_12mo_kw"), 1),
            "rate_class": str(rec.get("rate_class") or ""),
            "annual_savings_usd": _number(rec.get("annual_savings_usd"), 0),
            "confidence": rec["confidence"] if isinstance(rec.get("confidence"), str) else "",
        })
    entries.sort(key=lambda e: (e["key"], e["loc_id"]))

    return {
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "towns": [t.upper() for t in towns],
        "abbreviations": dict(ABBREVIATIONS),
        "statuses": dict(STATUS_SENTENCES),
        "entries": entries,
    }
