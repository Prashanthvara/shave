"""MassGIS L3 standardised assessor parcels, in, cleaned, and archetyped.

One municipality per call. The output is one row per *scoreable parcel* with a
schema the scorer and the ranked view can both read without knowing anything
about ESRI shapefiles or the Massachusetts assessor use-code system.

Three things in here are judgment calls rather than mechanics, so they are
written down.

The one-to-many collapse
------------------------
`TaxPar` is one polygon per parcel and `LOC_ID` is unique within it. `Assess` is
one row per *assessed interest*, so a LOC_ID can carry many rows: a condominium
with 56 units, a building held by two owners, a site the town records under
several property ids. Worcester FY2026 has 47,675 Assess rows against 42,455
polygons. Joining naively multiplies parcels; joining with `drop_duplicates`
silently throws floor area away. Neither is acceptable when the number being
published is a dollar saving per building.

The rule implemented here:

  * group the in-scope Assess rows by LOC_ID;
  * **floor area is the sum over the group.** The battery serves whatever is on
    the parcel, and total conditioned floor area is what sets the magnitude of
    the modelled load. Summing means the town's total square footage survives
    the collapse exactly — 53.18M sq ft in, 53.18M sq ft out for Worcester;
  * **identity comes from the dominant record**: largest `BLD_AREA`, ties broken
    by largest `TOTAL_VAL`, then by lowest `PROP_ID` so the result is stable
    across runs and machines. This deviates from the obvious "highest value
    wins" because the archetype supplies a *shape* and the shape should come
    from whichever record contributes most of the area, not from whichever
    record is worth the most money. A 5,000 sq ft high-value showroom should not
    dictate the load shape of a 90,000 sq ft parcel;
  * where the grouped records disagree on `USE_CODE` the parcel is flagged
    `multi_use` and the dominant record's code still picks the shape. Worcester
    has exactly two such parcels, so this branch is rare but it must not be
    silent.

No record is dropped without being counted. Every row that leaves the universe
is attributed to one of `out_of_class`, `unbuilt_use_code`, `excluded_use_code`
or `blank_loc_id` in `GeoDataFrame.attrs`, and `summarise` reports them.

Why the assessor vintage matters
--------------------------------
Municipalities certify and submit to MassGIS on their own schedules, so an L3
extract is a snapshot of *that town's* fiscal year, not of a common date. Two
towns in one ranking can be three or four years apart: a 2019-vintage town will
be missing buildings a 2026-vintage town has, will carry retired use codes, and
will value floor area against a different assessment. Because the score scales
with `BLD_AREA`, a stale town ranks systematically low for a reason that has
nothing to do with its buildings. So `assess_fy` rides on every row — never on
the town, never inferred at render time — and the ranked view is expected to
show it next to the parcel.

The scoping question
--------------------
`crosswalk.assert_covers` is deliberately unforgiving: an unclassified code must
raise rather than quietly shrink the universe. That only works if the set handed
to it is the set of codes that could plausibly describe a *building*. Two filters
define it, in this order:

  1. Massachusetts state class. Leading digit 3 (commercial), 4 (industrial) or
     9 (exempt). Classes 0-2 and 5-8 are mixed-use residential, residential,
     open space, personal property and chapter land.
  2. The code describes a building *somewhere in this town*. A use code under
     which the town records zero square feet of building area across every
     parcel is describing land, not a building — vacant lots (the `...V`
     codes), rights of way, substations without structures. Worcester has 57
     such codes and every one of them totals exactly 0 sq ft.

Applied to Worcester those two filters yield precisely the 95 codes the
crosswalk classifies, with nothing left over. A code that describes real
building area and has no crosswalk row raises `CrosswalkError`, which is the
whole point.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from . import crosswalk, siting
from .assumptions import DEFAULT_STORIES, LIKELY_SINGLE_METERED_MAX_SQFT

__all__ = [
    "load_municipality",
    "IngestError",
    "build_parcels",
    "summarise",
    "ASSESS_COLUMNS",
    "TAXPAR_COLUMNS",
    "OUTPUT_COLUMNS",
    "PREDICATES",
    "COARSE_REASON",
    "NONRESIDENTIAL_CLASSES",
]

# Column pushdown. Reading all 37 Assess fields costs about 3x this list, and
# the ones left behind (sale book and page, owner mailing address, CAMA id) have
# no bearing on a load shape.
ASSESS_COLUMNS: tuple[str, ...] = (
    "PROP_ID", "LOC_ID", "TOTAL_VAL", "FY", "USE_CODE", "SITE_ADDR",
    "CITY", "ZIP", "OWNER1", "ZONING", "YEAR_BUILT", "BLD_AREA",
    "STORIES", "TOWN_ID",
)

# TaxPar carries nothing we want except the polygon and its key. SHAPE_Area is
# the parcel, not the building, so it is not floor area and is not read.
TAXPAR_COLUMNS: tuple[str, ...] = ("LOC_ID", "POLY_TYPE")

# Massachusetts state class leading digits that can describe a C&I building.
NONRESIDENTIAL_CLASSES: tuple[str, ...] = ("3", "4", "9")

# The polygon type that carries an assessable fee interest. ROW, PRIV_ROW,
# RAIL_ROW and WATER polygons exist in TaxPar and never join to Assess.
FEE_POLY_TYPE = "FEE"

# The seven HIGH-confidence predicates, in report order. A parcel is HIGH only
# if all graded predicates hold. Names are returned verbatim in
# `confidence_reasons` so the UI can say which one failed rather than showing a
# bare chip. `single_roofprint` is graded only when a structures layer is
# supplied; `gdf.attrs["roofprints_graded"]` records whether it was.
PREDICATES: tuple[str, ...] = (
    "unique_archetype",          # the use code maps 1:1 to one archetype
    "has_floor_area",            # BLD_AREA present and non-zero, as the assessor recorded it
    "single_record",             # exactly one Assess record at this LOC_ID
    "single_owner",              # one owner of record
    "within_single_meter_cap",   # floor area <= LIKELY_SINGLE_METERED_MAX_SQFT
    "single_meter_archetype",    # the use code is not definitionally multi-tenant
    "single_roofprint",          # exactly one roofprint on the parcel
)

# Not a predicate: a hard floor. The crosswalk marks 4000 and 4010 as COLLAPSE
# POINTs — every manufacturer in the state carries 4000, and cold storage hides
# inside 4010 — so those parcels are capped at LOW however well they score on
# the other predicates.
COARSE_REASON = "coarse_use_code"

# Also a hard floor, from the spec's step 2: a floor area estimated from the
# roofprint rather than recorded by the assessor drops the parcel to LOW.
FALLBACK_REASON = "floor_area_from_roofprint"

OUTPUT_COLUMNS: tuple[str, ...] = (
    "loc_id", "prop_id", "use_code", "use_desc", "archetype", "source",
    "icp_sector", "sqft", "sqft_source", "stories", "year_built", "owner",
    "site_addr", "city", "zip", "zoning", "assess_fy", "record_count",
    "owner_count", "confidence", "confidence_reasons", "multi_use", "multi_meter",
    "roofprint_count", "roofprint_sqft", "wall_run_ft", "wall_bearing_deg",
    "siting", "wall_segment", "geometry",
)

_FY_IN_NAME = re.compile(r"_FY(\d{2,4})", re.IGNORECASE)


class IngestError(ValueError):
    """The municipality directory is not a readable MassGIS L3 extract."""


# ---------------------------------------------------------------------------
# file discovery
# ---------------------------------------------------------------------------


def _find_one(dir_path: Path, patterns: Sequence[str], what: str) -> Path:
    """The single file matching the first pattern that matches anything."""
    for pattern in patterns:
        hits = sorted(dir_path.glob(pattern))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise IngestError(
                f"{what}: {len(hits)} files match {pattern!r} in {dir_path}; "
                f"expected one: {[h.name for h in hits]}"
            )
    raise IngestError(f"{what}: nothing matching {list(patterns)} in {dir_path}")


def _fy_from_filename(*paths: Path) -> int | None:
    """Fiscal year carried in the MassGIS filename, e.g. `..._CY26_FY26.dbf`.

    Cross-checked against the `FY` column. The filename is the weaker of the
    two — it is a naming convention, not data — so it never overrides.
    """
    for path in paths:
        match = _FY_IN_NAME.search(path.stem)
        if match:
            raw = int(match.group(1))
            return raw if raw > 100 else 2000 + raw
    return None


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------


def _text(series: pd.Series) -> pd.Series:
    """A stripped string column with empties as NA. Vectorised."""
    out = series.astype("string").str.strip()
    return out.mask(out.eq(""), pd.NA)


def _use_code(series: pd.Series) -> pd.Series:
    """Use codes are strings: Worcester has `942C` and `995` alongside `3400`."""
    return series.astype("string").str.strip().fillna("")


def _crosswalk_frame(codes: Iterable[str]) -> pd.DataFrame:
    """One row per distinct use code, resolved through `crosswalk.archetype_for`.

    This iterates over distinct *codes* — 95 of them for Worcester — and never
    over parcels. The office family is left unresolved here because its band
    depends on floor area, which is only known after the collapse.
    """
    rows = crosswalk.load()
    records = []
    for code in sorted(set(codes)):
        cw = rows[code]
        office_family = cw.archetype == "office"
        resolved = cw if office_family else crosswalk.archetype_for(code)
        records.append(
            {
                "use_code": code,
                "use_desc": cw.use_desc,
                "archetype": "" if resolved is None else resolved.archetype,
                "source": "" if resolved is None else resolved.source,
                "icp_sector": cw.icp_sector,
                "excluded": resolved is None,
                "office_family": office_family,
                # The crosswalk's own confidence column is the mapping-quality
                # column: HIGH means this code names one archetype and nothing
                # else. MED and LOW rows carry a note saying what the code
                # cannot distinguish. That is exactly the "maps 1:1" predicate.
                "unique_archetype": cw.confidence == "HIGH",
                "collapse_point": cw.is_collapse_point,
                "multi_meter": cw.multi_meter,
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "use_code", "use_desc", "archetype", "source", "icp_sector",
            "excluded", "office_family", "unique_archetype", "collapse_point",
            "multi_meter",
        ],
    )


def _resolve_office_bands(archetype: pd.Series, sqft: pd.Series) -> pd.Series:
    """Vectorised `crosswalk.resolve_office_band`, applied post-collapse.

    The band edges and the labels both come from `crosswalk`; nothing about the
    office bands is restated here. `searchsorted(..., side="left")` reproduces
    the function's `<=` boundaries exactly, which the tests pin.
    """
    edges = np.array(
        [crosswalk.SMALL_OFFICE_MAX_SQFT, crosswalk.MEDIUM_OFFICE_MAX_SQFT],
        dtype=float,
    )
    labels = np.array(
        [
            crosswalk.resolve_office_band(float(edges[0])),
            crosswalk.resolve_office_band(float(edges[1])),
            crosswalk.resolve_office_band(float(edges[1]) + 1.0),
        ]
    )
    area = pd.to_numeric(sqft, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    banded = pd.Series(labels[np.searchsorted(edges, area, side="left")],
                       index=archetype.index, dtype="string")
    return archetype.where(archetype != "office", banded)


# ---------------------------------------------------------------------------
# the core: frames in, parcels out
# ---------------------------------------------------------------------------


def build_parcels(
    assess: pd.DataFrame,
    taxpar: gpd.GeoDataFrame | None = None,
    *,
    town_id: int | str | None = None,
    assess_fy_hint: int | None = None,
    structures: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Collapse, classify and score-confidence a raw Assess frame.

    Split out from `load_municipality` so the collapse rule, the coverage
    assertion and the confidence predicates are all testable against small
    synthetic frames without writing a shapefile. `load_municipality` is this
    function plus file discovery and timing.
    """
    raw = assess.copy()
    for column in ("LOC_ID", "USE_CODE", "BLD_AREA"):
        if column not in raw.columns:
            raise IngestError(f"Assess frame is missing required column {column!r}")

    n_assess_records = len(raw)

    if town_id is not None and "TOWN_ID" in raw.columns and n_assess_records:
        observed = set(pd.to_numeric(raw["TOWN_ID"], errors="coerce").dropna().astype(int))
        want = int(town_id)
        if observed and observed != {want}:
            raise IngestError(
                f"TOWN_ID in the data is {sorted(observed)}, expected {want}. "
                "Wrong directory, or a multi-town extract."
            )

    raw["LOC_ID"] = _text(raw["LOC_ID"])
    raw["USE_CODE"] = _use_code(raw["USE_CODE"])
    raw["BLD_AREA"] = pd.to_numeric(raw.get("BLD_AREA"), errors="coerce")
    raw["TOTAL_VAL"] = pd.to_numeric(raw.get("TOTAL_VAL"), errors="coerce").fillna(0.0)
    raw["PROP_ID"] = _text(raw["PROP_ID"]) if "PROP_ID" in raw.columns else pd.NA
    raw["OWNER1"] = _text(raw["OWNER1"]) if "OWNER1" in raw.columns else pd.NA

    # A record with no LOC_ID cannot be located on the ground and cannot be
    # joined to a polygon. Counted, never silent, and counted twice: Worcester
    # has 64 town-wide, 23 of them in the commercial/industrial/exempt classes,
    # and two of those 23 are real 4000-code industrial buildings totalling
    # 180,843 sq ft that simply cannot be put on the map. That is a defect in
    # the source extract, not a modelling choice, so it is reported rather than
    # absorbed.
    blank_loc = raw["LOC_ID"].isna()
    n_blank_loc_id = int(blank_loc.sum())
    blank_in_class = blank_loc & raw["USE_CODE"].str[:1].isin(NONRESIDENTIAL_CLASSES)
    n_blank_loc_id_in_class = int(blank_in_class.sum())
    blank_loc_id_sqft = float(raw.loc[blank_in_class, "BLD_AREA"].sum())
    raw = raw.loc[~blank_loc]

    # Multi-metering evidence is a property of the *parcel*, not of the
    # commercial records on it: a LOC_ID carrying a shop and three apartments is
    # not single-metered. So record and owner counts are taken over every Assess
    # row at the LOC_ID, before any use-code filtering narrows the frame.
    # Built column-by-column rather than through `.agg`: passing a callable to
    # `.agg` drops pandas into a per-group Python loop and costs ~9s on 47k
    # rows against ~0.02s for the native `nunique`.
    all_records = raw.groupby("LOC_ID", sort=False)
    parcel_stats = pd.DataFrame(
        {
            "record_count": all_records.size(),
            "owner_count": all_records["OWNER1"].nunique(dropna=False),
        }
    )

    # --- scoping, filter 1: state class -----------------------------------
    in_class = raw["USE_CODE"].str[:1].isin(NONRESIDENTIAL_CLASSES)
    n_out_of_class = int((~in_class).sum())
    candidates = raw.loc[in_class]

    # --- scoping, filter 2: the code describes a building somewhere -------
    built_area_by_code = candidates.groupby("USE_CODE", sort=False)["BLD_AREA"].sum(
        min_count=1
    )
    built_codes = set(built_area_by_code.index[built_area_by_code.fillna(0.0) > 0])
    describes_building = candidates["USE_CODE"].isin(built_codes)
    n_unbuilt_code = int((~describes_building).sum())
    candidates = candidates.loc[describes_building]

    # --- coverage assertion, before anything can shrink silently ----------
    observed_codes = set(candidates["USE_CODE"].unique())
    crosswalk.assert_covers(observed_codes)

    cw = _crosswalk_frame(observed_codes)
    candidates = candidates.merge(cw, left_on="USE_CODE", right_on="use_code", how="left")

    excluded_mask = candidates["excluded"].fillna(True).to_numpy(dtype=bool)
    n_excluded_records = int(excluded_mask.sum())
    excluded_parcels = int(candidates.loc[excluded_mask, "LOC_ID"].nunique())
    scoreable = candidates.loc[~excluded_mask]
    n_scoreable_records = len(scoreable)

    # --- the collapse ------------------------------------------------------
    ordered = scoreable.sort_values(
        ["LOC_ID", "BLD_AREA", "TOTAL_VAL", "PROP_ID"],
        ascending=[True, False, False, True],
        kind="stable",
        na_position="last",
    )
    dominant = ordered.drop_duplicates("LOC_ID", keep="first")

    grouped = scoreable.groupby("LOC_ID", sort=False)
    collapse_stats = pd.DataFrame(
        {
            # min_count=1 keeps a genuinely missing BLD_AREA as NA rather than
            # turning it into a confident zero.
            "sqft": grouped["BLD_AREA"].sum(min_count=1),
            "use_code_count": grouped["USE_CODE"].nunique(),
            "scoreable_record_count": grouped["LOC_ID"].size(),
        }
    )
    n_collapsed_away = n_scoreable_records - len(collapse_stats)

    parcels = (
        dominant.set_index("LOC_ID")
        .join(collapse_stats)
        .join(parcel_stats)
        .reset_index()
    )

    # --- assessor vintage --------------------------------------------------
    fy_column = pd.to_numeric(parcels.get("FY"), errors="coerce") if "FY" in parcels else None
    if fy_column is not None and fy_column.notna().any():
        parcels["assess_fy"] = fy_column.astype("Int64")
    else:
        parcels["assess_fy"] = pd.array([assess_fy_hint] * len(parcels), dtype="Int64")
    fy_values = sorted(int(v) for v in pd.unique(parcels["assess_fy"].dropna()))
    assess_fy = fy_values[-1] if fy_values else assess_fy_hint

    # --- geometry ----------------------------------------------------------
    crs = None
    n_missing_geometry = len(parcels)
    if taxpar is not None and len(taxpar):
        geo = taxpar
        if "POLY_TYPE" in geo.columns:
            fee = geo["POLY_TYPE"].astype("string").str.strip().eq(FEE_POLY_TYPE)
            if fee.any():
                geo = geo.loc[fee]
        geo = geo.assign(LOC_ID=_text(geo["LOC_ID"]))
        geo = geo.loc[geo["LOC_ID"].notna()]
        if geo["LOC_ID"].duplicated().any():
            # Not seen in Worcester (LOC_ID is unique across all 42,455
            # polygons). Deterministic tie-break if another town differs.
            geo = geo.assign(_a=geo.geometry.area).sort_values(
                ["LOC_ID", "_a"], ascending=[True, False], kind="stable"
            ).drop_duplicates("LOC_ID", keep="first").drop(columns="_a")
        crs = geo.crs
        parcels = parcels.merge(
            geo[["LOC_ID", geo.geometry.name]].rename(
                columns={geo.geometry.name: "geometry"}
            ),
            on="LOC_ID",
            how="left",
        )
        n_missing_geometry = int(parcels["geometry"].isna().sum())
    else:
        parcels["geometry"] = None

    # --- roofprints, the floor-area fallback, office band, grading ---------
    # All of these follow the geometry join because roofprints are assigned
    # by polygon. The office band needs the FINAL floor area and the fallback
    # can supply one, so the band is resolved after it; grading comes last
    # because it reads both.
    parcels["assessor_sqft"] = pd.to_numeric(parcels["sqft"], errors="coerce")
    roofprints_graded = structures is not None and crs is not None
    n_fallback = 0
    if roofprints_graded:
        # A parcel with no polygon arrives from the merge as NaN, not None;
        # normalise it so the GeoSeries sees a missing geometry, not a float.
        polygons = [g if getattr(g, "geom_type", None) else None for g in parcels["geometry"]]
        mapped = gpd.GeoDataFrame(
            {"loc_id": parcels["LOC_ID"].astype(str).to_numpy()},
            geometry=gpd.GeoSeries(polygons, crs=crs),
            crs=crs,
        )
        sited = siting.screen(mapped, structures).set_index("loc_id")
        for column in siting.SCREEN_COLUMNS[1:]:
            parcels[column] = parcels["LOC_ID"].astype(str).map(sited[column]).to_numpy()
        stories = (
            pd.to_numeric(parcels["STORIES"], errors="coerce")
            if "STORIES" in parcels else pd.Series(np.nan, index=parcels.index)
        )
        stories = stories.where(stories > 0, DEFAULT_STORIES)
        area = parcels["assessor_sqft"]
        roof_area = pd.to_numeric(parcels["roofprint_sqft"], errors="coerce").fillna(0.0)
        use_roof = (area.isna() | area.le(0)) & roof_area.gt(0)
        parcels["sqft"] = area.where(~use_roof, roof_area * stories)
        parcels["sqft_source"] = np.where(use_roof, "roofprint", "assessor")
        n_fallback = int(use_roof.sum())
    else:
        for column in siting.SCREEN_COLUMNS[1:]:
            parcels[column] = None
        parcels["sqft_source"] = "assessor"

    parcels["archetype"] = _resolve_office_bands(
        parcels["archetype"].astype("string"), parcels["sqft"]
    )
    parcels = _apply_confidence(parcels, roofprints_graded=roofprints_graded)

    # --- final schema ------------------------------------------------------
    out = pd.DataFrame(
        {
            "loc_id": parcels["LOC_ID"].astype("string"),
            "prop_id": parcels["PROP_ID"].astype("string"),
            "use_code": parcels["USE_CODE"].astype("string"),
            "use_desc": parcels["use_desc"].astype("string"),
            "archetype": parcels["archetype"].astype("string"),
            "source": parcels["source"].astype("string"),
            "icp_sector": parcels["icp_sector"].astype("string"),
            "sqft": pd.to_numeric(parcels["sqft"], errors="coerce").astype("Float64"),
            "sqft_source": parcels["sqft_source"].astype("string"),
            "stories": pd.to_numeric(
                parcels["STORIES"], errors="coerce"
            ).astype("Float64") if "STORIES" in parcels else pd.NA,
            # YEAR_BUILT is 0 for 3,061 Worcester records. Zero is not a year.
            "year_built": _year_built(parcels),
            "owner": parcels["OWNER1"].astype("string"),
            "site_addr": _text(parcels["SITE_ADDR"]) if "SITE_ADDR" in parcels else pd.NA,
            "city": _text(parcels["CITY"]) if "CITY" in parcels else pd.NA,
            "zip": _text(parcels["ZIP"]) if "ZIP" in parcels else pd.NA,
            "zoning": _text(parcels["ZONING"]) if "ZONING" in parcels else pd.NA,
            "assess_fy": parcels["assess_fy"],
            "record_count": parcels["record_count"].astype("Int64"),
            "owner_count": parcels["owner_count"].astype("Int64"),
            "confidence": parcels["confidence"].astype("string"),
            "confidence_reasons": parcels["confidence_reasons"],
            "multi_use": parcels["use_code_count"].fillna(1).gt(1),
            # The crosswalk's domain judgment, carried to the output so the row
            # detail can name it as the reason the row is not HIGH.
            "multi_meter": parcels["multi_meter"].fillna(False).astype(bool),
            "roofprint_count": pd.to_numeric(parcels["roofprint_count"], errors="coerce").astype("Int64"),
            "roofprint_sqft": pd.to_numeric(parcels["roofprint_sqft"], errors="coerce").astype("Float64"),
            "wall_run_ft": pd.to_numeric(parcels["wall_run_ft"], errors="coerce").astype("Float64"),
            "wall_bearing_deg": pd.to_numeric(parcels["wall_bearing_deg"], errors="coerce").astype("Int64"),
            "siting": parcels["siting"].astype("string"),
            "wall_segment": parcels["wall_segment"],
            "geometry": parcels["geometry"],
        }
    )
    out = out.loc[:, list(OUTPUT_COLUMNS)].sort_values("loc_id", kind="stable")
    gdf = gpd.GeoDataFrame(out.reset_index(drop=True), geometry="geometry", crs=crs)

    gdf.attrs.update(
        {
            "town_id": None if town_id is None else int(town_id),
            "assess_fy": assess_fy,
            "assess_fy_values": fy_values,
            "assess_records_total": n_assess_records,
            "blank_loc_id_records": n_blank_loc_id,
            "blank_loc_id_in_class_records": n_blank_loc_id_in_class,
            "blank_loc_id_in_class_sqft": blank_loc_id_sqft,
            "out_of_class_records": n_out_of_class,
            "unbuilt_use_code_records": n_unbuilt_code,
            "excluded_records": n_excluded_records,
            "excluded_parcels": excluded_parcels,
            "scoreable_records": n_scoreable_records,
            "collapsed_away_records": n_collapsed_away,
            "missing_geometry": n_missing_geometry,
            "use_codes_in_scope": len(observed_codes),
            "roofprints_graded": roofprints_graded,
            "fallback_floor_area": n_fallback,
        }
    )
    return gdf


def _year_built(parcels: pd.DataFrame) -> pd.Series:
    if "YEAR_BUILT" not in parcels:
        return pd.Series(pd.NA, index=parcels.index, dtype="Int64")
    year = pd.to_numeric(parcels["YEAR_BUILT"], errors="coerce")
    return year.mask(year.le(0)).astype("Int64")


def _apply_confidence(parcels: pd.DataFrame, roofprints_graded: bool = False) -> pd.DataFrame:
    """HIGH/MED/LOW plus the names of the predicates that failed.

    HIGH is every graded predicate. MED is exactly one failure. LOW is two or
    more, a coarse 400-series code, or a floor area estimated from the
    roofprint -- regardless of the rest. The failing names are carried out so
    the ranked view can say *why* a row is not HIGH.

    `has_floor_area` reads the assessor's own figure, so a parcel rescued by
    the roofprint fallback still says the assessor recorded nothing.
    """
    sqft = pd.to_numeric(parcels["sqft"], errors="coerce")
    assessor = pd.to_numeric(
        parcels["assessor_sqft"] if "assessor_sqft" in parcels else parcels["sqft"],
        errors="coerce",
    )
    # Read defensively: existing tests build parcel frames without these
    # columns, and a missing column is a KeyError where a missing value is not.
    multi_meter = (
        parcels["multi_meter"] if "multi_meter" in parcels
        else pd.Series(False, index=parcels.index)
    ).fillna(False).astype(bool)
    roof_count = pd.to_numeric(
        parcels["roofprint_count"] if "roofprint_count" in parcels
        else pd.Series(np.nan, index=parcels.index),
        errors="coerce",
    )
    graded = [p for p in PREDICATES if roofprints_graded or p != "single_roofprint"]
    holds = pd.DataFrame(
        {
            "unique_archetype": parcels["unique_archetype"].fillna(False).astype(bool),
            "has_floor_area": (assessor.notna() & assessor.gt(0)).to_numpy(),
            "single_record": parcels["record_count"].fillna(1).eq(1).to_numpy(),
            "single_owner": parcels["owner_count"].fillna(1).eq(1).to_numpy(),
            "within_single_meter_cap": sqft.fillna(0.0)
            .le(LIKELY_SINGLE_METERED_MAX_SQFT)
            .to_numpy(),
            "single_meter_archetype": ~multi_meter.to_numpy(),
            "single_roofprint": roof_count.eq(1).to_numpy(),
        },
        index=parcels.index,
    )[graded]

    coarse = parcels["collapse_point"].fillna(False).astype(bool).to_numpy()
    fallback = (
        parcels["sqft_source"].eq("roofprint").to_numpy()
        if "sqft_source" in parcels else np.zeros(len(parcels), dtype=bool)
    )
    failures = ~holds.to_numpy(dtype=bool)
    n_failed = failures.sum(axis=1)

    confidence = np.where(
        coarse | fallback | (n_failed >= 2), "LOW",
        np.where(n_failed == 1, "MED", "HIGH"),
    )

    # A comprehension over output parcels (~2.1k for Worcester), not over the
    # 47,675 input records. The 47k-row work above is all vectorised.
    all_names = graded + [COARSE_REASON, FALLBACK_REASON]
    flagged = np.column_stack([failures, coarse[:, None], fallback[:, None]])
    reasons = [
        tuple(name for name, bad in zip(all_names, row) if bad) for row in flagged
    ]

    parcels = parcels.copy()
    parcels["confidence"] = confidence
    parcels["confidence_reasons"] = pd.Series(reasons, index=parcels.index, dtype=object)
    return parcels


# ---------------------------------------------------------------------------
# the public entry point
# ---------------------------------------------------------------------------


def load_municipality(
    dir_path: str | Path, town_id: int | str, structures_path: str | Path | None = None
) -> gpd.GeoDataFrame:
    """One row per scoreable parcel for one MassGIS L3 municipality directory.

    Pure function of `dir_path`: no network, no writes, no cache on disk. Reads
    `M<town_id>TaxPar_*.shp` for geometry and `M<town_id>Assess_*.dbf` for
    attributes, collapses the one-to-many join, attaches the crosswalk and
    grades confidence.

    With `structures_path`, it also joins the MassGIS STRUCTURES_POLY layer:
    roofprint counts feed the `single_roofprint` predicate, roofprint area
    fills a missing floor area, and every parcel gets a siting screen result.

    Raises `crosswalk.CrosswalkError` if the town uses a building use code the
    crosswalk has never classified, and `IngestError` if the directory is not a
    readable L3 extract.

    `GeoDataFrame.attrs` carries `assess_fy`, `town_id`, the source paths, the
    wall-clock `load_seconds`, and a count for every record that left the
    universe. `summarise` renders that into a dict.
    """
    started = time.perf_counter()
    directory = Path(dir_path)
    if not directory.is_dir():
        raise IngestError(f"not a directory: {directory}")

    tid = int(town_id)
    taxpar_path = _find_one(
        directory,
        [f"M{tid}TaxPar_*.shp", f"M{tid:03d}TaxPar_*.shp", "M*TaxPar_*.shp"],
        "TaxPar",
    )
    assess_path = _find_one(
        directory,
        [f"M{tid}Assess_*.dbf", f"M{tid:03d}Assess_*.dbf", "M*Assess_*.dbf"],
        "Assess",
    )

    assess = pyogrio.read_dataframe(
        assess_path, read_geometry=False, columns=list(ASSESS_COLUMNS)
    )
    taxpar = pyogrio.read_dataframe(taxpar_path, columns=list(TAXPAR_COLUMNS))

    structures = (
        siting.load_structures(structures_path) if structures_path is not None else None
    )
    gdf = build_parcels(
        assess,
        taxpar,
        town_id=tid,
        assess_fy_hint=_fy_from_filename(assess_path, taxpar_path),
        structures=structures,
    )

    filename_fy = _fy_from_filename(assess_path, taxpar_path)
    gdf.attrs.update(
        {
            "source_dir": str(directory),
            "assess_path": str(assess_path),
            "taxpar_path": str(taxpar_path),
            "structures_path": None if structures_path is None else str(structures_path),
            "assess_fy_from_filename": filename_fy,
            # The FY column wins; a mismatch is recorded, not resolved, because
            # it means the extract and its filename disagree and a human should
            # look at it.
            "assess_fy_agrees_with_filename": (
                filename_fy is None or gdf.attrs.get("assess_fy") == filename_fy
            ),
            "load_seconds": round(time.perf_counter() - started, 3),
        }
    )
    return gdf


def summarise(gdf: gpd.GeoDataFrame) -> dict[str, object]:
    """What the load did, in the shape a method page or a log line can print."""
    attrs = gdf.attrs
    source = gdf["source"].fillna("").value_counts()
    confidence = gdf["confidence"].fillna("").value_counts()
    sqft = pd.to_numeric(gdf["sqft"], errors="coerce")

    return {
        "town_id": attrs.get("town_id"),
        "assess_fy": attrs.get("assess_fy"),
        "assess_fy_from_filename": attrs.get("assess_fy_from_filename"),
        "assess_records_total": attrs.get("assess_records_total"),
        "parcels": int(len(gdf)),
        "scoreable_records": attrs.get("scoreable_records"),
        "collapsed_away_records": attrs.get("collapsed_away_records"),
        "excluded_records": attrs.get("excluded_records"),
        "excluded_parcels": attrs.get("excluded_parcels"),
        "out_of_class_records": attrs.get("out_of_class_records"),
        "unbuilt_use_code_records": attrs.get("unbuilt_use_code_records"),
        "blank_loc_id_records": attrs.get("blank_loc_id_records"),
        "blank_loc_id_in_class_records": attrs.get("blank_loc_id_in_class_records"),
        "blank_loc_id_in_class_sqft": attrs.get("blank_loc_id_in_class_sqft"),
        "use_codes_in_scope": attrs.get("use_codes_in_scope"),
        "total_sqft": float(sqft.sum()),
        "median_sqft": float(sqft.median()) if sqft.notna().any() else 0.0,
        "sqft_over_single_meter_cap": int(sqft.gt(LIKELY_SINGLE_METERED_MAX_SQFT).sum()),
        "source_split": {
            "comstock": int(source.get("comstock", 0)),
            "modeled": int(source.get("modeled", 0)),
        },
        "confidence": {
            "HIGH": int(confidence.get("HIGH", 0)),
            "MED": int(confidence.get("MED", 0)),
            "LOW": int(confidence.get("LOW", 0)),
        },
        "multi_use_parcels": int(gdf["multi_use"].fillna(False).sum()),
        "missing_geometry": attrs.get("missing_geometry"),
        "load_seconds": attrs.get("load_seconds"),
    }
