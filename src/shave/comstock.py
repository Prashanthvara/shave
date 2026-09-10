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

import duckdb
import pandas as pd

from .assumptions import (
    COMSTOCK_RELEASE,
    COMSTOCK_S3_BASE,
    COMSTOCK_STATE,
    COMSTOCK_UPGRADE,
    INTERVAL_MINUTES,
)

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
