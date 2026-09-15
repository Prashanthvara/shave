"""Assessor use code to load-shape archetype.

`crosswalk.csv` sits next to this file and is the domain judgment of the whole
project: which Massachusetts assessor use codes correspond to which load shapes,
which are backed by measured data, and which are excluded from the customer
universe entirely. It is meant to be read by a human, and it is committed so a
reviewer can disagree with a specific line.

Two collapse points are called out explicitly in the file and repeated here
because they bound what the product can honestly claim:

  4000  every manufacturer carries this one code. Machine shops, metal
        fabricators, food and beverage producers, industrial materials makers
        and commercial laundries are indistinguishable from assessor data.
  4010  refrigerated cold storage is inside this code alongside ambient
        warehousing with no way to separate them.

Within those two codes the ranking is driven by floor area and rate class, not
by load shape. Across every other code, shape differentiation is real.

The validator exists because a missing or mistyped row produces a plausible
score with no error. That is the failure mode worth spending code on.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

CROSSWALK_PATH = Path(__file__).with_name("crosswalk.csv")

Source = Literal["comstock", "modeled", ""]
Confidence = Literal["HIGH", "MED", "LOW"]

# ComStock models exactly these 14 building types. Anything else must be
# `modeled` or `exclude`; NREL names laboratories, data centers, movie theaters
# and ice rinks as explicitly not covered.
COMSTOCK_TYPES: frozenset[str] = frozenset({
    "full_service_restaurant", "hospital", "large_hotel", "large_office",
    "medium_office", "outpatient", "quick_service_restaurant", "primary_school",
    "retail_standalone", "secondary_school", "small_hotel", "small_office",
    "strip_mall", "warehouse",
    # `office` is a family resolved to a size band from floor area at scoring
    # time; see resolve_office_band.
    "office",
})

MODELED_TYPES: frozenset[str] = frozenset({
    "industrial_manufacturing", "industrial_warehouse_process",
    "laboratory", "ice_rink", "auto_service", "auto_dealership",
    "data_hall", "university",
})

EXCLUDE = "exclude"

# Office size bands, from the ComStock prototype definitions.
SMALL_OFFICE_MAX_SQFT = 20_000
MEDIUM_OFFICE_MAX_SQFT = 100_000


class CrosswalkError(ValueError):
    """The crosswalk is internally inconsistent, or does not cover the data."""


@dataclass(frozen=True)
class CrosswalkRow:
    use_code: str
    use_desc: str
    archetype: str
    source: Source
    icp_sector: str
    confidence: Confidence
    note: str
    #: True when this use code describes a building with more than one service
    #: account. Demand charges accrue to an account, not a building, so a
    #: parcel-level estimate for such a building is an aggregate that nobody is
    #: billed for -- and it is always an overstatement, never an understatement.
    multi_meter: bool = False
    #: Blank for the statewide Department of Revenue meaning of the code. A
    #: town id when that municipality uses the code for something of its own:
    #: Lowell's fourth character is a local sub-code, and the 970-999 range is
    #: assigned locally (Worcester's 9760 is its redevelopment authority, Fall
    #: River's is a library). A town's row wins for that town and no other.
    town_id: str = ""

    @property
    def excluded(self) -> bool:
        return self.archetype == EXCLUDE

    @property
    def is_collapse_point(self) -> bool:
        """True where the code cannot distinguish load shapes within itself."""
        return self.note.startswith("COLLAPSE POINT")


#: Accepted spellings for a boolean crosswalk column, and which mean True.
#: One mapping rather than two sets, so a value can never be accepted by the
#: validator and then read as False by the parser.
_FLAG_VALUES: dict[str, bool] = {
    "": False, "0": False, "false": False,
    "1": True, "true": True,
}


def _parse_flag(raw: object, column: str, where: str) -> bool:
    """Read a 0/1 crosswalk column, rejecting anything unrecognised.

    A typo must not silently read as False: these columns only ever *remove*
    confidence, so a misparse fails open and grades a row higher than the
    domain judgment intended.
    """
    text = str(raw if raw is not None else "").strip()
    if text.lower() not in _FLAG_VALUES:
        raise CrosswalkError(f"{where} {column} must be 0 or 1, got {text!r}")
    return _FLAG_VALUES[text.lower()]


#: Town rows per crosswalk file, filled by `load` as it parses. Kept beside the
#: cached statewide dict so existing callers of `load()` see exactly what they
#: always have.
_TOWN_ROWS: dict[Path, dict[tuple[str, str], CrosswalkRow]] = {}


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict[str, CrosswalkRow]:
    """Read and validate the crosswalk; return its STATEWIDE rows.

    Town rows are validated too and made available through `rows_for_town`.
    Cached; call `load.cache_clear()` in tests.
    """
    src = Path(path) if path is not None else CROSSWALK_PATH
    if not src.exists():
        raise CrosswalkError(f"crosswalk not found at {src}")

    statewide: dict[str, CrosswalkRow] = {}
    town_rows: dict[tuple[str, str], CrosswalkRow] = {}
    with src.open(newline="", encoding="utf-8") as fh:
        for lineno, raw in enumerate(csv.DictReader(fh), start=2):
            code = (raw.get("use_code") or "").strip()
            if not code:
                raise CrosswalkError(f"{src}:{lineno} blank use_code")
            town = (raw.get("town_id") or "").strip()
            if town and not town.isdigit():
                raise CrosswalkError(f"{src}:{lineno} town_id must be a number, got {town!r}")
            if (town and (town, code) in town_rows) or (not town and code in statewide):
                raise CrosswalkError(
                    f"{src}:{lineno} duplicate use_code {code!r}"
                    + (f" for town {town}" if town else "")
                )

            row = CrosswalkRow(
                use_code=code,
                use_desc=(raw.get("use_desc") or "").strip(),
                archetype=(raw.get("archetype") or "").strip(),
                source=(raw.get("source") or "").strip(),  # type: ignore[arg-type]
                icp_sector=(raw.get("icp_sector") or "").strip(),
                confidence=((raw.get("confidence") or "LOW").strip().upper()),  # type: ignore[arg-type]
                note=(raw.get("note") or "").strip(),
                multi_meter=_parse_flag(
                    raw.get("multi_meter"), "multi_meter", f"{src.name}:{lineno} ({code})"
                ),
                town_id=town,
            )
            _validate_row(row, src, lineno)
            if town:
                town_rows[(town, code)] = row
            else:
                statewide[code] = row

    if not statewide and not town_rows:
        raise CrosswalkError(f"{src} has no rows")
    _TOWN_ROWS[src] = town_rows
    return statewide


def rows_for_town(
    town_id: int | str | None = None, path: Path | None = None
) -> dict[str, CrosswalkRow]:
    """Statewide rows with one town's own rows laid over them."""
    statewide = load(path)
    if town_id is None:
        return statewide
    tid = str(int(town_id))
    src = Path(path) if path is not None else CROSSWALK_PATH
    local = {code: row for (town, code), row in _TOWN_ROWS.get(src, {}).items() if town == tid}
    return {**statewide, **local}


def _validate_row(row: CrosswalkRow, src: Path, lineno: int) -> None:
    where = f"{src.name}:{lineno} ({row.use_code})"

    if row.confidence not in ("HIGH", "MED", "LOW"):
        raise CrosswalkError(f"{where} confidence must be HIGH/MED/LOW, got {row.confidence!r}")

    if row.excluded:
        if row.source:
            raise CrosswalkError(f"{where} excluded rows must have an empty source")
        return

    if not row.archetype:
        raise CrosswalkError(f"{where} archetype is blank; use '{EXCLUDE}' to drop a code")

    if row.source == "comstock":
        if row.archetype not in COMSTOCK_TYPES:
            raise CrosswalkError(
                f"{where} archetype {row.archetype!r} is not a ComStock type. "
                "ComStock models 14 types; anything else must be source=modeled."
            )
    elif row.source == "modeled":
        # Order matters. The ComStock check comes first so a row that tries to
        # model something NREL already measures gets the specific reason rather
        # than the generic "unknown type". Behind the MODELED_TYPES guard this
        # branch was unreachable, since the two sets are disjoint.
        if row.archetype in COMSTOCK_TYPES:
            raise CrosswalkError(
                f"{where} archetype {row.archetype!r} is measured by ComStock; "
                "do not model what NREL already covers"
            )
        if row.archetype not in MODELED_TYPES:
            raise CrosswalkError(f"{where} archetype {row.archetype!r} is not a known modeled type")
    else:
        raise CrosswalkError(f"{where} source must be 'comstock' or 'modeled', got {row.source!r}")


def resolve_office_band(sqft: float) -> str:
    """Map the `office` family to a ComStock size band."""
    if sqft <= SMALL_OFFICE_MAX_SQFT:
        return "small_office"
    if sqft <= MEDIUM_OFFICE_MAX_SQFT:
        return "medium_office"
    return "large_office"


def archetype_for(use_code: str, sqft: float | None = None, town_id: int | str | None = None) -> CrosswalkRow | None:
    """The crosswalk row for a use code, or None if the code is excluded.

    Raises if the code is absent entirely, which is a data-coverage bug rather
    than a scoring decision.
    """
    rows = rows_for_town(town_id)
    code = str(use_code).strip()
    if code not in rows:
        raise CrosswalkError(
            f"use_code {code!r} has no crosswalk row. Every code present in the "
            "data must be classified, including as 'exclude'."
        )
    row = rows[code]
    if row.excluded:
        return None
    if row.archetype == "office":
        if sqft is None:
            raise CrosswalkError(f"use_code {code!r} maps to the office family; sqft is required")
        return CrosswalkRow(**{**row.__dict__, "archetype": resolve_office_band(sqft)})
    return row


def assert_covers(use_codes: set[str], town_id: int | str | None = None) -> None:
    """Every use code observed in real data has a row. Call this at ingest.

    Without it a code the crosswalk has never seen silently produces no row,
    the parcel drops out, and the universe quietly shrinks with no error.
    """
    rows = rows_for_town(town_id)
    missing = {c for c in (str(c).strip() for c in use_codes) if c and c not in rows}
    if missing:
        raise CrosswalkError(
            f"{len(missing)} use code(s) in the data have no crosswalk row: "
            f"{sorted(missing)[:15]}{' ...' if len(missing) > 15 else ''}"
        )


def coverage_summary() -> dict[str, int]:
    """Counts over every row in the file, town rows included."""
    statewide = load()
    town_rows = list(_TOWN_ROWS.get(CROSSWALK_PATH, {}).values())
    rows = list(statewide.values()) + town_rows
    return {
        "total": len(rows),
        "comstock": sum(1 for r in rows if r.source == "comstock"),
        "modeled": sum(1 for r in rows if r.source == "modeled"),
        "excluded": sum(1 for r in rows if r.excluded),
        "collapse_points": sum(1 for r in rows if r.is_collapse_point),
        "town_overrides": len(town_rows),
    }
