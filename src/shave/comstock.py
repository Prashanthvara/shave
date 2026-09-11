"""Measured load shapes from NREL ComStock, read in place on S3.

The parquet is queried where it sits with DuckDB's httpfs extension rather
than downloaded. MA's individual-building partition is 3,595 files; pulling it
locally would cost gigabytes and a caching problem, and the scorer reads about
0.2% of what is in there.

Two partition schemes, and they do not match. Metadata is partitioned by
county, so a building's type and floor area come from a county file. The
timeseries is partitioned by state, so the profile for a given building comes
from the state directory. The extractor resolves ids from the first and reads
rows from the second.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .archetype import INTERVALS_PER_BILLED_DAY
from .assumptions import (
    COMSTOCK_RELEASE,
    COMSTOCK_S3_BASE,
    COMSTOCK_STATE,
    COMSTOCK_UPGRADE,
    INTERVAL_MINUTES,
    PEAK_HOUR_START,
)
from .billing_window import billed_mask

# Worcester County, FIPS 25027, in NHGIS GISJOIN form.
WORCESTER_COUNTY_GISJOIN = "G2500270"

# ComStock reports energy consumed during each interval, in kWh. Average power
# over the interval is energy divided by duration.
KWH_PER_INTERVAL_TO_KW = 60.0 / INTERVAL_MINUTES

TOTAL_ELECTRICITY_COL = "out.electricity.total.energy_consumption"

_RELEASE_ROOT = f"{COMSTOCK_S3_BASE}/{COMSTOCK_RELEASE}"


def county_metadata_path(county_gisjoin: str) -> str:
    """Path to one county's baseline metadata parquet."""
    return (
        f"{_RELEASE_ROOT}/metadata_and_annual_results/by_state_and_county"
        f"/basic/parquet/state={COMSTOCK_STATE}/county={county_gisjoin}"
        f"/{COMSTOCK_STATE}_{county_gisjoin}_baseline_basic.parquet"
    )


def timeseries_path(bldg_id: int) -> str:
    """Path to one building's 15-minute timeseries parquet."""
    return (
        f"{_RELEASE_ROOT}/timeseries_individual_buildings/by_state"
        f"/upgrade={COMSTOCK_UPGRADE}/state={COMSTOCK_STATE}"
        f"/{int(bldg_id)}-{COMSTOCK_UPGRADE}.parquet"
    )


def connect() -> duckdb.DuckDBPyConnection:
    """A DuckDB connection configured for anonymous reads of the OEDI bucket."""
    conn = duckdb.connect()
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute("SET s3_region='us-west-2';")
    return conn


def load_county_index(
    county_gisjoin: str = WORCESTER_COUNTY_GISJOIN,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Building id, ComStock type and floor area for one county.

    One row per building. The DISTINCT is not cosmetic: the county metadata
    parquet carries one row per (building, census tract), because ComStock
    apportions each simulated building across the tracts it stands in and
    gives each share its own stock-expansion `weight`. Worcester County is
    19,077 such rows over 2,443 distinct buildings -- one building reaches 116
    rows. Verified on the file: building type and floor area are constant
    within a bldg_id, so collapsing to distinct buildings loses nothing these
    three columns carry. What it does drop is `weight` and the tract geography;
    anything that needs to weight results back up to the real building stock
    has to go back to the parquet for them.

    Without the DISTINCT a caller iterating this index would fetch the same
    35,040-row timeseries file from S3 up to 116 times.
    """
    own = conn is None
    conn = conn or connect()
    try:
        df = conn.execute(
            f"""
            SELECT DISTINCT
                   bldg_id::BIGINT              AS bldg_id,
                   "in.comstock_building_type"  AS building_type,
                   "in.sqft..ft2"::DOUBLE       AS sqft
            FROM read_parquet('{county_metadata_path(county_gisjoin)}')
            WHERE upgrade = {COMSTOCK_UPGRADE}
            ORDER BY bldg_id
            """
        ).fetchdf()
    finally:
        if own:
            conn.close()
    return df


# Below this many buildings of a type in a county, the median is arbitrary and
# selection widens to the whole state. Hospital has 2 in Worcester County.
MIN_COHORT = 30


class ComStockError(RuntimeError):
    """ComStock cannot supply a shape for what was asked."""


@dataclass(frozen=True)
class Representative:
    bldg_id: int
    building_type: str
    sqft: float
    cohort_size: int
    widened: bool


def select_representative(
    index: pd.DataFrame,
    building_type: str,
    min_cohort: int = MIN_COHORT,
) -> Representative:
    """The median-floor-area building of its type, as that type's shape.

    Ties and even cohorts take the lower middle rather than interpolating, so
    the result is always a real building that can be cited by id.
    """
    cohort = index[index["building_type"] == building_type]
    if cohort.empty:
        raise ComStockError(
            f"no ComStock buildings of type {building_type!r} in this index"
        )

    ordered = cohort.sort_values(["sqft", "bldg_id"], kind="stable")
    middle = (len(ordered) - 1) // 2  # lower middle for even counts
    row = ordered.iloc[middle]

    return Representative(
        bldg_id=int(row["bldg_id"]),
        building_type=building_type,
        sqft=float(row["sqft"]),
        cohort_size=len(ordered),
        widened=len(ordered) < min_cohort,
    )


@dataclass(frozen=True)
class ReducedProfile:
    """A building's billed peak shape: twelve monthly peaks, twelve windows.

    Reduces the 35,040-row raw timeseries to what the scorer actually reads --
    about 0.2% of the input -- by masking to the billed window first (see
    `billing_window.billed_mask`) and keeping only each month's peak value and
    its worst billed day's 52-interval shape.
    """

    bldg_id: int
    monthly_peak_kw: np.ndarray   # (12,)
    windows: np.ndarray           # (12, INTERVALS_PER_BILLED_DAY)
    sqft: float | None = None
    # Carried from the Representative that produced this profile, so a
    # thin-cohort shape (e.g. Hospital, 2 buildings in Worcester County)
    # stays visible to anything downstream, including after a cache round
    # trip. Absent on profiles built directly by reduce_from_frame/
    # reduce_timeseries, which know nothing about cohort selection.
    widened: bool = False
    cohort_size: int | None = None

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "bldg_id": np.repeat(self.bldg_id, 12),
            "month": np.arange(1, 13),
            "monthly_peak_kw": self.monthly_peak_kw,
            "sqft": np.repeat(np.nan if self.sqft is None else self.sqft, 12),
            "widened": np.repeat(self.widened, 12),
            "cohort_size": np.repeat(
                np.nan if self.cohort_size is None else self.cohort_size, 12
            ),
            **{f"i{i:02d}": self.windows[:, i] for i in range(INTERVALS_PER_BILLED_DAY)},
        })

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "ReducedProfile":
        df = df.sort_values("month")
        cols = [f"i{i:02d}" for i in range(INTERVALS_PER_BILLED_DAY)]
        sqft = float(df["sqft"].iloc[0])
        # Older cached/fixture frames predate these two columns; default them
        # rather than raising, so a pre-existing cache is not a hard break.
        if "widened" in df.columns:
            widened = bool(df["widened"].iloc[0])
        else:
            widened = False
        if "cohort_size" in df.columns:
            raw_cohort = df["cohort_size"].iloc[0]
            cohort_size = None if pd.isna(raw_cohort) else int(raw_cohort)
        else:
            cohort_size = None
        return cls(
            bldg_id=int(df["bldg_id"].iloc[0]),
            monthly_peak_kw=df["monthly_peak_kw"].to_numpy(dtype=float),
            windows=df[cols].to_numpy(dtype=float),
            sqft=None if np.isnan(sqft) else sqft,
            widened=widened,
            cohort_size=cohort_size,
        )


def reduce_from_frame(
    bldg_id: int, raw: pd.DataFrame, sqft: float | None = None
) -> ReducedProfile:
    """Twelve monthly peaks and twelve peak-day windows, billed intervals only."""
    ts = pd.DatetimeIndex(raw["timestamp"])
    kw = raw[TOTAL_ELECTRICITY_COL].to_numpy(dtype=float) * KWH_PER_INTERVAL_TO_KW

    keep = billed_mask(ts)
    ts, kw = ts[keep], kw[keep]

    month = ts.month.to_numpy()
    day = ts.normalize().to_numpy(dtype="datetime64[s]")

    # Position within the billed window, derived so the window length is never
    # assumed. billing_window guarantees these are all inside the peak period.
    slot = ((ts.hour.to_numpy() - PEAK_HOUR_START) * 60
            + ts.minute.to_numpy()) // INTERVAL_MINUTES

    peaks = np.zeros(12)
    windows = np.zeros((12, INTERVALS_PER_BILLED_DAY))

    for m in range(1, 13):
        sel = month == m
        if not sel.any():
            raise ComStockError(f"building {bldg_id}: no billed intervals in month {m}")
        m_kw, m_day, m_slot = kw[sel], day[sel], slot[sel]
        peaks[m - 1] = m_kw.max()

        # The day whose own maximum is highest is that month's peak day.
        days, inverse = np.unique(m_day, return_inverse=True)
        per_day_max = np.zeros(len(days))
        np.maximum.at(per_day_max, inverse, m_kw)
        worst = inverse == int(per_day_max.argmax())
        windows[m - 1, m_slot[worst]] = m_kw[worst]

    return ReducedProfile(int(bldg_id), peaks, windows, sqft)


def reduce_timeseries(
    bldg_id: int,
    conn: duckdb.DuckDBPyConnection | None = None,
    sqft: float | None = None,
) -> ReducedProfile:
    """Read one building's timeseries from S3 and reduce it."""
    own = conn is None
    conn = conn or connect()
    try:
        raw = conn.execute(
            f'''SELECT timestamp, "{TOTAL_ELECTRICITY_COL}"
                FROM read_parquet('{timeseries_path(bldg_id)}')
                ORDER BY timestamp'''
        ).fetchdf()
    finally:
        if own:
            conn.close()
    if raw.empty:
        raise ComStockError(f"building {bldg_id}: timeseries is empty")
    return reduce_from_frame(bldg_id, raw, sqft)


CACHE_DIR = Path("data/interim/comstock")

# Crosswalk archetype name to ComStock's in.comstock_building_type value.
# The crosswalk's `office` family is resolved to a size band by
# crosswalk.resolve_office_band before it reaches here.
ARCHETYPE_TO_COMSTOCK: dict[str, str] = {
    "small_office": "SmallOffice",
    "medium_office": "MediumOffice",
    "large_office": "LargeOffice",
    "retail_standalone": "RetailStandalone",
    "strip_mall": "RetailStripmall",
    "warehouse": "Warehouse",
    "full_service_restaurant": "FullServiceRestaurant",
    "quick_service_restaurant": "QuickServiceRestaurant",
    "primary_school": "PrimarySchool",
    "secondary_school": "SecondarySchool",
    "hospital": "Hospital",
    "outpatient": "Outpatient",
    "large_hotel": "LargeHotel",
    "small_hotel": "SmallHotel",
}


@dataclass
class ComStockArchetype:
    """A measured profile, scaled to one parcel's floor area.

    The representative building has its own floor area. A parcel's profile is
    the representative's, scaled linearly by parcel_sqft / representative_sqft.
    Shape comes from the measured building; magnitude comes from the parcel.

    `widened` and `cohort_size` carry the thin-cohort flag from the
    Representative that produced this archetype's profile (see
    select_representative). Hospital has exactly 2 buildings in Worcester
    County, so its shape is the median of 2 -- anything consuming this
    archetype can see that instead of it being silently discarded.
    """

    profile: ReducedProfile
    sqft: float
    source: str = "comstock"
    widened: bool = False
    cohort_size: int | None = None

    @property
    def _scale(self) -> float:
        base = self.profile.sqft
        if not base:
            raise ComStockError(
                f"building {self.profile.bldg_id} has no floor area; cannot scale"
            )
        return self.sqft / base

    def monthly_peaks(self) -> np.ndarray:
        return self.profile.monthly_peak_kw * self._scale

    def peak_day_window(self, month: int) -> np.ndarray:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        return self.profile.windows[month - 1] * self._scale


def build_archetype(
    archetype_name: str,
    sqft: float,
    county_gisjoin: str = WORCESTER_COUNTY_GISJOIN,
    cache_dir: Path | str = CACHE_DIR,
) -> ComStockArchetype:
    """The measured archetype for a crosswalk name, cached to local parquet.

    One network round trip per (archetype, county), not per parcel. The
    Representative's widened/cohort_size travel with the cached profile, so a
    cache hit reports the same thin-cohort flag a cache miss would have
    computed rather than silently reverting to the dataclass default.
    """
    if archetype_name not in ARCHETYPE_TO_COMSTOCK:
        raise ComStockError(
            f"{archetype_name!r} has no ComStock type. ComStock models 14 "
            "building types; anything else must be a modeled archetype."
        )
    cache_dir = Path(cache_dir)
    cached = cache_dir / f"{archetype_name}__{county_gisjoin}.parquet"

    if cached.exists():
        profile = ReducedProfile.from_frame(pd.read_parquet(cached))
    else:
        conn = connect()
        try:
            index = load_county_index(county_gisjoin, conn=conn)
            rep = select_representative(index, ARCHETYPE_TO_COMSTOCK[archetype_name])
            profile = reduce_timeseries(rep.bldg_id, conn=conn, sqft=rep.sqft)
        finally:
            conn.close()
        profile = replace(profile, widened=rep.widened, cohort_size=rep.cohort_size)
        cache_dir.mkdir(parents=True, exist_ok=True)
        profile.to_frame().to_parquet(cached)

    return ComStockArchetype(
        profile=profile,
        sqft=sqft,
        widened=profile.widened,
        cohort_size=profile.cohort_size,
    )
