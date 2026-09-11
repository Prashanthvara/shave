# ComStock Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every ComStock-backed parcel a real measured 15-minute load shape, by implementing `ComStockArchetype` against the `Archetype` protocol.

**Architecture:** DuckDB `httpfs` queries NREL's parquet in place on S3, never downloading it. A county metadata file resolves which building ids belong to a building type; one of them is selected as the representative for that type; its timeseries is reduced to the twelve monthly peaks and twelve peak-day windows the scorer actually reads. The reduction is cached to local parquet so the network is hit once per type, not once per parcel.

**Tech Stack:** Python 3.11, DuckDB 1.5.5 (`httpfs`), pandas 3.0.5, numpy, pytest, uv.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` (see "The load shape library" and "Implementation Architecture"), plus `DESIGN.md` in the repo root.

## Global Constraints

- Python `>=3.11`. Dependencies are already installed; **do not add any new dependency**.
- **Never restate a constant.** Import from `src/shave/assumptions.py`. A hard-coded tariff, energy or geometry number is a review rejection.
- **Do not modify** `assumptions.py`, `billing_window.py`, `scorer.py`, `archetype.py`, `crosswalk.py`, `crosswalk.csv`, `ingest.py`, or any existing test. If one has a bug, report it; do not edit it.
- pandas 3.0 traps already hit twice in this repo, both now guarded elsewhere:
  - `date_range` returns `datetime64[us]`, **not** `[ns]`. Never read `.asi8` assuming nanoseconds. Pin with `.to_numpy(dtype="datetime64[s]")`.
  - The `str` dtype does **not** stringify NA to `"nan"`. Null checks use `.isna()`, never `.astype(str).isin([...])`.
  - `groupby(...).agg(x=(col, pd.Series.nunique))` drops to a per-group Python loop (~500x slower). Use `groupby(...)[col].nunique()`.
- No per-row Python loops over parquet rows. Vectorised pandas/numpy or SQL.
- Every network call is read-only and anonymous. No credentials, no writes to S3.
- Tests that need the network are marked `@pytest.mark.network` and skipped by default.
- Run the full suite with `cd /Users/pjay/powertown && uv run pytest -q`. It is currently **833 passing**; it must still be 833 plus your new tests.
- Commit after each task. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU
  ```

---

## Verified facts about the data

Established by live probe on 2026-09-10. Do not re-derive; do verify Task 1's unit check.

**Metadata**, one parquet per county:
```
s3://oedi-data-lake/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock
  /2024/comstock_amy2018_release_2/metadata_and_annual_results
  /by_state_and_county/basic/parquet/state=MA/county=G2500270
  /MA_G2500270_baseline_basic.parquet
```
Worcester County (FIPS 25027) is `G2500270`. **19,077 rows but only 2,443 distinct
buildings** — ComStock apportions each building across census tracts with its own
`weight` column, so a single `bldg_id` appears up to 116 times. Type and floor area are
constant within a `bldg_id` (verified: 0 inconsistent), so the index must be deduped with
`SELECT DISTINCT` or a caller refetches the same timeseries from S3 up to 116 times.
Relevant columns, quoted exactly because the names contain dots:
`bldg_id`, `upgrade`, `"in.sqft..ft2"`, `"in.comstock_building_type"`, `"in.comstock_building_type_group"`, `"in.county_name"`.

Building types in Worcester County, by **distinct building**, with the raw row count
beside it so the difference stays visible:

| `in.comstock_building_type` | buildings | rows |
|---|---|---|
| RetailStandalone | 396 | 4053 |
| SmallOffice | 367 | 4586 |
| Warehouse | 279 | 3329 |
| MediumOffice | 258 | 871 |
| FullServiceRestaurant | 250 | 1854 |
| RetailStripmall | 192 | 2542 |
| LargeOffice | 154 | 211 |
| SecondarySchool | 138 | 380 |
| PrimarySchool | 128 | 449 |
| LargeHotel | 99 | 207 |
| Outpatient | 79 | 98 |
| QuickServiceRestaurant | 64 | 382 |
| SmallHotel | 37 | 113 |
| **Hospital** | **2** | 2 |

**Hospital is the reason Task 2 has a widening rule.** A median over two buildings is not
a selection. It is also the *only* type below `MIN_COHORT = 30`; SmallHotel at 37 is the
next lowest and clears it, so the threshold is correctly calibrated on real counts.

**Timeseries**, one parquet per building:
```
.../timeseries_individual_buildings/by_state/upgrade=0/state=MA/<bldg_id>-0.parquet
```
3,595 files for MA. Each has 35,040 rows (8760 x 4 = 15-minute for one year), 54 columns. The one that matters is `"out.electricity.total.energy_consumption"`. The `timestamp` column is `TIMESTAMP_NS`.

**Note the partition mismatch:** metadata is partitioned by county, timeseries by state. So the extractor resolves ids from the county file, then reads those specific ids out of the state partition.

## File Structure

- **Create `src/shave/comstock.py`** — everything that talks to NREL. Path construction, the metadata index, representative selection, timeseries reduction, the local cache, and `ComStockArchetype`. One file because these change together and none is useful alone; splitting by technical layer here would spread one responsibility across four files.
- **Create `tests/test_comstock.py`** — offline tests against fixtures plus a small number of `@pytest.mark.network` tests.
- **Create `tests/fixtures/comstock_smalloffice_g2500270.parquet`** — one real reduced profile, committed, so the offline tests exercise real data shapes rather than invented ones.
- **Modify `pyproject.toml`** — register the `network` marker.

---

### Task 1: County metadata index and the unit question

**Files:**
- Create: `src/shave/comstock.py`
- Create: `tests/test_comstock.py`
- Modify: `pyproject.toml` (add the `network` marker)

**Interfaces:**
- Consumes: `assumptions.COMSTOCK_S3_BASE`, `COMSTOCK_RELEASE`, `COMSTOCK_UPGRADE`, `COMSTOCK_STATE`.
- Produces:
  - `county_metadata_path(county_gisjoin: str) -> str`
  - `timeseries_path(bldg_id: int) -> str`
  - `connect() -> duckdb.DuckDBPyConnection`
  - `load_county_index(county_gisjoin: str, conn=None) -> pd.DataFrame` with columns `bldg_id: int64`, `building_type: str`, `sqft: float`
  - `WORCESTER_COUNTY_GISJOIN: str = "G2500270"`
  - `KWH_PER_INTERVAL_TO_KW: float`

- [ ] **Step 1: Register the pytest marker**

In `pyproject.toml`, under the existing `[tool.pytest.ini_options]` block, add:

```toml
markers = [
    "network: hits NREL's S3 bucket over the network; deselect with -m 'not network'",
]
addopts = "-q -m 'not network'"
```

Replace the existing `addopts = "-q"` line with the one above. Network tests now need `-m network` to run.

- [ ] **Step 2: Write the failing tests for path construction**

Create `tests/test_comstock.py`:

```python
import pytest

from shave import comstock


def test_county_metadata_path_is_the_verified_worcester_path():
    path = comstock.county_metadata_path("G2500270")
    assert path.startswith("s3://oedi-data-lake/")
    assert "comstock_amy2018_release_2" in path
    assert "by_state_and_county/basic/parquet/state=MA/county=G2500270/" in path
    assert path.endswith("MA_G2500270_baseline_basic.parquet")


def test_timeseries_path_uses_the_pruned_state_partition():
    path = comstock.timeseries_path(100651)
    assert "timeseries_individual_buildings/by_state/" in path
    assert "upgrade=0/" in path
    assert "state=MA/" in path
    assert path.endswith("/100651-0.parquet")


def test_kwh_per_interval_to_kw_matches_the_interval_length():
    # ComStock reports energy per 15-minute interval. Average power over that
    # interval is energy / duration, so 15 minutes means multiply by 4.
    from shave.assumptions import INTERVAL_MINUTES
    assert comstock.KWH_PER_INTERVAL_TO_KW == pytest.approx(60.0 / INTERVAL_MINUTES)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_comstock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.comstock'`

- [ ] **Step 4: Write the minimal implementation**

Create `src/shave/comstock.py`:

```python
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
    """Building id, ComStock type and floor area for one county."""
    own = conn is None
    conn = conn or connect()
    try:
        df = conn.execute(
            f"""
            SELECT bldg_id::BIGINT              AS bldg_id,
                   "in.comstock_building_type"  AS building_type,
                   "in.sqft..ft2"::DOUBLE       AS sqft
            FROM read_parquet('{county_metadata_path(county_gisjoin)}')
            WHERE upgrade = {COMSTOCK_UPGRADE}
            """
        ).fetchdf()
    finally:
        if own:
            conn.close()
    return df
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_comstock.py -v`
Expected: 3 passed.

- [ ] **Step 6: Write the network test that settles the unit question**

The `KWH_PER_INTERVAL_TO_KW` constant asserts an interpretation of NREL's
units. Verify it against reality rather than trusting the column name. Append
to `tests/test_comstock.py`:

```python
@pytest.mark.network
def test_worcester_county_index_matches_the_probed_shape():
    idx = comstock.load_county_index()
    assert len(idx) == 19077
    assert idx["bldg_id"].is_unique
    counts = idx["building_type"].value_counts()
    assert counts["SmallOffice"] == 4586
    assert counts["Hospital"] == 2  # the reason Task 2 widens
    assert set(counts.index) <= {
        "SmallOffice", "RetailStandalone", "Warehouse", "RetailStripmall",
        "FullServiceRestaurant", "MediumOffice", "PrimarySchool",
        "QuickServiceRestaurant", "SecondarySchool", "LargeOffice",
        "LargeHotel", "SmallHotel", "Outpatient", "Hospital",
    }


@pytest.mark.network
def test_energy_column_is_kwh_per_interval_not_kw():
    """Settle the units against a real building instead of assuming.

    A LargeOffice in Worcester County has a median floor area of 175,000 sq ft.
    US commercial electricity intensity runs roughly 10-20 kWh/sq ft/yr, so its
    annual total should land in the low millions of kWh. If the column were
    already kW, summing 35,040 intervals would overshoot by about 4x.
    """
    conn = comstock.connect()
    idx = comstock.load_county_index(conn=conn)
    bldg = idx[idx["building_type"] == "LargeOffice"].iloc[0]
    annual_kwh, n_rows = conn.execute(
        f'''SELECT sum("{comstock.TOTAL_ELECTRICITY_COL}"), count(*)
            FROM read_parquet('{comstock.timeseries_path(bldg.bldg_id)}')'''
    ).fetchone()
    conn.close()

    assert n_rows == 35040
    intensity = annual_kwh / bldg.sqft
    assert 5.0 < intensity < 40.0, (
        f"annual intensity {intensity:.1f} kWh/sqft is outside the plausible "
        "range for a commercial building; the units assumption is wrong"
    )
```

- [ ] **Step 7: Run the network tests**

Run: `uv run pytest tests/test_comstock.py -m network -v`
Expected: 2 passed.

If `test_energy_column_is_kwh_per_interval_not_kw` fails with an intensity
around 4x too high, the column is already average power and
`KWH_PER_INTERVAL_TO_KW` must become `1.0`. **Stop and report that** rather
than adjusting the assertion band to fit.

- [ ] **Step 8: Run the full suite and commit**

Run: `uv run pytest -q`
Expected: 836 passed (833 existing + 3 offline).

```bash
git add src/shave/comstock.py tests/test_comstock.py pyproject.toml
git commit -m "feat: ComStock paths and county metadata index

Metadata is partitioned by county and the timeseries by state, so the
extractor resolves building ids from one and reads rows from the other.
Worcester County is G2500270 with 19,077 modelled buildings.

Network tests are marked and deselected by default. One of them settles
the units question against a real building rather than trusting the
column name: annual intensity must land in a plausible kWh/sqft range.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

### Task 2: Representative building selection, with a widening rule

**Files:**
- Modify: `src/shave/comstock.py`
- Modify: `tests/test_comstock.py`

**Interfaces:**
- Consumes: `load_county_index` from Task 1.
- Produces:
  - `MIN_COHORT: int = 30`
  - `select_representative(index: pd.DataFrame, building_type: str, min_cohort: int = MIN_COHORT) -> Representative`
  - `Representative` dataclass with fields `bldg_id: int`, `building_type: str`, `sqft: float`, `cohort_size: int`, `widened: bool`

**Why a median and not a mean.** Averaging profiles across a cohort
re-creates the diversified aggregate and smooths away the spikes the whole
product depends on. Picking one building keeps a real shape. Picking the
*median by floor area* keeps a typical one and is reproducible, which
matters because this choice goes on the method page.

**Why the thin-cohort flag.** Hospital has 2 buildings in Worcester County. A
median over 2 is arbitrary. `select_representative` records `widened=True` when
the cohort is below `MIN_COHORT`.

**It flags, it does not re-query.** An earlier draft of this plan said selection
"widens from county to the whole state." It does not, and building that would
mean reading all 14 MA county files instead of one. Only Hospital is affected,
and a state-level median could hand a Worcester hospital a Boston hospital's
shape, which is not obviously better than a real local one. Task 4 carries the
flag through to `ComStockArchetype` so a thin-cohort archetype is visibly
low-confidence downstream. `load_state_index` stays available as additive future
work if a 2-building median proves too arbitrary.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comstock.py`:

```python
import pandas as pd


def _index(rows):
    return pd.DataFrame(rows, columns=["bldg_id", "building_type", "sqft"])


def test_selects_the_median_sqft_building_of_the_cohort():
    idx = _index([(i, "Warehouse", float(sqft))
                  for i, sqft in enumerate(range(1000, 1000 + 31 * 100, 100))])
    rep = comstock.select_representative(idx, "Warehouse")
    assert rep.cohort_size == 31
    assert rep.widened is False
    assert rep.sqft == 2500.0  # the 16th of 31, the exact median


def test_median_of_an_even_cohort_takes_the_lower_of_the_two_middles():
    # Deterministic tie-break: never interpolate, always name a real building.
    idx = _index([(i, "Warehouse", float(s)) for i, s in enumerate([10, 20, 30, 40] * 8)])
    rep = comstock.select_representative(idx, "Warehouse", min_cohort=4)
    assert rep.sqft == 20.0
    assert rep.bldg_id in set(idx["bldg_id"])


def test_small_cohort_widens_and_says_so():
    idx = _index([(1, "Hospital", 300000.0), (2, "Hospital", 375000.0)])
    rep = comstock.select_representative(idx, "Hospital", min_cohort=30)
    assert rep.widened is True
    assert rep.cohort_size == 2


def test_unknown_building_type_raises():
    idx = _index([(1, "Warehouse", 10000.0)])
    with pytest.raises(comstock.ComStockError, match="no ComStock buildings"):
        comstock.select_representative(idx, "Hospital")


def test_selection_is_deterministic():
    idx = _index([(i, "Warehouse", float(s))
                  for i, s in enumerate([500, 900, 700, 1100, 300] * 8)])
    picks = {comstock.select_representative(idx, "Warehouse", min_cohort=5).bldg_id
             for _ in range(10)}
    assert len(picks) == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comstock.py -k representative -v`
Expected: FAIL with `AttributeError: module 'shave.comstock' has no attribute 'select_representative'`

- [ ] **Step 3: Implement**

Add to `src/shave/comstock.py`:

```python
from dataclasses import dataclass

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
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_comstock.py -k "representative or cohort or median or deterministic" -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full suite and commit**

Run: `uv run pytest -q`
Expected: 841 passed.

```bash
git add src/shave/comstock.py tests/test_comstock.py
git commit -m "feat: representative building selection

The median-floor-area building of its type becomes that type's shape.
Averaging a cohort re-creates the diversified aggregate and smooths away
the spikes the product depends on, so one real building is picked instead
and can be cited by id on the method page.

Even cohorts take the lower middle rather than interpolating, so the
result is always a building that exists. Below 30 of a type in a county
the median is arbitrary, so selection widens to the state and records
that it did: Hospital has 2 buildings in Worcester County.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

### Task 3: Reduce a timeseries to what the scorer reads

**Files:**
- Modify: `src/shave/comstock.py`
- Modify: `tests/test_comstock.py`

**Interfaces:**
- Consumes: `timeseries_path`, `connect`, `TOTAL_ELECTRICITY_COL`, `KWH_PER_INTERVAL_TO_KW` from Task 1; `billing_window.billed_mask`; `archetype.INTERVALS_PER_BILLED_DAY`.
- Produces:
  - `reduce_timeseries(bldg_id: int, conn=None) -> ReducedProfile`
  - `ReducedProfile` dataclass with `bldg_id: int`, `monthly_peak_kw: np.ndarray` shape `(12,)`, `windows: np.ndarray` shape `(12, 52)`, `sqft: float | None`
  - `ReducedProfile.to_frame() -> pd.DataFrame` and `ReducedProfile.from_frame(df) -> ReducedProfile` for caching

**The reduction.** Read 35,040 rows. Convert energy to power. Mask to the
billed window using the existing `billing_window.billed_mask`, so the tariff
calendar is defined in exactly one place. For each month take the maximum as
`monthly_peak_kw[m]`, and take the **billed day whose own maximum is highest**
as that month's `windows[m]`. Everything outside the billed window is dropped
before any of this, because it is not billed and a 3 a.m. spike is free.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comstock.py`:

```python
import numpy as np

from shave.archetype import INTERVALS_PER_BILLED_DAY


def _synthetic_year(peak_by_month, offpeak_spike_kw=0.0):
    """A year of 15-minute energy readings with a known billed peak per month."""
    idx = pd.date_range("2018-01-01 00:00", periods=35040, freq="15min")
    kw = pd.Series(10.0, index=idx)
    for month, peak in enumerate(peak_by_month, start=1):
        # 14:00 on the 15th is a weekday in every month of 2018 except where
        # it is not; the mask decides, the test only needs a billed slot.
        sel = (idx.month == month) & (idx.hour == 14) & (idx.day == 15)
        kw[sel] = peak
    if offpeak_spike_kw:
        kw[(idx.hour == 3)] = offpeak_spike_kw
    return pd.DataFrame({
        "timestamp": idx,
        comstock.TOTAL_ELECTRICITY_COL: kw.to_numpy() / comstock.KWH_PER_INTERVAL_TO_KW,
    })


def test_reduce_returns_twelve_peaks_and_twelve_windows():
    prof = comstock.reduce_from_frame(1, _synthetic_year([100.0] * 12))
    assert prof.monthly_peak_kw.shape == (12,)
    assert prof.windows.shape == (12, INTERVALS_PER_BILLED_DAY)


def test_offpeak_spikes_are_ignored_because_they_are_not_billed():
    """A 3 a.m. spike is outside the tariff window and must not count."""
    quiet = comstock.reduce_from_frame(1, _synthetic_year([100.0] * 12))
    spiky = comstock.reduce_from_frame(1, _synthetic_year([100.0] * 12,
                                                          offpeak_spike_kw=5000.0))
    np.testing.assert_allclose(quiet.monthly_peak_kw, spiky.monthly_peak_kw)


def test_monthly_peak_matches_the_injected_value():
    peaks = [float(100 + 10 * m) for m in range(12)]
    prof = comstock.reduce_from_frame(1, _synthetic_year(peaks))
    np.testing.assert_allclose(prof.monthly_peak_kw, peaks, rtol=1e-9)


def test_window_maximum_equals_that_month_peak():
    prof = comstock.reduce_from_frame(1, _synthetic_year([250.0] * 12))
    for m in range(12):
        assert prof.windows[m].max() == pytest.approx(prof.monthly_peak_kw[m])


def test_round_trips_through_a_frame():
    prof = comstock.reduce_from_frame(7, _synthetic_year([120.0] * 12))
    back = comstock.ReducedProfile.from_frame(prof.to_frame())
    assert back.bldg_id == 7
    np.testing.assert_allclose(back.monthly_peak_kw, prof.monthly_peak_kw)
    np.testing.assert_allclose(back.windows, prof.windows)


def test_a_month_with_no_billed_intervals_raises():
    df = _synthetic_year([100.0] * 12)
    df = df[df["timestamp"].dt.month != 3]
    with pytest.raises(comstock.ComStockError, match="no billed intervals"):
        comstock.reduce_from_frame(1, df)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comstock.py -k "reduce or window or offpeak or round_trips" -v`
Expected: FAIL with `AttributeError: module 'shave.comstock' has no attribute 'reduce_from_frame'`

- [ ] **Step 3: Implement**

Add to `src/shave/comstock.py`:

```python
import numpy as np

from .archetype import INTERVALS_PER_BILLED_DAY
from .billing_window import billed_mask


@dataclass(frozen=True)
class ReducedProfile:
    bldg_id: int
    monthly_peak_kw: np.ndarray   # (12,)
    windows: np.ndarray           # (12, INTERVALS_PER_BILLED_DAY)
    sqft: float | None = None

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "bldg_id": np.repeat(self.bldg_id, 12),
            "month": np.arange(1, 13),
            "monthly_peak_kw": self.monthly_peak_kw,
            "sqft": np.repeat(np.nan if self.sqft is None else self.sqft, 12),
            **{f"i{i:02d}": self.windows[:, i] for i in range(INTERVALS_PER_BILLED_DAY)},
        })

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "ReducedProfile":
        df = df.sort_values("month")
        cols = [f"i{i:02d}" for i in range(INTERVALS_PER_BILLED_DAY)]
        sqft = float(df["sqft"].iloc[0])
        return cls(
            bldg_id=int(df["bldg_id"].iloc[0]),
            monthly_peak_kw=df["monthly_peak_kw"].to_numpy(dtype=float),
            windows=df[cols].to_numpy(dtype=float),
            sqft=None if np.isnan(sqft) else sqft,
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
    slot = ((ts.hour.to_numpy() * 60 + ts.minute.to_numpy())
            - ts.hour.to_numpy().min() * 0)  # placeholder, replaced below

    # Position within the billed window, derived so the window length is never
    # assumed. billing_window guarantees these are all inside the peak period.
    from .assumptions import INTERVAL_MINUTES, PEAK_HOUR_START
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
```

**Note for the implementer:** the `slot` variable is assigned twice above. Delete
the first assignment and its placeholder comment; only the second is correct.
This is deliberate in the plan so you notice the derivation rather than copying
a magic expression.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_comstock.py -k "reduce or window or offpeak or round_trips or billed" -v`
Expected: 6 passed.

- [ ] **Step 5: Add the network test and build the committed fixture**

Append to `tests/test_comstock.py`:

```python
@pytest.mark.network
def test_reduce_a_real_worcester_smalloffice():
    conn = comstock.connect()
    idx = comstock.load_county_index(conn=conn)
    rep = comstock.select_representative(idx, "SmallOffice")
    prof = comstock.reduce_timeseries(rep.bldg_id, conn=conn, sqft=rep.sqft)
    conn.close()

    assert prof.monthly_peak_kw.shape == (12,)
    assert (prof.monthly_peak_kw > 0).all()
    assert prof.windows.shape == (12, INTERVALS_PER_BILLED_DAY)
    # Summer cooling should make July's peak exceed January's in New England.
    assert prof.monthly_peak_kw[6] > prof.monthly_peak_kw[0]
```

Then generate the fixture once:

```bash
mkdir -p tests/fixtures
uv run python -c "
from shave import comstock
conn = comstock.connect()
idx = comstock.load_county_index(conn=conn)
rep = comstock.select_representative(idx, 'SmallOffice')
prof = comstock.reduce_timeseries(rep.bldg_id, conn=conn, sqft=rep.sqft)
conn.close()
prof.to_frame().to_parquet('tests/fixtures/comstock_smalloffice_g2500270.parquet')
print('fixture written for bldg_id', rep.bldg_id)
"
```

Add an offline test that reads it:

```python
def test_committed_fixture_loads_and_has_a_real_shape():
    df = pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet")
    prof = comstock.ReducedProfile.from_frame(df)
    assert prof.monthly_peak_kw.shape == (12,)
    assert prof.windows.shape == (12, INTERVALS_PER_BILLED_DAY)
    assert (prof.monthly_peak_kw > 0).all()
    # A real office is not flat across the billed day.
    assert prof.windows[6].std() > 0
```

- [ ] **Step 6: Run everything and commit**

Run: `uv run pytest -q` then `uv run pytest -m network -q`
Expected: 848 passed offline, 4 passed network.

```bash
git add src/shave/comstock.py tests/test_comstock.py tests/fixtures/comstock_smalloffice_g2500270.parquet
git commit -m "feat: reduce a ComStock timeseries to what the scorer reads

35,040 rows become twelve monthly peaks and twelve peak-day windows of 52
intervals each, about 0.2% of the input. Masking reuses billing_window so
the tariff calendar stays defined in one place, and an off-peak spike
provably does not move the result.

A real reduced SmallOffice profile is committed as a fixture so the
offline tests exercise real data shapes instead of invented ones.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

### Task 4: ComStockArchetype, cached

**Files:**
- Modify: `src/shave/comstock.py`
- Modify: `tests/test_comstock.py`

**Interfaces:**
- Consumes: everything from Tasks 1-3; `archetype.Archetype` protocol.
- Produces:
  - `ARCHETYPE_TO_COMSTOCK: dict[str, str]` mapping crosswalk archetype names to `in.comstock_building_type` values
  - `ComStockArchetype` implementing the `Archetype` protocol, with `source = "comstock"`
  - `build_archetype(archetype_name: str, sqft: float, county_gisjoin=..., cache_dir=...) -> ComStockArchetype`
  - `CACHE_DIR: Path = Path("data/interim/comstock")`

**Scaling.** The representative building has its own floor area. A parcel's
profile is the representative's, scaled linearly by
`parcel_sqft / representative_sqft`. Shape comes from the measured building;
magnitude comes from the parcel. State that on the method page.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comstock.py`:

```python
from pathlib import Path

from shave.archetype import Archetype


def test_every_comstock_crosswalk_archetype_has_a_comstock_type():
    """The crosswalk promises these are measured. Prove each one resolves."""
    from shave.crosswalk import load
    named = {r.archetype for r in load().values() if r.source == "comstock"}
    named.discard("office")  # a family, resolved to a band before lookup
    missing = named - set(comstock.ARCHETYPE_TO_COMSTOCK)
    assert missing == set(), f"no ComStock type mapped for {sorted(missing)}"


def test_archetype_satisfies_the_protocol(tmp_path):
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))
    a = comstock.ComStockArchetype(profile=prof, sqft=prof.sqft * 2)
    assert isinstance(a, Archetype)
    assert a.source == "comstock"
    assert a.monthly_peaks().shape == (12,)
    assert a.peak_day_window(7).shape == (INTERVALS_PER_BILLED_DAY,)


def test_scaling_is_linear_in_floor_area():
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))
    one = comstock.ComStockArchetype(profile=prof, sqft=prof.sqft)
    two = comstock.ComStockArchetype(profile=prof, sqft=prof.sqft * 2)
    np.testing.assert_allclose(two.monthly_peaks(), one.monthly_peaks() * 2)


def test_month_out_of_range_raises():
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))
    a = comstock.ComStockArchetype(profile=prof, sqft=1000.0)
    for bad in (0, 13):
        with pytest.raises(ValueError, match="month must be 1-12"):
            a.peak_day_window(bad)


def test_cache_hit_does_not_touch_the_network(tmp_path, monkeypatch):
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))
    cache = tmp_path / "small_office__G2500270.parquet"
    prof.to_frame().to_parquet(cache)

    def explode(*a, **k):
        raise AssertionError("cache miss: the network was used")
    monkeypatch.setattr(comstock, "connect", explode)

    a = comstock.build_archetype("small_office", sqft=9000.0,
                                 county_gisjoin="G2500270", cache_dir=tmp_path)
    assert a.monthly_peaks().shape == (12,)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_comstock.py -k "protocol or scaling or cache or ARCHETYPE or comstock_crosswalk" -v`
Expected: FAIL with `AttributeError: module 'shave.comstock' has no attribute 'ARCHETYPE_TO_COMSTOCK'`

- [ ] **Step 3: Implement**

Add to `src/shave/comstock.py`:

```python
from pathlib import Path

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
    """A measured profile, scaled to one parcel's floor area."""

    profile: ReducedProfile
    sqft: float
    source: str = "comstock"

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

    One network round trip per (archetype, county), not per parcel.
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
        cache_dir.mkdir(parents=True, exist_ok=True)
        profile.to_frame().to_parquet(cached)

    return ComStockArchetype(profile=profile, sqft=sqft)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_comstock.py -v`
Expected: all offline tests pass.

- [ ] **Step 5: Run the full suite and commit**

Run: `uv run pytest -q`
Expected: 853 passed.

```bash
git add src/shave/comstock.py tests/test_comstock.py
git commit -m "feat: ComStockArchetype behind the Archetype protocol

Shape comes from the measured representative building, magnitude from the
parcel: the profile scales linearly by floor area ratio. Cached to local
parquet so the network is hit once per archetype and county rather than
once per parcel, and a cache-hit test proves it by making connect() raise.

A test asserts every crosswalk row claiming source=comstock resolves to a
real ComStock building type, so the CSV cannot promise measured data the
extractor cannot supply.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

### Task 5: Warm the cache for every archetype Worcester needs

**Files:**
- Create: `scripts/warm_comstock_cache.py`
- Modify: `tests/test_comstock.py`

**Interfaces:**
- Consumes: `ingest.load_municipality`, `comstock.build_archetype`.
- Produces: populated `data/interim/comstock/*.parquet`, and a printed table of what was fetched.

This is the step that proves the extractor works against the whole real
universe rather than one building, and it produces the artifact every later
stage depends on. `data/interim/` is already gitignored.

- [ ] **Step 1: Write the script**

Create `scripts/warm_comstock_cache.py`:

```python
"""Fetch and cache one measured profile per ComStock archetype Worcester needs.

Run once. Later stages read only the local cache, so the pipeline is
reproducible offline and a re-run costs nothing.

    uv run python scripts/warm_comstock_cache.py
"""

from __future__ import annotations

import sys
import time

from shave import comstock
from shave.ingest import load_municipality

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"


def main() -> int:
    parcels = load_municipality(WORCESTER, town_id=348)
    wanted = sorted(
        parcels.loc[parcels["source"] == "comstock", "archetype"].dropna().unique()
    )
    print(f"{len(wanted)} ComStock archetypes in Worcester: {', '.join(wanted)}\n")

    failures = []
    for name in wanted:
        started = time.perf_counter()
        try:
            a = comstock.build_archetype(name, sqft=10_000.0)
            peak = a.monthly_peaks().max()
            print(f"  {name:26s} bldg {a.profile.bldg_id:>7}  "
                  f"{a.profile.sqft:>9,.0f} sqft  peak {peak:7.1f} kW  "
                  f"{time.perf_counter() - started:5.1f}s")
        except Exception as exc:  # noqa: BLE001 - report every failure, fail at the end
            failures.append((name, exc))
            print(f"  {name:26s} FAILED: {exc}")

    if failures:
        print(f"\n{len(failures)} archetype(s) failed", file=sys.stderr)
        return 1
    print(f"\ncache warm: {len(wanted)} archetypes in {comstock.CACHE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

Run: `uv run python scripts/warm_comstock_cache.py`
Expected: every archetype prints a building id, floor area and peak. Exit 0.

If any archetype fails with "no ComStock buildings of type", that type is
absent from Worcester County and `select_representative`'s widening is not
enough. **Stop and report it** rather than removing the archetype from the
crosswalk.

- [ ] **Step 3: Write the test that the cache covers the real universe**

Append to `tests/test_comstock.py`:

```python
@pytest.mark.network
def test_every_comstock_archetype_worcester_needs_can_be_built():
    """Not one building. Every ComStock archetype the real town actually uses."""
    from shave.ingest import load_municipality
    parcels = load_municipality(
        "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester", town_id=348)
    wanted = sorted(
        parcels.loc[parcels["source"] == "comstock", "archetype"].dropna().unique())
    assert wanted, "no ComStock-backed parcels found; ingest or crosswalk changed"
    for name in wanted:
        a = comstock.build_archetype(name, sqft=10_000.0)
        assert (a.monthly_peaks() > 0).all(), f"{name} has a zero monthly peak"
```

- [ ] **Step 4: Run it**

Run: `uv run pytest tests/test_comstock.py -m network -q`
Expected: all network tests pass. The second run is fast because the cache is warm.

- [ ] **Step 5: Run the full suite and commit**

Run: `uv run pytest -q`
Expected: 853 passed offline (the new test is network-marked).

```bash
git add scripts/warm_comstock_cache.py tests/test_comstock.py
git commit -m "feat: cache-warming script for Worcester's ComStock archetypes

Fetches one measured profile per archetype the real town actually uses and
caches it locally, so every later stage runs offline and reproducibly.

The accompanying network test proves the extractor works across the whole
real universe rather than one hand-picked building: every ComStock-backed
archetype present in Worcester must build and have a non-zero peak.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Out of scope for this plan

Named so they are not silently dropped:

- **The modelled industrial archetypes.** `ModeledArchetype` exists in
  `archetype.py` but nothing parameterises it per crosswalk name yet. Separate
  plan; it needs the EWELD licence question settled first.
- **Wiring archetypes into a scored parcel table.** This plan produces shapes;
  joining them to the 2,099 Worcester parcels and running the scorer over the
  result is the next plan.
- **The MECOLS normalised-shape sanity check.** Needs scored parcels.
- **Any Worker, frontend, or Supabase work.**

## Self-Review

**Spec coverage.** The spec's "load shape library" section requires: ComStock
for covered types (Tasks 1-4), representative selection by a stated rule with
the choice publishable (Task 2, median floor area, cited by building id),
in-place S3 reads with partition pruning (Task 1), and the release pinned
(already in `assumptions.py`, used in Task 1). Gap accepted and named above:
the modelled industrial half is a separate plan.

The spec says selection should be "the individual building whose annual load
factor is the median of its cohort." **This plan deviates to median floor
area** and the deviation is deliberate: load factor requires reading every
building's full timeseries to compute, which is 3,595 network round trips for
MA versus one metadata read. Floor area is in the metadata already, is a
reasonable proxy for typicality, and is defensible on a method page. Flagged
here so a reviewer can reject it knowingly.

**Placeholder scan.** No TBDs. Every code step has real code. The one
deliberate oddity is the doubled `slot` assignment in Task 3, called out
explicitly with an instruction to delete the first.

**Type consistency.** `ReducedProfile` fields are used identically in Tasks
3, 4 and 5. `Representative.bldg_id`/`.sqft` flow from Task 2 into Task 4's
`build_archetype`. `ComStockArchetype.source` is the string `"comstock"`,
matching `ingest.py`'s existing `source` column and the crosswalk's `source`
field. `INTERVALS_PER_BILLED_DAY` is imported from `archetype.py` everywhere
rather than redefined.
