"""Which fifteen-minute intervals National Grid actually bills for demand.

Rate G-2/G-3 bills monthly demand on the greatest fifteen-minute peak occurring
*during the Peak hours period*. Everything else is invisible to the demand
charge: a 3 a.m. spike is free, a Saturday spike is free, a Thanksgiving spike
is free. A model that takes the raw monthly maximum will therefore price peaks
the customer is not paying for, and every score downstream inflates.

From M.D.P.U. No. 1591:

    "Peak hours will be from 8:00 a.m. to 9:00 p.m. daily on Monday through
     Friday, excluding holidays. Off-Peak hours will be from 9:00 p.m. to 8:00
     a.m. daily Monday through Friday, and all day on Saturdays, Sundays, and
     holidays."

    "The holidays will be: New Years Day, Presidents Day, Memorial Day,
     Independence Day, Columbus Day, Labor Day, Veterans Day, Thanksgiving Day
     and Christmas Day. All holidays will be the nationally observed day."

Nine holidays, not the eleven on the federal list: Martin Luther King Jr. Day
and Juneteenth are billed as ordinary weekdays under this tariff.

"Nationally observed day" is the part that bites. The four fixed-date holidays
shift off a weekend to the nearest weekday, and that shift moves a holiday onto
a day that would otherwise have been billed. Independence Day 2026 falls on a
Saturday, which is already unbilled; observance moves it to Friday 3 July and
removes a real billed weekday from the month.

Year attribution: observed_holidays(year) returns the observed dates of that
year's nine holidays, which is not the same as the observed holidays landing in
that calendar year. New Year's Day 2022 fell on a Saturday, so it was observed
on Friday 31 December 2021. That date belongs to observed_holidays(2022),
because it is the 2022 holiday, even though it lands in 2021. is_holiday()
hides this: it checks both the date's own year and the following year, so
31 December 2021 reads as a holiday regardless of which set it came from.

An interval is identified by its START. The interval starting at 20:45 ends at
21:00 and is billed; the interval starting at 21:00 is not.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from shave.assumptions import INTERVAL_MINUTES, PEAK_HOUR_END, PEAK_HOUR_START

__all__ = [
    "HOLIDAY_NAMES",
    "billed_days",
    "billed_mask",
    "intervals_per_billed_day",
    "is_billed_day",
    "is_billed_interval",
    "is_holiday",
    "observed_holiday_map",
    "observed_holidays",
    "peak_window_minutes",
]

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

# Tariff order, and the order observed_holiday_map returns them in.
HOLIDAY_NAMES: tuple[str, ...] = (
    "New Years Day",
    "Presidents Day",
    "Memorial Day",
    "Independence Day",
    "Labor Day",
    "Columbus Day",
    "Veterans Day",
    "Thanksgiving Day",
    "Christmas Day",
)

_PEAK_START_SEC = PEAK_HOUR_START * 3600
_PEAK_END_SEC = PEAK_HOUR_END * 3600
_INTERVAL_SEC = INTERVAL_MINUTES * 60


# --------------------------------------------------------------------------
# Holidays
# --------------------------------------------------------------------------


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth given weekday of a month, n counting from 1."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last given weekday of a month."""
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _nationally_observed(d: date) -> date:
    """Weekend shift for a fixed-date holiday.

    Saturday moves back to Friday, Sunday forward to Monday. Weekdays stand.
    """
    if d.weekday() == SATURDAY:
        return d - timedelta(days=1)
    if d.weekday() == SUNDAY:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=256)
def observed_holiday_map(year: int) -> dict[str, date]:
    """The nine holidays of `year`, mapped name -> observed date.

    The returned date can fall in the previous calendar year: a Saturday
    New Year's Day is observed on 31 December of the year before.
    """
    return {
        "New Years Day": _nationally_observed(date(year, 1, 1)),
        "Presidents Day": _nth_weekday(year, 2, MONDAY, 3),
        "Memorial Day": _last_weekday(year, 5, MONDAY),
        "Independence Day": _nationally_observed(date(year, 7, 4)),
        "Labor Day": _nth_weekday(year, 9, MONDAY, 1),
        "Columbus Day": _nth_weekday(year, 10, MONDAY, 2),
        "Veterans Day": _nationally_observed(date(year, 11, 11)),
        "Thanksgiving Day": _nth_weekday(year, 11, THURSDAY, 4),
        "Christmas Day": _nationally_observed(date(year, 12, 25)),
    }


@lru_cache(maxsize=256)
def observed_holidays(year: int) -> frozenset[date]:
    """The nine observed dates for `year`'s holidays."""
    return frozenset(observed_holiday_map(year).values())


@lru_cache(maxsize=4096)
def is_holiday(d: date) -> bool:
    """True if `d` is one of the nine, on its nationally observed day.

    Checks the next year as well, because a 31 December date can be the
    following year's New Year's Day observance.
    """
    return d in observed_holidays(d.year) or d in observed_holidays(d.year + 1)


def _holiday_year_span(years: set[int]) -> frozenset[date]:
    """Every observed date that could land inside `years`."""
    span: set[date] = set()
    for y in years:
        span |= observed_holidays(y)
        # A Saturday New Year's Day in y+1 is observed on 31 December of y.
        span |= observed_holidays(y + 1)
    return frozenset(span)


# --------------------------------------------------------------------------
# The peak window
# --------------------------------------------------------------------------


def peak_window_minutes() -> int:
    """Length of the daily peak window in minutes."""
    return (PEAK_HOUR_END - PEAK_HOUR_START) * 60


def intervals_per_billed_day() -> int:
    """Billed intervals on a full billed day, derived from the constants."""
    span, remainder = divmod(peak_window_minutes(), INTERVAL_MINUTES)
    if remainder:
        raise ValueError(
            f"peak window of {peak_window_minutes()} min does not divide "
            f"evenly into {INTERVAL_MINUTES} min intervals"
        )
    return span


def is_billed_day(d: date) -> bool:
    """True on a Monday-to-Friday that is not an observed holiday."""
    return d.weekday() < SATURDAY and not is_holiday(d)


def is_billed_interval(dt: datetime) -> bool:
    """True if the interval STARTING at `dt` is inside the billed window.

    The whole interval must fit: a start at PEAK_HOUR_END - INTERVAL is the
    last billed one, and a start at PEAK_HOUR_END is not billed.
    """
    if not is_billed_day(dt.date()):
        return False
    start = dt.hour * 3600 + dt.minute * 60 + dt.second
    return start >= _PEAK_START_SEC and start + _INTERVAL_SEC <= _PEAK_END_SEC


_EPOCH = date(1970, 1, 1)
_EPOCH_WEEKDAY = _EPOCH.weekday()  # Thursday
_SEC_PER_DAY = 86_400
_NAT = np.iinfo(np.int64).min


def _holiday_days(epoch_day: np.ndarray) -> np.ndarray:
    """Observed holidays covering `epoch_day`, as days since the epoch."""
    if len(epoch_day) == 0:
        return np.zeros(0, dtype=np.int64)
    first = _EPOCH + timedelta(days=int(epoch_day.min()))
    last = _EPOCH + timedelta(days=int(epoch_day.max()))
    holidays = _holiday_year_span(set(range(first.year, last.year + 1)))
    return np.fromiter(
        ((h - _EPOCH).days for h in holidays),
        dtype=np.int64,
        count=len(holidays),
    )


def billed_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """Vectorised is_billed_interval over a DatetimeIndex.

    The pipeline calls this once per building over a year of 15-minute stamps,
    so it stays in numpy. No per-element Python.

    Everything is derived from one epoch-second array rather than from seven
    separate pandas accessors, which is several times faster and keeps
    day-of-week, time-of-day and the holiday lookup consistent by construction.
    """
    index = pd.DatetimeIndex(index)
    if len(index) == 0:
        return np.zeros(0, dtype=bool)

    # A tz-aware index stores UTC. The tariff is written in wall-clock terms,
    # so drop to local wall time before doing any arithmetic.
    if index.tz is not None:
        index = index.tz_localize(None)

    # Cast the unit explicitly. pandas 3 keeps whatever resolution the data
    # arrived in (us for date_range, ns for older parquet), so reading the
    # raw integers without pinning the unit silently rescales every stamp.
    epoch_sec = index.to_numpy(dtype="datetime64[s]", copy=False).astype(np.int64)

    valid = epoch_sec != _NAT
    epoch_day, start = np.divmod(np.where(valid, epoch_sec, 0), _SEC_PER_DAY)

    in_window = (start >= _PEAK_START_SEC) & (
        start + _INTERVAL_SEC <= _PEAK_END_SEC
    )
    weekday = (epoch_day + _EPOCH_WEEKDAY) % 7 < SATURDAY
    not_holiday = ~np.isin(epoch_day, _holiday_days(epoch_day[valid]))

    return valid & in_window & weekday & not_holiday


def billed_days(year: int, month: int) -> list[date]:
    """The non-holiday weekdays in a billing month, in order."""
    days_in_month = calendar.monthrange(year, month)[1]
    return [
        d
        for d in (date(year, month, day) for day in range(1, days_in_month + 1))
        if is_billed_day(d)
    ]
