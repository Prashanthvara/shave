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
