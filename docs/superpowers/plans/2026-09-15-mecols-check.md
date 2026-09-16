# MECOLS Class-Shape Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meet success criterion 4. Compare the ComStock-backed bottom-up aggregate against National Grid's published G-2/G-3 class average load shapes, using a pass criterion committed before the first real run, and publish the result on the method page whichever way it comes out.

**Architecture:**
- **Monthly energy in the cache.** The cache gains monthly energy, written by re-reducing each cached building's own timeseries rather than re-selecting representatives. Every billed-demand figure, and so every score, stays byte-identical.
- **A new `calibration` module.** It reduces `MECOLS.xlsx` and the aggregate to the same monthly quantities: billed-window hourly peak, its hour and whole-month energy. It then compares them against constants committed in `assumptions.py` in a commit that precedes the first real run.
- **Delivery.** The result travels in the method payload, and the page renders a table and two small charts.

**Tech Stack:** Python 3.11, pandas + openpyxl (both already dependencies), DuckDB httpfs (already used), vanilla ES2020 + inline SVG, vitest.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`
- Stage 1 step 6: *"Calibration check against `MECOLS.xlsx`. Aggregate estimates by rate class per town vs the published G-2/G-3 class shape. Chart goes on the method page."*
- The MECOLS rationale, around line 224:
  - *"Compare normalized shape only — each curve scaled to its own annual max"*
  - *"Restrict to ComStock-backed types"*
  - *"Pass criterion, stated before running: hour-of-peak within ±1 h in ≥9 of 12 months, and monthly load factor within ±15%"*
  - *"Presented as a modest shape sanity check, not as validation."*
- Success criterion 4, same wording.

**Order among the pending plans:** first. It needs nothing from the town or occupant plans and closes the only unmet success criterion.

## Global Constraints

- **The criterion is declared before the first real run.**
  - Task 2 commits the constants and the comparison code, tested on synthetic data only.
  - The first computation against real Worcester data happens in Task 3, after that commit.
  - **Never run `calibration.run` on real data before Task 2 is committed**, and never change a Task 2 constant after seeing a result. If a result looks wrong, report it; do not tune the threshold.
- **Publish the result whichever way it goes.** A fail is stated on the method page as plainly as a pass.
- **No new dependency.** `openpyxl` and `duckdb` are already in `pyproject.toml`.
- **Never restate a constant**: tariff hours from `assumptions.py`, interval width from `archetype.STEP_HOURS`.
- **The page computes no figure it displays.** Percentages and normalised shapes arrive from Python.
- **`--signal` is spent on exactly three things** (DESIGN.md), and the calibration chart is not one of them.
- **Tooling:**
  - `node`/`npm`/`npx` are nvm shell functions: `NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run`.
  - Run `uv run pytest` **without `-q`**, because `addopts` already has it.
  - `data/raw/` and `data/interim/` are gitignored.
- **Baselines at `main` `b571be7`:** Python **1016 passed, 4 deselected**; render **57 passed**.
- Branch: `git checkout -b feat/mecols-check`.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts, measured 2026-09-15

**The workbook is still published.** National Grid's MA Electric *Information and Forms* page links *"Class average load shapes"* to `https://forms.nationalgrid.com/files/loaddata/massachusetts/MECOLS.xlsx`.
- **File:** 909,846 bytes, downloaded to `data/raw/mecols/MECOLS.xlsx`.
- **Sheets:**
  - `MECO Rate Class Definitions`, the text *"estimates of the amount of electricity the average customer in a particular rate class uses each hour of the year"*, plus a code list: G-1 General Service, G-2 General Service: Demand, G-3 Time-Of-Use, R-1 Regular Residential, S-0 Street Lighting.
  - `MECO ALL`, the data.
- **Data layout:** columns `Rate`, `Date`, `HR_1_KW_AVG` … `HR_24_KW_AVG`, one row per rate class per day. `HR_n` is the hour **ending** n, so hour-start `n-1`.
- **Coverage:** each of the five classes has **1,277 days, 2023-01-01 to 2026-06-30**, with **no nulls**. `Rate` values carry trailing spaces in the definitions sheet only.
- **2025**, the latest complete calendar year, has 365 days per class:
  - **G-2** average customer: mean 27.5 kW, max hourly 48.0 kW.
  - **G-3**: mean 249.4 kW, max 402.7 kW.

**The aggregate's sample.** Kept, ComStock-backed Worcester parcels:
- **G-2 380**, **G-3 148**.
- G-3 archetypes: large_office 17, hospital 16, strip_mall 17, medium_office 28, secondary_school 25, outpatient 12, retail_standalone 8, large_hotel 7, full_service_restaurant 6, warehouse 6, small_office 4, primary_school 1, small_hotel 1.

**The cache lacks monthly energy.**
- `comstock.ReducedProfile` stores `monthly_peak_kw`, the 12 × 52 worst-billed-day `windows`, `offpeak_max_kw`, `sqft`, `widened` and `cohort_size`.
- The spec's *"monthly load factor"* needs energy over the whole month, which is not stored.
- **Re-reading is cheap:** one ComStock timeseries (35,040 rows) read from S3 in **1.3 s**. There are 13 cached Worcester archetypes, so about 20 s.
- **Representatives are not re-selected.** `select_representative` samples 15 buildings per type, and re-running it could pick a different building. The refresh re-reads the *same* `bldg_id` already in each cached parquet and refuses to write if the billed shape changes.

**Weather years differ.**
- ComStock is **AMY2018**: 35,040 fifteen-minute rows, 365 days, `COMSTOCK_RELEASE = 2024/comstock_amy2018_release_2`.
- MECOLS 2025 is a later calendar and weather year.

Shapes are compared, not dates, and the method page says so.

**What "hour of peak" and "load factor" mean here, fixed now.**

| quantity | MECOLS side | aggregate side |
|---|---|---|
| **monthly billed peak** | max hourly kW on billed days (`billing_window.is_billed_day`), hour-starts 08–20 (`HR_9`…`HR_21`) | max of the 13 hourly averages of the summed 52-interval worst-billed-day windows |
| **hour of peak** | the hour-start of that max | `PEAK_HOUR_START` + index of that max |
| **monthly energy** | sum of all 24 hourly kW values over every day of the month | sum of each parcel's scaled `monthly_energy_kwh` |
| **load factor** | energy ÷ (hours in month × monthly billed peak) | same formula, hours from the ComStock weather year |
| **pass** | — | hour of peak within ±1 h in **≥ 9 of 12** months, **and** load factor within ±15 % (relative) in **all 12** months, per rate class |

Both peaks are hourly averages, so the aggregate's 15-minute windows are averaged to hours first. The spec's *"monthly load factor within ±15%"* does not say how many months; **all 12** is the stricter reading and is declared here, before running.

**Known limits of the comparison, stated on the method page:**
- the class averages are diversified across many customers, while the aggregate sums each archetype's own worst billed day (a coincident-peak proxy);
- ComStock-backed types only (the spec's rule);
- different weather years;
- Worcester parcels against a territory-wide class.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/comstock.py` *(modify)* | `ReducedProfile.monthly_energy_kwh`; `ComStockArchetype.monthly_energy_kwh()`; `refresh_cached_profile`. |
| `scripts/refresh_comstock_energy.py` *(new)* | Re-reduce every cached profile in place, identity preserved. |
| `scripts/fetch_mecols.py` *(new)* | Download the workbook with curl. |
| `src/shave/assumptions.py` *(modify)* | The declared criterion, the MECOLS year, the ComStock weather year. |
| `src/shave/calibration.py` *(new)* | Load MECOLS, reduce both sides to monthly shapes, compare, run. |
| `scripts/build_site.py`, `src/shave/site_data.py`, `src/shave/method.py` *(modify)* | Run it, carry it, state its limits. |
| `public/app.js` *(modify)* | `calibrationHTML`, rendered on the method page. |
| `tests/test_comstock.py`, `tests/test_calibration.py` *(new)*, `tests/test_method.py`, `tests/test_site_data.py`, `tests/conftest.py`, `web/render.test.js` | |
| `docs/spec-coverage.md` *(modify)* | Criterion 4 and step 6. |

---

## Task 1: Monthly energy in the ComStock cache, scores untouched

**Files:**
- Modify: `src/shave/comstock.py` (`ReducedProfile` ~lines 207–283, `reduce_from_frame` ~286–330, `ComStockArchetype` ~379–425; append `refresh_cached_profile`)
- Create: `scripts/refresh_comstock_energy.py`
- Test: `tests/test_comstock.py`

**Interfaces:**
- Produces:
  - `ReducedProfile.monthly_energy_kwh: np.ndarray`, shape (12,), kWh over every interval of each calendar month; **NaN** when read from a frame without the column
  - `ComStockArchetype.monthly_energy_kwh() -> np.ndarray`, scaled to the parcel
  - `comstock.refresh_cached_profile(path, reader=None) -> ReducedProfile`

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/mecols-check
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_comstock.py`:

```python
# ---------------------------------------------------------------------------
# monthly energy, for the MECOLS load-factor check
# ---------------------------------------------------------------------------

def _flat_year(kw: float = 100.0) -> pd.DataFrame:
    """A whole 2018 at a constant `kw`, as ComStock's kWh-per-interval column."""
    ts = pd.date_range("2018-01-01 00:00", "2018-12-31 23:45", freq="15min")
    kwh = kw / comstock.KWH_PER_INTERVAL_TO_KW
    return pd.DataFrame({"timestamp": ts, comstock.TOTAL_ELECTRICITY_COL: kwh})


def test_monthly_energy_counts_every_interval_billed_or_not():
    """Load factor is energy over the whole month, nights and weekends included."""
    prof = comstock.reduce_from_frame(1, _flat_year(100.0), sqft=10_000.0)
    # January 2018: 31 days x 96 intervals x 100 kW x 0.25 h
    assert prof.monthly_energy_kwh[0] == pytest.approx(31 * 96 * 100 * 0.25)
    assert prof.monthly_energy_kwh[1] == pytest.approx(28 * 96 * 100 * 0.25)


def test_monthly_energy_survives_the_cache_round_trip():
    prof = comstock.reduce_from_frame(1, _flat_year(80.0), sqft=10_000.0)
    back = comstock.ReducedProfile.from_frame(prof.to_frame())
    np.testing.assert_allclose(back.monthly_energy_kwh, prof.monthly_energy_kwh)


def test_a_frame_without_monthly_energy_reads_as_nan_never_zero():
    """A zero-energy month would give a load factor of zero and a calibration
    verdict computed from nothing. NaN makes the calibration refuse instead."""
    prof = comstock.reduce_from_frame(1, _flat_year(80.0), sqft=10_000.0)
    back = comstock.ReducedProfile.from_frame(prof.to_frame().drop(columns="monthly_energy_kwh"))
    assert np.isnan(back.monthly_energy_kwh).all()


def test_the_committed_fixture_predates_monthly_energy_and_reads_as_nan():
    df = pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet")
    assert np.isnan(comstock.ReducedProfile.from_frame(df).monthly_energy_kwh).all()


def test_refresh_fills_energy_and_keeps_the_building_and_its_flags(tmp_path):
    original = replace(
        comstock.reduce_from_frame(7, _flat_year(120.0), sqft=5_000.0),
        widened=True, cohort_size=2,
    )
    cache = tmp_path / "hospital__G2500270.parquet"
    original.to_frame().drop(columns="monthly_energy_kwh").to_parquet(cache)

    def reader(bldg_id, conn=None, sqft=None):
        assert bldg_id == 7, "must re-read the cached building, not a new pick"
        return comstock.reduce_from_frame(bldg_id, _flat_year(120.0), sqft=sqft)

    refreshed = comstock.refresh_cached_profile(cache, reader=reader)
    back = comstock.ReducedProfile.from_frame(pd.read_parquet(cache))

    assert (back.bldg_id, back.sqft, back.widened, back.cohort_size) == (7, 5_000.0, True, 2)
    assert not np.isnan(back.monthly_energy_kwh).any()
    np.testing.assert_allclose(refreshed.monthly_peak_kw, original.monthly_peak_kw)


def test_refresh_refuses_to_overwrite_when_the_billed_shape_changed(tmp_path):
    """The cache is what every score was computed from. If S3 now returns a
    different shape for the same building, stop rather than silently move them."""
    original = comstock.reduce_from_frame(7, _flat_year(120.0), sqft=5_000.0)
    cache = tmp_path / "warehouse__G2500270.parquet"
    original.to_frame().to_parquet(cache)
    before = cache.read_bytes()

    def reader(bldg_id, conn=None, sqft=None):
        return comstock.reduce_from_frame(bldg_id, _flat_year(999.0), sqft=sqft)

    with pytest.raises(comstock.ComStockError, match="changed its billed shape"):
        comstock.refresh_cached_profile(cache, reader=reader)
    assert cache.read_bytes() == before
```

If `replace` is not already imported at the top of `tests/test_comstock.py`, add `from dataclasses import replace` beside the other imports.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_comstock.py -k "energy or refresh"`
Expected: FAIL — `AttributeError: 'ReducedProfile' object has no attribute 'monthly_energy_kwh'`.

- [ ] **Step 4: Implement in `src/shave/comstock.py`**

**Dataclass.** In `ReducedProfile`, directly after the `offpeak_max_kw` field, add:

```python
    #: Energy over EVERY interval of each calendar month, billed or not, in kWh.
    #: The MECOLS check needs it for monthly load factor. NaN, never zero, when
    #: read from a cache written before the column existed.
    monthly_energy_kwh: np.ndarray = field(
        default_factory=lambda: np.full(12, np.nan)
    )
```

**Writing the column.** In `to_frame`, directly after the `"offpeak_max_kw": self.offpeak_max_kw,` entry, add:

```python
            "monthly_energy_kwh": self.monthly_energy_kwh,
```

**Reading it back.** In `from_frame`, directly after the `offpeak` block, add:

```python
        if "monthly_energy_kwh" in df.columns:
            energy = df["monthly_energy_kwh"].to_numpy(dtype=float)
        else:
            # NaN, never zero: a zero-energy month gives a load factor of zero
            # and a calibration verdict computed from nothing.
            energy = np.full(12, np.nan)
```

and pass `monthly_energy_kwh=energy,` in its `return cls(...)`.

**Computing it.** In `reduce_from_frame`, directly **before** `keep = billed_mask(ts)`, add:

```python
    # Energy per calendar month over every interval, computed BEFORE the billed
    # mask drops nights and weekends. Load factor is energy over the whole month.
    energy = np.zeros(12, dtype=float)
    np.add.at(energy, ts.month.to_numpy() - 1, kw * (INTERVAL_MINUTES / 60.0))
```

and change its `return` to:

```python
    return ReducedProfile(
        int(bldg_id), peaks, windows, sqft,
        offpeak_max_kw=offpeak_max, monthly_energy_kwh=energy,
    )
```

**Scaling.** In `ComStockArchetype`, after `offpeak_max`, add:

```python
    def monthly_energy_kwh(self) -> np.ndarray:
        """Energy per calendar month, scaled to the parcel. NaN if the cached
        profile predates the column; run scripts/refresh_comstock_energy.py."""
        return self.profile.monthly_energy_kwh * self._scale
```

**Refresh.** Append to the end of the module:

```python
def refresh_cached_profile(
    path: Path | str, reader: Callable[..., ReducedProfile] | None = None
) -> ReducedProfile:
    """Re-reduce a cached profile's OWN building, so new columns fill in.

    Re-running representative selection could pick a different building and
    move every score. This re-reads the bldg_id already in the cache, carries
    its floor area and cohort flags across, and refuses to write if the billed
    shape it re-derives differs from the one the scores were computed from.
    """
    path = Path(path)
    old = ReducedProfile.from_frame(pd.read_parquet(path))
    read = reader or reduce_timeseries
    fresh = read(old.bldg_id, sqft=old.sqft)
    new = replace(fresh, sqft=old.sqft, widened=old.widened, cohort_size=old.cohort_size)
    same_shape = np.allclose(new.monthly_peak_kw, old.monthly_peak_kw) and np.allclose(
        new.windows, old.windows
    )
    if not same_shape:
        raise ComStockError(
            f"{path.name}: re-reading building {old.bldg_id} changed its billed "
            "shape; refusing to overwrite the cache the scores were computed from"
        )
    new.to_frame().to_parquet(path)
    return new
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_comstock.py`
Expected: PASS, with 6 new tests.

- [ ] **Step 6: Refresh the real cache**

Create `scripts/refresh_comstock_energy.py`:

```python
"""Fill monthly energy into every cached ComStock profile, identity preserved.

    uv run python scripts/refresh_comstock_energy.py

Re-reads each cached building's own timeseries from S3 (about 1.3 s each) and
refuses to overwrite any file whose billed shape would change.
"""

from __future__ import annotations

import sys
import time

from shave import comstock


def main() -> int:
    paths = sorted(comstock.CACHE_DIR.glob("*.parquet"))
    if not paths:
        print(f"no cached profiles in {comstock.CACHE_DIR}", file=sys.stderr)
        return 1
    for path in paths:
        started = time.perf_counter()
        prof = comstock.refresh_cached_profile(path)
        print(f"  {path.name:40s} bldg {prof.bldg_id:>7}  "
              f"annual {prof.monthly_energy_kwh.sum():>12,.0f} kWh  "
              f"{time.perf_counter() - started:4.1f}s")
    print(f"refreshed {len(paths)} profiles", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run, recording the Worcester scores before and after:

```bash
uv run python scripts/build_site.py && cp public/data/ranked.json /tmp/ranked-before.json
uv run python scripts/refresh_comstock_energy.py
uv run python scripts/build_site.py
uv run python -c "
import json
a = json.load(open('/tmp/ranked-before.json')); b = json.load(open('public/data/ranked.json'))
key = lambda d: [(r['loc_id'], r['annual_savings_usd'], r['rank']) for l in d['lists'].values() for r in l]
print('scores identical:', key(a) == key(b))
"
```

**Pass conditions, declared in advance:** every cached profile refreshes with no `ComStockError`; `scores identical: True`.

- [ ] **Step 7: Full suite and commit**

```bash
uv run pytest
git add src/shave/comstock.py scripts/refresh_comstock_energy.py tests/test_comstock.py
git commit -m "feat: monthly energy in the ComStock cache, scores untouched

The MECOLS check compares monthly load factor, which needs energy over the
whole month; the cache kept only billed peaks and worst-day windows. Profiles
now carry monthly energy, filled by re-reading each cached building's own
timeseries rather than re-selecting representatives, and the refresh refuses
to write if the billed shape it re-derives has changed. A cache written before
the column reads as NaN, never zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **1022 passed, 4 deselected** (1016 + 6).

---

## Task 2: The criterion and the comparison, committed before any real run

**Files:**
- Modify: `src/shave/assumptions.py`
- Create: `src/shave/calibration.py`
- Create: `scripts/fetch_mecols.py`
- Create: `tests/test_calibration.py`

**Interfaces:**
- Consumes: `ComStockArchetype.monthly_energy_kwh()`, `peak_day_window(m)` (Task 1).
- Produces:
  - `assumptions.MECOLS_URL: str`, `MECOLS_YEAR = 2025`, `MECOLS_HOUR_TOLERANCE_H = 1`, `MECOLS_MONTHS_REQUIRED = 9`, `MECOLS_LOAD_FACTOR_TOLERANCE = 0.15`, `COMSTOCK_WEATHER_YEAR = 2018`
  - `calibration.RATES = ("G-2", "G-3")`, `calibration.MECOLS_PATH = Path("data/raw/mecols/MECOLS.xlsx")`
  - `calibration.MonthlyShape(peak_kw, peak_hour, energy_kwh, hours)`, with property `load_factor`
  - `calibration.load_mecols(path) -> pd.DataFrame`
  - `calibration.mecols_monthly(frame, rate, year) -> MonthlyShape`
  - `calibration.bottom_up_monthly(scored, archetype_factory=None) -> dict[str, MonthlyShape]`
  - `calibration.compare(ours, theirs) -> dict`
  - `calibration.run(scored, mecols_path=MECOLS_PATH, archetype_factory=None, year=MECOLS_YEAR) -> dict`

**No step in this task touches real Worcester data.** The first real run is Task 3, after this task's commit.

- [ ] **Step 1: Declare the criterion**

First, confirm the names are free:

```bash
grep -n "MECOLS_\|COMSTOCK_WEATHER_YEAR" src/shave/assumptions.py
```

Expected: no output.

Add to `src/shave/assumptions.py`, directly after `COMSTOCK_RELEASE` is defined:

```python
# ComStock's timeseries are the AMY2018 weather year: 35,040 fifteen-minute
# rows over 365 days. Hours in a month for the aggregate come from this year.
COMSTOCK_WEATHER_YEAR = 2018

# --------------------------------------------------------------------------
# MECOLS class-shape check (success criterion 4)
# --------------------------------------------------------------------------
# DECLARED BEFORE THE CHECK WAS FIRST RUN. The commit that adds these precedes
# the first computation against real data; changing one after seeing a result
# would turn a sanity check into a fitted one.

MECOLS_URL = "https://forms.nationalgrid.com/files/loaddata/massachusetts/MECOLS.xlsx"

#: The latest complete calendar year in the workbook (it runs 2023-01 to 2026-06).
MECOLS_YEAR = 2025

#: Hour of the monthly billed peak must be within this many hours...
MECOLS_HOUR_TOLERANCE_H = 1
#: ...in at least this many of the 12 months.
MECOLS_MONTHS_REQUIRED = 9

#: Monthly load factor must be within this relative tolerance, in all 12 months.
MECOLS_LOAD_FACTOR_TOLERANCE = 0.15
```

In `PUBLISHED`, after the `comstock_release` entry, add:

```python
    Assumption(
        "mecols_pass_criterion",
        f"peak hour +/-{MECOLS_HOUR_TOLERANCE_H} h in >={MECOLS_MONTHS_REQUIRED} of 12 months; "
        f"load factor +/-{MECOLS_LOAD_FACTOR_TOLERANCE:.0%} in all 12",
        "", "ASSUMED", "design doc, declared before the first run",
        "Per rate class, G-2 and G-3. The design doc's load-factor clause does "
        "not say how many months; all 12 is the stricter reading and was fixed "
        "before any result was seen.",
    ),
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_calibration.py`:

```python
"""The MECOLS class-shape check, on synthetic data only.

Nothing here reads the real workbook or real Worcester parcels. The criterion
and the arithmetic are committed before the first real run, which is the
point of declaring a pass criterion in advance.
"""

import calendar
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from shave import assumptions, calibration
from shave.archetype import INTERVALS_PER_BILLED_DAY
from shave.billing_window import billed_days

HOURS = [f"HR_{h}_KW_AVG" for h in range(1, 25)]


def _synthetic_mecols(tmp_path, year=2025):
    """G-2 at a flat 10 kW, with three spikes per month:
    - 30 kW at hour-start 14 on the first billed day  (the billed peak)
    - 50 kW at hour-start 14 on the first Saturday      (not billed)
    - 60 kW at hour-start 3 on the first billed day     (outside the window)
    """
    rows = []
    for m in range(1, 13):
        first_billed = billed_days(year, m)[0]
        first_saturday = next(
            date(year, m, d) for d in range(1, 8) if date(year, m, d).weekday() == 5
        )
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            day = date(year, m, d)
            kw = [10.0] * 24
            if day == first_billed:
                kw[14] = 30.0   # HR_15 is hour-start 14
                kw[3] = 60.0    # HR_4 is hour-start 3
            if day == first_saturday:
                kw[14] = 50.0
            rows.append({"Rate": "G-2", "Date": pd.Timestamp(day), **dict(zip(HOURS, kw))})
    path = tmp_path / "MECOLS.xlsx"
    pd.DataFrame(rows).to_excel(path, sheet_name=calibration.MECOLS_SHEET, index=False)
    return path


def test_the_criterion_is_published_with_the_assumptions():
    keys = {a.key for a in assumptions.PUBLISHED}
    assert "mecols_pass_criterion" in keys
    assert assumptions.MECOLS_MONTHS_REQUIRED == 9
    assert assumptions.MECOLS_HOUR_TOLERANCE_H == 1
    assert assumptions.MECOLS_LOAD_FACTOR_TOLERANCE == 0.15


def test_the_billed_peak_ignores_weekends_and_hours_outside_the_window(tmp_path):
    frame = calibration.load_mecols(_synthetic_mecols(tmp_path))

    shape = calibration.mecols_monthly(frame, "G-2", 2025)

    assert list(shape.peak_hour) == [14] * 12, "not the Saturday, not 03:00"
    np.testing.assert_allclose(shape.peak_kw, 30.0)


def test_energy_counts_every_hour_and_load_factor_uses_the_billed_peak(tmp_path):
    frame = calibration.load_mecols(_synthetic_mecols(tmp_path))

    shape = calibration.mecols_monthly(frame, "G-2", 2025)

    jan_hours = 31 * 24
    jan_energy = jan_hours * 10.0 + (30 - 10) + (60 - 10) + (50 - 10)
    assert shape.hours[0] == jan_hours
    assert shape.energy_kwh[0] == pytest.approx(jan_energy)
    assert shape.load_factor[0] == pytest.approx(jan_energy / (jan_hours * 30.0))


class _Stub:
    """A ComStock-like archetype: flat `level`, tripled at hour-start 14."""

    def __init__(self, level: float):
        self.level = level

    def peak_day_window(self, month):
        w = np.full(INTERVALS_PER_BILLED_DAY, self.level)
        w[24:28] = self.level * 3.0  # intervals 24-27 are 14:00-14:45
        return w

    def monthly_energy_kwh(self):
        return np.full(12, 1000.0 * self.level)


def test_the_aggregate_sums_comstock_kept_rows_by_rate_as_hourly_averages():
    scored = pd.DataFrame([
        {"source": "comstock", "keep": True, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
        {"source": "comstock", "keep": True, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
        {"source": "modeled", "keep": True, "rate_class": "G-2", "archetype": "university", "sqft": 1.0},
        {"source": "comstock", "keep": False, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
    ])

    out = calibration.bottom_up_monthly(scored, archetype_factory=lambda row: _Stub(10.0))

    assert set(out) == {"G-2"}, "no G-3 rows, so no G-3 shape"
    g2 = out["G-2"]
    np.testing.assert_allclose(g2.peak_kw, 60.0)           # two parcels x 30 kW
    assert list(g2.peak_hour) == [14] * 12
    np.testing.assert_allclose(g2.energy_kwh, 20_000.0)     # modeled and dropped rows excluded
    assert g2.hours[0] == 31 * 24 and g2.hours[1] == 28 * 24  # 2018


def test_an_aggregate_with_missing_energy_refuses_rather_than_reporting():
    class NoEnergy(_Stub):
        def monthly_energy_kwh(self):
            return np.full(12, np.nan)

    scored = pd.DataFrame([{"source": "comstock", "keep": True, "rate_class": "G-3",
                            "archetype": "hospital", "sqft": 1.0}])
    with pytest.raises(ValueError, match="refresh_comstock_energy"):
        calibration.bottom_up_monthly(scored, archetype_factory=lambda row: NoEnergy(1.0))


def _shape(peak_hour, load_factor):
    hours = np.full(12, 720.0)
    peak = np.full(12, 100.0)
    return calibration.MonthlyShape(
        peak_kw=peak, peak_hour=np.asarray(peak_hour), energy_kwh=np.asarray(load_factor) * hours * peak,
        hours=hours,
    )


def test_compare_applies_the_declared_thresholds():
    ours = _shape([14] * 12, [0.50] * 12)
    close = _shape([15] * 9 + [17] * 3, [0.44] * 12)   # 9 hour matches; LF within 13.6%
    far = _shape([15] * 8 + [17] * 4, [0.40] * 12)     # 8 hour matches; LF off by 25%

    good = calibration.compare(ours, close)
    bad = calibration.compare(ours, far)

    assert (good["months_hour_ok"], good["months_load_factor_ok"], good["passes"]) == (9, 12, True)
    assert (bad["months_hour_ok"], bad["months_load_factor_ok"], bad["passes"]) == (8, 0, False)
    assert max(good["peak_shape_ours"]) == 1.0 and max(good["peak_shape_mecols"]) == 1.0
    json.dumps(good)


def test_run_without_the_workbook_reports_unrun_not_failed(tmp_path):
    out = calibration.run(pd.DataFrame(), mecols_path=tmp_path / "absent.xlsx")
    assert "status" in out
    assert "not failed" in out["status"]
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_calibration.py`
Expected: FAIL — `ImportError: cannot import name 'calibration' from 'shave'`.

- [ ] **Step 4: Write `src/shave/calibration.py`**

```python
"""The MECOLS class-shape check: a modest sanity check, not validation.

National Grid publishes the hourly load of the AVERAGE customer in each
Massachusetts Electric rate class. This compares that published G-2 and G-3
shape with the bottom-up aggregate of this tool's ComStock-backed rows, on two
quantities reduced identically on both sides:

  hour of the monthly billed peak   billed days only, hour-starts 08-20
  monthly load factor               whole-month energy over (hours x billed peak)

The pass criterion lives in `assumptions.py` and was committed before the check
first ran. It is not tuned after the fact. The result is published whichever
way it comes out.

What it cannot show, stated on the method page: the class average is
diversified across many customers while the aggregate sums each archetype's
own worst billed day; ComStock is weather year 2018 and the class shapes a
later year; and it says nothing about the modelled industrial rows.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from shave import comstock
from shave.archetype import INTERVALS_PER_BILLED_DAY, STEP_HOURS
from shave.assumptions import (
    COMSTOCK_WEATHER_YEAR,
    MECOLS_HOUR_TOLERANCE_H,
    MECOLS_LOAD_FACTOR_TOLERANCE,
    MECOLS_MONTHS_REQUIRED,
    MECOLS_YEAR,
    PEAK_HOUR_END,
    PEAK_HOUR_START,
)
from shave.billing_window import is_billed_day

MECOLS_PATH = Path("data/raw/mecols/MECOLS.xlsx")
MECOLS_SHEET = "MECO ALL"
RATES: tuple[str, ...] = ("G-2", "G-3")

#: `HR_n` is the hour ENDING n, so column index i is hour-start i.
_HOUR_COLUMNS = [f"HR_{h}_KW_AVG" for h in range(1, 25)]


@dataclass(frozen=True)
class MonthlyShape:
    peak_kw: np.ndarray      #: (12,) highest hourly-average kW in the billed window
    peak_hour: np.ndarray    #: (12,) hour-start of that peak
    energy_kwh: np.ndarray   #: (12,) energy over every hour of the month
    hours: np.ndarray        #: (12,) hours in the month

    @property
    def load_factor(self) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return self.energy_kwh / (self.hours * self.peak_kw)


def load_mecols(path: Path | str) -> pd.DataFrame:
    """The `MECO ALL` sheet: Rate, Date, and 24 hourly-average kW columns."""
    frame = pd.read_excel(path, sheet_name=MECOLS_SHEET)
    missing = {"Rate", "Date", *_HOUR_COLUMNS} - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: {MECOLS_SHEET} is missing columns {sorted(missing)}")
    frame = frame[["Rate", "Date", *_HOUR_COLUMNS]].copy()
    frame["Rate"] = frame["Rate"].astype(str).str.strip()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


def mecols_monthly(frame: pd.DataFrame, rate: str, year: int) -> MonthlyShape:
    """One class's twelve months, reduced the way the tariff bills."""
    rows = frame[(frame["Rate"] == rate) & (frame["Date"].dt.year == year)]
    peak = np.zeros(12)
    peak_hour = np.zeros(12, dtype=int)
    energy = np.zeros(12)
    hours = np.zeros(12)
    window = slice(PEAK_HOUR_START, PEAK_HOUR_END)
    for m in range(1, 13):
        month = rows[rows["Date"].dt.month == m]
        expected = calendar.monthrange(year, m)[1]
        if len(month) != expected:
            raise ValueError(f"MECOLS {rate} {year}-{m:02d} has {len(month)} days, expected {expected}")
        kw = month[_HOUR_COLUMNS].to_numpy(dtype=float)
        energy[m - 1] = kw.sum()  # an hourly-average kW over one hour is kWh
        hours[m - 1] = kw.size
        billed = np.array([is_billed_day(ts.date()) for ts in month["Date"]])
        in_window = kw[billed, window]
        flat = int(np.argmax(in_window))
        peak[m - 1] = float(in_window.flat[flat])
        peak_hour[m - 1] = PEAK_HOUR_START + flat % in_window.shape[1]
    return MonthlyShape(peak, peak_hour, energy, hours)


def _default_factory(row: Mapping) -> comstock.ComStockArchetype:
    return comstock.build_archetype(str(row["archetype"]), float(row["sqft"]))


def bottom_up_monthly(
    scored: pd.DataFrame,
    archetype_factory: Callable[[Mapping], object] | None = None,
) -> dict[str, MonthlyShape]:
    """The ComStock-backed kept rows, summed by rate class.

    Each archetype contributes its own worst billed day per month, so the sum
    is a coincident-peak proxy rather than a real day. The 15-minute windows
    are averaged to hours so both sides compare hourly peaks.
    """
    build = archetype_factory or _default_factory
    kept = scored[(scored["source"] == "comstock") & scored["keep"].astype(bool)]
    per_hour = int(round(1.0 / STEP_HOURS))
    hours = np.array(
        [calendar.monthrange(COMSTOCK_WEATHER_YEAR, m)[1] * 24 for m in range(1, 13)],
        dtype=float,
    )
    out: dict[str, MonthlyShape] = {}
    for rate in RATES:
        rows = kept[kept["rate_class"] == rate]
        if rows.empty:
            continue
        windows = np.zeros((12, INTERVALS_PER_BILLED_DAY))
        energy = np.zeros(12)
        for row in rows.to_dict("records"):
            archetype = build(row)
            windows += np.array([archetype.peak_day_window(m) for m in range(1, 13)])
            energy += np.asarray(archetype.monthly_energy_kwh(), dtype=float)
        if np.isnan(energy).any():
            raise ValueError(
                "a cached ComStock profile has no monthly energy; run "
                "scripts/refresh_comstock_energy.py"
            )
        hourly = windows.reshape(12, -1, per_hour).mean(axis=2)
        out[rate] = MonthlyShape(
            peak_kw=hourly.max(axis=1),
            peak_hour=PEAK_HOUR_START + hourly.argmax(axis=1),
            energy_kwh=energy,
            hours=hours,
        )
    return out


def compare(ours: MonthlyShape, theirs: MonthlyShape) -> dict:
    """The declared criterion, applied month by month."""
    hour_diff = np.abs(ours.peak_hour.astype(int) - theirs.peak_hour.astype(int))
    lf_ratio = ours.load_factor / theirs.load_factor - 1.0
    months_hour_ok = int((hour_diff <= MECOLS_HOUR_TOLERANCE_H).sum())
    months_lf_ok = int((np.abs(lf_ratio) <= MECOLS_LOAD_FACTOR_TOLERANCE).sum())
    passes_hour = months_hour_ok >= MECOLS_MONTHS_REQUIRED
    passes_lf = months_lf_ok == 12
    return {
        "peak_hour_ours": [int(h) for h in ours.peak_hour],
        "peak_hour_mecols": [int(h) for h in theirs.peak_hour],
        "load_factor_ours": [round(float(v), 3) for v in ours.load_factor],
        "load_factor_mecols": [round(float(v), 3) for v in theirs.load_factor],
        "peak_shape_ours": [round(float(v), 3) for v in ours.peak_kw / ours.peak_kw.max()],
        "peak_shape_mecols": [round(float(v), 3) for v in theirs.peak_kw / theirs.peak_kw.max()],
        "months_hour_ok": months_hour_ok,
        "months_load_factor_ok": months_lf_ok,
        "passes_hour_of_peak": passes_hour,
        "passes_load_factor": passes_lf,
        "passes": passes_hour and passes_lf,
    }


def run(
    scored: pd.DataFrame,
    mecols_path: Path | str = MECOLS_PATH,
    archetype_factory: Callable[[Mapping], object] | None = None,
    year: int = MECOLS_YEAR,
) -> dict:
    """The whole check, or a status saying why it did not run."""
    path = Path(mecols_path)
    if not path.exists():
        return {
            "status": f"not run: {path} is not on disk (scripts/fetch_mecols.py). "
                      "The result is unreported, not failed."
        }
    frame = load_mecols(path)
    ours = bottom_up_monthly(scored, archetype_factory)
    kept = scored[(scored["source"] == "comstock") & scored["keep"].astype(bool)]
    counts = kept["rate_class"].value_counts()
    return {
        "year": int(year),
        "comstock_weather_year": COMSTOCK_WEATHER_YEAR,
        "criterion": {
            "hour_tolerance_h": MECOLS_HOUR_TOLERANCE_H,
            "months_required": MECOLS_MONTHS_REQUIRED,
            "load_factor_tolerance_pct": int(round(MECOLS_LOAD_FACTOR_TOLERANCE * 100)),
            "load_factor_months_required": 12,
        },
        "by_rate": {
            rate: {"n_parcels": int(counts.get(rate, 0)),
                   **compare(ours[rate], mecols_monthly(frame, rate, year))}
            for rate in RATES
            if rate in ours
        },
    }
```

Create `scripts/fetch_mecols.py`:

```python
"""Download National Grid's MECOLS class average load shapes.

    uv run python scripts/fetch_mecols.py

Writes data/raw/mecols/MECOLS.xlsx (gitignored). Downloads through curl for the
same reason as scripts/fetch_structures.py: a python.org Python on macOS may
have no certificate store, and curl uses the system's.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from shave import calibration
from shave.assumptions import MECOLS_URL


def main() -> int:
    if shutil.which("curl") is None:
        print("curl is required", file=sys.stderr)
        return 1
    calibration.MECOLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "120",
         "--output", str(calibration.MECOLS_PATH), MECOLS_URL],
        check=True,
    )
    size = calibration.MECOLS_PATH.stat().st_size
    print(f"{MECOLS_URL}\n{size:,} bytes -> {calibration.MECOLS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests (synthetic only)**

Run: `uv run pytest tests/test_calibration.py tests/test_assumptions.py`
Expected: PASS, with 8 new tests in `test_calibration.py`.

- [ ] **Step 6: Commit, before any real run**

```bash
uv run pytest
git add src/shave/assumptions.py src/shave/calibration.py scripts/fetch_mecols.py tests/test_calibration.py
git commit -m "feat: the MECOLS criterion and comparison, declared before any run

Success criterion 4's pass test -- hour of peak within 1 h in at least 9 of 12
months, monthly load factor within 15% -- is committed as constants with the
code that applies it, tested on synthetic data only. The load-factor clause
names no month count; all 12 is the stricter reading and is fixed here, before
the first computation against real Worcester data.

Both sides reduce identically: billed days only, hour-starts 08-20, hourly
averages, whole-month energy over hours times billed peak.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git log --oneline -1
```

Expected: **1030 passed, 4 deselected** (1022 + 8). Record the commit hash: Task 4 cites it as the proof of order.

---

## Task 3: Run it for real, and put it on the method page

**Files:**
- Modify: `scripts/build_site.py`, `src/shave/site_data.py`, `src/shave/method.py`
- Modify: `public/app.js`
- Modify: `tests/conftest.py`
- Test: `tests/test_calibration.py`, `tests/test_method.py`, `tests/test_site_data.py`, `web/render.test.js`

**Interfaces:**
- Consumes: `calibration.run` (Task 2).
- Produces:
  - `method.method_payload(scored, regression=None, calibration=None)`, whose payload gains `calibration`
  - `site_data.enrich` passes `export_payload.get("calibration")` through
  - `app.js` exports `calibrationHTML(cal) -> string`
  - `KNOWN_GAPS` loses `no_class_shape_check`; `LIMITATIONS` gains `class_shape_check_is_modest`

- [ ] **Step 1: Write the failing tests**

Add to `tests/conftest.py`:

```python
MECOLS_PATH = Path("data/raw/mecols/MECOLS.xlsx")


@pytest.fixture(scope="session")
def mecols_path():
    if not MECOLS_PATH.exists():
        pytest.skip("MECOLS.xlsx not present (data/raw is gitignored); run scripts/fetch_mecols.py")
    return MECOLS_PATH
```

Append to `tests/test_calibration.py`:

```python
def test_the_real_check_reports_both_rates_over_twelve_months(worcester_scored, mecols_path):
    """Structure only. The verdict is published, never asserted: a test that
    required a pass would be a threshold tuned after the fact."""
    out = calibration.run(worcester_scored, mecols_path=mecols_path)

    assert out["year"] == 2025
    assert set(out["by_rate"]) == {"G-2", "G-3"}
    assert out["by_rate"]["G-2"]["n_parcels"] == 380
    assert out["by_rate"]["G-3"]["n_parcels"] == 148
    for rate in ("G-2", "G-3"):
        r = out["by_rate"][rate]
        assert len(r["peak_hour_ours"]) == len(r["load_factor_mecols"]) == 12
        assert isinstance(r["passes"], bool)
    json.dumps(out)
```

Append to `tests/test_method.py`:

```python
def test_the_class_shape_check_is_a_stated_limitation_not_a_gap():
    gaps = {g.key for g in method.KNOWN_GAPS}
    assert "no_class_shape_check" not in gaps
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "class_shape_check_is_modest" in stated, sorted(stated)
    text = stated["class_shape_check_is_modest"].lower()
    for words in ("not validation", "2018", "modelled"):
        assert words in text, words


def test_the_method_payload_carries_the_calibration_it_was_given():
    payload = method.method_payload(_fake_scored(), calibration={"year": 2025, "by_rate": {}})
    assert payload["calibration"] == {"year": 2025, "by_rate": {}}
    assert "status" in method.method_payload(_fake_scored())["calibration"]
```

Append to `tests/test_site_data.py`:

```python
def test_enrich_carries_the_calibration_the_build_ran():
    payload = {"schema_version": "1.5.0", "counts": {},
               "calibration": {"year": 2025, "by_rate": {"G-2": {"passes": False}}},
               "lists": {"comstock": [{"loc_id": "L1", "rank": 1,
                                       "monthly_billed_demand_kw": [1.0] * 12,
                                       "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub())

    assert out["method"]["calibration"]["by_rate"]["G-2"]["passes"] is False
```

Append to `web/render.test.js`:

```js
import { calibrationHTML } from "../public/app.js";

const CAL = {
  year: 2025,
  criterion: { hour_tolerance_h: 1, months_required: 9, load_factor_tolerance_pct: 15, load_factor_months_required: 12 },
  by_rate: {
    "G-2": { n_parcels: 380, months_hour_ok: 10, months_load_factor_ok: 12, passes: true,
             peak_shape_ours: Array(12).fill(0.9), peak_shape_mecols: Array(12).fill(0.8) },
    "G-3": { n_parcels: 148, months_hour_ok: 7, months_load_factor_ok: 11, passes: false,
             peak_shape_ours: Array(12).fill(1), peak_shape_mecols: Array(12).fill(1) },
  },
};

describe("calibrationHTML", () => {
  it("states the declared criterion and both results plainly, pass or not", () => {
    const html = calibrationHTML(CAL);
    expect(html).toContain("10 of 12");
    expect(html).toContain("7 of 12");
    expect(html).toContain("Passes");
    expect(html).toContain("Does not pass");
    expect(html).toContain("15%");
    expect(html).toMatch(/not validation/);
  });

  it("says an unrun check is unreported, not failed", () => {
    const html = calibrationHTML({ status: "not run: file missing. The result is unreported, not failed." });
    expect(html).toContain("unreported, not failed");
    expect(html).not.toContain("<table");
  });

  it("draws two lines per rate and never spends the accent", () => {
    const html = calibrationHTML(CAL);
    expect(html.match(/<polyline/g)).toHaveLength(4);
    expect(html).not.toContain("var(--signal)");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/test_calibration.py tests/test_method.py tests/test_site_data.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run
```

Expected: the real-data test **passes already**, since the Task 2 code exists and the cache was refreshed in Task 1. The method, site-data and render tests FAIL (`unexpected keyword argument 'calibration'`, `calibrationHTML is not a function`). This is the first real run; note its result but **change nothing in `assumptions.py`**.

- [ ] **Step 3: Wire it through**

**`src/shave/method.py`:**
1. Change the signature to `def method_payload(scored: pd.DataFrame, regression: dict | None = None, calibration: dict | None = None) -> dict[str, object]:`.
2. Add to the returned dict, after `"regression": …`:

   ```python
        "calibration": calibration
        if calibration is not None
        else {"status": "not yet run; the result is unreported, not failed"},
   ```

3. Delete the `Limitation("no_class_shape_check", …)` entry from `KNOWN_GAPS`.
4. Add as the last entry of `LIMITATIONS`:

   ```python
    Limitation(
        "class_shape_check_is_modest",
        "The class-shape check compares the ComStock-backed aggregate with "
        "National Grid's published class average load shapes. It is a modest "
        "sanity check, not validation: the class average is diversified across "
        "many customers while the aggregate sums each archetype's own worst "
        "billed day, ComStock's weather year is 2018 and the class shapes are a "
        "later year, and it says nothing about the modelled industrial rows.",
    ),
   ```

**`src/shave/site_data.py`:** change the `method.method_payload(...)` call in `enrich` to:

```python
    payload["method"] = method.method_payload(
        scored,
        regression=export_payload.get("regression"),
        calibration=export_payload.get("calibration"),
    )
```

**`scripts/build_site.py`:**
- Change the import to include `calibration`: `from shave import addresses, calibration, export, ingest, mapgeo, pipeline, regression, siting, site_data`.
- Directly after `raw["regression"] = regression.run(scored)`, add:

  ```python
    raw["calibration"] = calibration.run(scored)
  ```

**`public/app.js`:** insert directly before `export function methodHTML(`:

```js
// The MECOLS class-shape check. Every figure, including the percentage and both
// normalised shapes, arrives from calibration.py; this only lays them out.
function calShapeSVG(rate, r) {
  const w = 240;
  const h = 60;
  const x = (i) => (4 + (i / 11) * (w - 8)).toFixed(1);
  const y = (v) => (h - 4 - (Number(v) || 0) * (h - 8)).toFixed(1);
  const line = (vals) => (vals || []).map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    `<figure class="calshape"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" ` +
    `aria-label="${esc(rate)}: monthly billed peak, this tool against MECOLS, each ` +
    `normalised to its own annual maximum.">` +
    `<polyline points="${line(r.peak_shape_mecols)}" fill="none" stroke="var(--ink-3)" ` +
    `stroke-width="1.1" stroke-dasharray="3 2"/>` +
    `<polyline points="${line(r.peak_shape_ours)}" fill="none" stroke="var(--ink-2)" stroke-width="1.4"/>` +
    `</svg><figcaption class="eyebrow">${esc(rate)} &middot; solid = this tool &middot; ` +
    `dashed = MECOLS</figcaption></figure>`
  );
}

export function calibrationHTML(cal) {
  if (!cal || cal.status || !cal.by_rate) {
    return (
      `<p>${esc((cal && cal.status) ||
        "The class-shape check has not been run. Its result is unreported, not failed.")}</p>`
    );
  }
  const c = cal.criterion || {};
  const rates = Object.keys(cal.by_rate);
  const rows = rates
    .map((rate) => {
      const r = cal.by_rate[rate];
      return (
        `<tr><td>${esc(rate)}</td><td class="v r">${esc(r.n_parcels)}</td>` +
        `<td class="v r">${esc(r.months_hour_ok)} of 12</td>` +
        `<td class="v r">${esc(r.months_load_factor_ok)} of 12</td>` +
        `<td>${r.passes ? "Passes" : "Does not pass"}</td></tr>`
      );
    })
    .join("");
  return (
    `<p>The ComStock-backed rows, summed by rate class, against National Grid's ` +
    `published class average load shapes for ${esc(cal.year)}. Declared before the ` +
    `first run: hour of the monthly billed peak within &plusmn;${esc(c.hour_tolerance_h)} h ` +
    `in at least ${esc(c.months_required)} of 12 months, and monthly load factor within ` +
    `&plusmn;${esc(c.load_factor_tolerance_pct)}% in all 12. A modest sanity check, ` +
    `not validation.</p>` +
    `<div class="tablewrap"><table class="assum"><thead><tr><th>Rate</th>` +
    `<th class="r">Parcels</th><th class="r">Hour of peak</th>` +
    `<th class="r">Load factor</th><th>Result</th></tr></thead>` +
    `<tbody>${rows}</tbody></table></div>` +
    rates.map((rate) => calShapeSVG(rate, cal.by_rate[rate])).join("")
  );
}
```

In `methodHTML`, directly after `regressionBlock +` in the `prose` string, add:

```js
    `<h2 style="margin-top:16px">Does the aggregate look like National Grid's classes?</h2>` +
    calibrationHTML(payload.calibration) +
```

Append to `public/app.css`:

```css
/* ---------- calibration ---------- */
.calshape{display:inline-block; margin:8px 16px 0 0}
.calshape svg{display:block; max-width:100%; height:auto}
.calshape figcaption{margin-top:2px}
```

- [ ] **Step 4: Run everything and rebuild**

```bash
uv run pytest
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run
uv run python scripts/build_site.py
uv run python -c "
import json; m = json.load(open('public/data/method.json'))['calibration']
for rate, r in m['by_rate'].items():
    print(rate, 'parcels', r['n_parcels'], '| hour ok', r['months_hour_ok'], '| LF ok', r['months_load_factor_ok'], '| passes', r['passes'])
    print('   peak hour ours  ', r['peak_hour_ours']); print('   peak hour mecols', r['peak_hour_mecols'])
    print('   LF ours  ', r['load_factor_ours']); print('   LF mecols', r['load_factor_mecols'])
"
```

**Pass conditions, declared in advance:**
- Python **1034 passed, 4 deselected** (1030 + 1 calibration + 2 method + 1 site_data);
- render **60 passed**;
- `method.json` carries `calibration.by_rate` for G-2 and G-3.

**The verdict itself is not a pass condition.** Report both rates' figures verbatim, whichever way they fall.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_site.py src/shave/site_data.py src/shave/method.py public/app.js public/app.css \
        tests/conftest.py tests/test_calibration.py tests/test_method.py tests/test_site_data.py web/render.test.js
git commit -m "feat: the MECOLS check runs and is published on the method page

G-2: <months_hour_ok> of 12 hour-of-peak, <months_load_factor_ok> of 12 load factor, <passes>.
G-3: <months_hour_ok> of 12 hour-of-peak, <months_load_factor_ok> of 12 load factor, <passes>.

The criterion was committed in <Task 2 hash> before this first real run and is
unchanged. The method page states the result, the criterion and what the check
cannot show, and retires the gap that said it had not been run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Replace each `<…>` in that message with the figures printed in Step 4 and the hash recorded at the end of Task 2. They are measurements, not choices.

---

## Task 4: Update the review and ship

**Files:**
- Modify: `docs/spec-coverage.md`
- Merge and deploy

- [ ] **Step 1: Update `docs/spec-coverage.md`**

- **Stage 1 row 6:** state `✅`. Notes: `Ran against MECOLS.xlsx (2025) with the criterion committed in <Task 2 hash> before the first run. G-2 <passes / does not pass>, G-3 <passes / does not pass>; figures on the method page.`
- **Success criteria row 4:** state `✅` (the check exists and is published). Evidence: the same sentence.
- **Success criteria heading:** `## Success criteria — 7 of 7`.
- **Header table:**
  - `Success criteria` → `**7 of 7**`
  - `Tests` → `**1034 Python** (4 network-marked, deselected) + **60 render**`
  - `Coverage of spec stages` → `**9 of 12 numbered steps complete**, 1 partial`
- **Stage 1 heading** → `## Stage 1 — 8 of 9 complete, 1 partial`.
- **Pending table:** delete the MECOLS row and renumber.

If either rate does not pass, **add** this to the deliberate divergences, with the real months:

```markdown
**10. The class-shape check does not pass for <rate>.** Hour of peak matched in <n> of 12 months and load
factor in <n> of 12, against a criterion declared before the first run. It is published as a finding: the
aggregate sums each archetype's worst billed day, which a diversified class average does not, and the
criterion was not loosened after the result was seen.
```

- [ ] **Step 2: Commit, merge, deploy**

```bash
git add docs/spec-coverage.md
git commit -m "docs: coverage review after the MECOLS check

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git checkout main && git pull --ff-only origin main
git merge --no-ff feat/mecols-check -m "merge: the MECOLS class-shape check

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" wrangler deploy
```

If `git pull --ff-only` refuses, stop and report.

- [ ] **Step 3: Verify live**

```bash
URL="https://shave.pjayav.workers.dev"; T=$(date +%s)
curl -s -o /dev/null -w 'index %{http_code} %{time_total}s\n' "$URL/"
curl -s "$URL/data/method.json?v=$T" | uv run python -c "import json,sys; c=json.load(sys.stdin)['calibration']; print({k: v['passes'] for k, v in c['by_rate'].items()})"
curl -s "$URL/app.js?v=$T" | grep -c "export function calibrationHTML"
```

Expected: `200`; a dict of both rates' verdicts matching Task 3; `1`. Plain URLs can lag the edge cache for a minute; the cache-busted fetches are authoritative.

---

## Self-Review

**Spec coverage.**
- *"Calibration check against MECOLS.xlsx"* → Tasks 2–3.
- *"normalized to each curve's own annual max"* → `peak_shape_ours` / `peak_shape_mecols`; hour of peak and load factor are scale-free.
- *"ComStock-backed types only"* → the `source == "comstock"` filter.
- *"pass criterion declared before running"* → the Task 2 constants committed before the Task 3 run, with the hash cited in the Task 3 commit and the review.
- *"hour-of-peak within ±1 h in ≥9 of 12 months; monthly load factor within ±15%"* → `compare`, with the month count for load factor fixed at 12 in advance.
- *"Chart goes on the method page"* → `calShapeSVG` in `calibrationHTML`.
- *"modest sanity check, not validation"* → the page copy and the limitation.
- *"per town"* → only Worcester exists at this plan's time. `run` takes whatever scored frame it is given, so the town plan can run it per town without changes.
- *"Apply the per-parcel ±30 min schedule jitter"* applies to modelled rows, which this check excludes by the spec's own rule. ComStock-backed rows have no jitter.

**Placeholder scan.** The `<…>` markers in the Task 3 commit message and the Task 4 doc edit are **measurement slots**: each is filled from a printed figure in the same task, and each is named. No code step contains a placeholder.

**Type consistency.**
- `MonthlyShape` fields (`peak_kw`, `peak_hour`, `energy_kwh`, `hours`) and `load_factor` are used identically in `mecols_monthly`, `bottom_up_monthly`, `compare` and the tests.
- `compare`'s keys (`months_hour_ok`, `months_load_factor_ok`, `passes`, `peak_shape_ours`, `peak_shape_mecols`) match `calibrationHTML` and its tests.
- `criterion.load_factor_tolerance_pct` is produced by `run` and read by the page.
- `method_payload(..., calibration=)` matches `site_data.enrich`.

**Count arithmetic.**
- Python: 1016 → T1 +6 = 1022 → T2 +8 = 1030 → T3 +4 = **1034**.
- Render: 57 → T3 +3 = **60**.

**Risk.** `refresh_cached_profile` compares against S3 today. If NREL has republished the release since the cache was written, the refresh stops with a clear error rather than moving scores. In that case, stop and report; do not force it.
