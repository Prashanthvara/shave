"""Tests for the billed-window logic.

Every expected date below was checked against a real calendar. The nine
holidays that matter are also cross-checked against pandas' federal holiday
calendar, which is an independent implementation of the same observance rules.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from shave.assumptions import INTERVAL_MINUTES, PEAK_HOUR_END, PEAK_HOUR_START
from shave.billing_window import (
    HOLIDAY_NAMES,
    billed_days,
    billed_mask,
    intervals_per_billed_day,
    is_billed_interval,
    is_holiday,
    observed_holiday_map,
    observed_holidays,
    peak_window_minutes,
)

# --------------------------------------------------------------------------
# The nine holidays, three years, every date verified against a calendar.
# --------------------------------------------------------------------------

EXPECTED = {
    2024: {
        "New Years Day": date(2024, 1, 1),  # Monday
        "Presidents Day": date(2024, 2, 19),
        "Memorial Day": date(2024, 5, 27),
        "Independence Day": date(2024, 7, 4),  # Thursday
        "Labor Day": date(2024, 9, 2),
        "Columbus Day": date(2024, 10, 14),
        "Veterans Day": date(2024, 11, 11),  # Monday
        "Thanksgiving Day": date(2024, 11, 28),
        "Christmas Day": date(2024, 12, 25),  # Wednesday
    },
    2025: {
        "New Years Day": date(2025, 1, 1),  # Wednesday
        "Presidents Day": date(2025, 2, 17),
        "Memorial Day": date(2025, 5, 26),
        "Independence Day": date(2025, 7, 4),  # Friday
        "Labor Day": date(2025, 9, 1),
        "Columbus Day": date(2025, 10, 13),
        "Veterans Day": date(2025, 11, 11),  # Tuesday
        "Thanksgiving Day": date(2025, 11, 27),
        "Christmas Day": date(2025, 12, 25),  # Thursday
    },
    2026: {
        "New Years Day": date(2026, 1, 1),  # Thursday
        "Presidents Day": date(2026, 2, 16),
        "Memorial Day": date(2026, 5, 25),
        "Independence Day": date(2026, 7, 3),  # Jul 4 is a Saturday
        "Labor Day": date(2026, 9, 7),
        "Columbus Day": date(2026, 10, 12),
        "Veterans Day": date(2026, 11, 11),  # Wednesday
        "Thanksgiving Day": date(2026, 11, 26),
        "Christmas Day": date(2026, 12, 25),  # Friday
    },
}


@pytest.mark.parametrize("year", sorted(EXPECTED))
@pytest.mark.parametrize("name", HOLIDAY_NAMES)
def test_each_holiday_resolves(year: int, name: str) -> None:
    assert observed_holiday_map(year)[name] == EXPECTED[year][name]


@pytest.mark.parametrize("year", [1999, 2020, 2024, 2025, 2026, 2031, 2040])
def test_exactly_nine_holidays(year: int) -> None:
    assert len(observed_holiday_map(year)) == 9
    assert len(observed_holidays(year)) == 9
    assert set(observed_holiday_map(year)) == set(HOLIDAY_NAMES)


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_every_expected_date_is_a_holiday(year: int) -> None:
    for expected in EXPECTED[year].values():
        assert is_holiday(expected)


# --------------------------------------------------------------------------
# Observed-day shifts. These are the ones that remove a billed weekday.
# --------------------------------------------------------------------------


def test_new_years_2022_saturday_shifts_back_into_2021() -> None:
    # 1 Jan 2022 was a Saturday, so it is observed on Friday 31 Dec 2021.
    assert date(2022, 1, 1).weekday() == 5
    observed = observed_holiday_map(2022)["New Years Day"]
    assert observed == date(2021, 12, 31)

    # Attribution: the date belongs to the 2022 set, because it is the 2022
    # holiday, and it is NOT in the 2021 set. is_holiday hides the seam.
    assert observed in observed_holidays(2022)
    assert observed not in observed_holidays(2021)
    assert is_holiday(observed)

    # And it really is unbilled, despite being a Friday.
    assert date(2021, 12, 31) not in billed_days(2021, 12)
    assert not is_billed_interval(datetime(2021, 12, 31, 12, 0))


def test_new_years_2023_sunday_shifts_to_monday() -> None:
    assert date(2023, 1, 1).weekday() == 6
    assert observed_holiday_map(2023)["New Years Day"] == date(2023, 1, 2)
    assert is_holiday(date(2023, 1, 2))
    assert date(2023, 1, 2) not in billed_days(2023, 1)


def test_independence_day_2026_saturday_shifts_to_friday() -> None:
    assert date(2026, 7, 4).weekday() == 5
    assert observed_holiday_map(2026)["Independence Day"] == date(2026, 7, 3)
    assert is_holiday(date(2026, 7, 3))
    assert not is_holiday(date(2026, 7, 6))  # not pushed forward as well
    assert date(2026, 7, 3) not in billed_days(2026, 7)


def test_christmas_2027_saturday_shifts_to_friday() -> None:
    assert date(2027, 12, 25).weekday() == 5
    assert observed_holiday_map(2027)["Christmas Day"] == date(2027, 12, 24)
    assert is_holiday(date(2027, 12, 24))
    assert date(2027, 12, 24) not in billed_days(2027, 12)


def test_veterans_day_2029_sunday_shifts_to_monday() -> None:
    assert date(2029, 11, 11).weekday() == 6
    assert observed_holiday_map(2029)["Veterans Day"] == date(2029, 11, 12)
    assert is_holiday(date(2029, 11, 12))
    assert date(2029, 11, 12) not in billed_days(2029, 11)


def test_independence_day_2027_sunday_shifts_to_monday() -> None:
    assert date(2027, 7, 4).weekday() == 6
    assert observed_holiday_map(2027)["Independence Day"] == date(2027, 7, 5)


@pytest.mark.parametrize("year", range(1995, 2061))
def test_observed_holidays_never_land_on_a_weekend(year: int) -> None:
    for name, d in observed_holiday_map(year).items():
        assert d.weekday() < 5, f"{name} {year} landed on {d:%A}"


@pytest.mark.parametrize("year", range(1995, 2061))
def test_fixed_holidays_move_at_most_one_day(year: int) -> None:
    fixed = {
        "New Years Day": date(year, 1, 1),
        "Independence Day": date(year, 7, 4),
        "Veterans Day": date(year, 11, 11),
        "Christmas Day": date(year, 12, 25),
    }
    observed = observed_holiday_map(year)
    for name, actual in fixed.items():
        assert abs((observed[name] - actual).days) <= 1


# --------------------------------------------------------------------------
# Floating holidays are already weekdays and must never shift.
# --------------------------------------------------------------------------

FLOATING = {
    # name -> (weekday, month, valid day range)
    "Presidents Day": (0, 2, range(15, 22)),
    "Memorial Day": (0, 5, range(25, 32)),
    "Labor Day": (0, 9, range(1, 8)),
    "Columbus Day": (0, 10, range(8, 15)),
    "Thanksgiving Day": (3, 11, range(22, 29)),
}


@pytest.mark.parametrize("name", sorted(FLOATING))
@pytest.mark.parametrize("year", range(1995, 2061))
def test_floating_holiday_never_shifts(name: str, year: int) -> None:
    weekday, month, days = FLOATING[name]
    d = observed_holiday_map(year)[name]
    assert d.weekday() == weekday
    assert d.month == month
    assert d.day in days


@pytest.mark.parametrize("year", range(1995, 2061))
def test_memorial_day_is_the_last_monday_in_may(year: int) -> None:
    d = observed_holiday_map(year)["Memorial Day"]
    assert d.weekday() == 0
    assert (d + pd.Timedelta(days=7)).month == 6  # no Monday left in May


@pytest.mark.parametrize("year", range(1995, 2061))
def test_thanksgiving_is_the_fourth_thursday(year: int) -> None:
    d = observed_holiday_map(year)["Thanksgiving Day"]
    assert d.weekday() == 3
    thursdays = [
        day
        for day in range(1, 31)
        if date(year, 11, day).weekday() == 3 and day <= d.day
    ]
    assert len(thursdays) == 4


def test_mlk_and_juneteenth_are_ordinary_billed_weekdays() -> None:
    # The tariff lists nine holidays. The federal list has eleven.
    assert not is_holiday(date(2025, 1, 20))  # MLK Day 2025, a Monday
    assert not is_holiday(date(2025, 6, 19))  # Juneteenth 2025, a Thursday
    assert is_billed_interval(datetime(2025, 1, 20, 10, 0))
    assert is_billed_interval(datetime(2025, 6, 19, 10, 0))


def test_agrees_with_pandas_federal_calendar() -> None:
    """Independent oracle for the eight holidays the two lists share."""
    from pandas.tseries.holiday import USFederalHolidayCalendar

    shared = {
        "New Year's Day": "New Years Day",
        "Washington's Birthday": "Presidents Day",
        "Memorial Day": "Memorial Day",
        "Independence Day": "Independence Day",
        "Labor Day": "Labor Day",
        "Columbus Day": "Columbus Day",
        "Veterans Day": "Veterans Day",
        "Thanksgiving Day": "Thanksgiving Day",
        "Christmas Day": "Christmas Day",
    }
    federal = USFederalHolidayCalendar().holidays(
        start="2015-01-01", end="2040-12-31", return_name=True
    )
    checked = 0
    for stamp, name in federal.items():
        if name not in shared:
            continue
        assert is_holiday(stamp.date()), f"{name} on {stamp.date()} missed"
        checked += 1
    assert checked > 200

    # And nothing extra: every date we call a holiday is on the federal list.
    federal_dates = {stamp.date() for stamp in federal.index}
    for year in range(2016, 2040):
        for d in observed_holidays(year):
            assert d in federal_dates


# --------------------------------------------------------------------------
# Weekends
# --------------------------------------------------------------------------


def test_saturday_and_sunday_are_never_billed() -> None:
    saturday = datetime(2025, 6, 14, 12, 0)
    sunday = datetime(2025, 6, 15, 12, 0)
    assert saturday.weekday() == 5
    assert sunday.weekday() == 6
    assert not is_billed_interval(saturday)
    assert not is_billed_interval(sunday)


def test_no_weekend_day_in_a_month_is_billed() -> None:
    for d in billed_days(2025, 6):
        assert d.weekday() < 5


def test_billed_days_excludes_a_holiday_weekday() -> None:
    june = billed_days(2025, 6)
    assert date(2025, 6, 19) in june  # Juneteenth, billed under this tariff
    may = billed_days(2025, 5)
    assert date(2025, 5, 26) not in may  # Memorial Day
    assert len(may) == 21  # 22 weekdays in May 2025, minus Memorial Day


def test_billed_days_february_leap_year() -> None:
    feb = billed_days(2024, 2)
    assert date(2024, 2, 29) in feb  # a Thursday
    assert date(2024, 2, 19) not in feb  # Presidents Day
    assert len(feb) == 20  # 21 weekdays, minus Presidents Day
    assert feb == sorted(feb)


# --------------------------------------------------------------------------
# Window boundaries. The interval is identified by its start.
# --------------------------------------------------------------------------

BILLED_WEDNESDAY = date(2025, 6, 11)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (0, 0, False),
        (3, 0, False),  # the free 3 a.m. spike
        (7, 45, False),
        (7, 59, False),
        (8, 0, True),  # first billed interval
        (8, 15, True),
        (12, 30, True),
        (20, 30, True),
        (20, 45, True),  # ends exactly at 21:00, still billed
        (20, 46, False),  # would run past 21:00
        (21, 0, False),  # first off-peak interval
        (21, 15, False),
        (23, 45, False),
        (23, 59, False),
    ],
)
def test_window_boundaries(hour: int, minute: int, expected: bool) -> None:
    assert BILLED_WEDNESDAY.weekday() == 2
    dt = datetime(BILLED_WEDNESDAY.year, BILLED_WEDNESDAY.month,
                  BILLED_WEDNESDAY.day, hour, minute)
    assert is_billed_interval(dt) is expected


def test_boundaries_are_derived_from_the_constants() -> None:
    day = BILLED_WEDNESDAY
    first = datetime(day.year, day.month, day.day, PEAK_HOUR_START, 0)
    last = first + pd.Timedelta(
        minutes=peak_window_minutes() - INTERVAL_MINUTES
    ).to_pytimedelta()
    after = datetime(day.year, day.month, day.day, PEAK_HOUR_END, 0)
    before = first - pd.Timedelta(minutes=INTERVAL_MINUTES).to_pytimedelta()

    assert is_billed_interval(first)
    assert is_billed_interval(last)
    assert not is_billed_interval(after)
    assert not is_billed_interval(before)


def test_seconds_inside_an_interval_do_not_extend_the_window() -> None:
    day = BILLED_WEDNESDAY
    # A stamp one second past the last valid start would end past 21:00.
    assert not is_billed_interval(datetime(day.year, day.month, day.day, 20, 45, 1))
    assert is_billed_interval(datetime(day.year, day.month, day.day, 20, 45, 0))


# --------------------------------------------------------------------------
# Derived counts
# --------------------------------------------------------------------------


def test_intervals_per_billed_day() -> None:
    assert intervals_per_billed_day() == 52
    assert peak_window_minutes() == 780
    assert intervals_per_billed_day() == peak_window_minutes() // INTERVAL_MINUTES


def test_a_billed_day_has_exactly_that_many_billed_intervals() -> None:
    day = BILLED_WEDNESDAY
    index = pd.date_range(
        f"{day} 00:00", f"{day} 23:45", freq=f"{INTERVAL_MINUTES}min"
    )
    assert billed_mask(index).sum() == intervals_per_billed_day()


def test_year_total_is_billed_days_times_intervals() -> None:
    index = pd.date_range(
        "2025-01-01 00:00", "2025-12-31 23:45", freq=f"{INTERVAL_MINUTES}min"
    )
    days = sum(len(billed_days(2025, m)) for m in range(1, 13))
    assert billed_mask(index).sum() == days * intervals_per_billed_day()


# --------------------------------------------------------------------------
# The vectorised path must agree with the scalar one, element for element.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("year", [2023, 2024, 2026])
def test_mask_matches_scalar_over_a_full_year(year: int) -> None:
    index = pd.date_range(
        f"{year}-01-01 00:00",
        f"{year}-12-31 23:45",
        freq=f"{INTERVAL_MINUTES}min",
    )
    expected = [is_billed_interval(ts.to_pydatetime()) for ts in index]
    mask = billed_mask(index)
    assert mask.dtype == bool
    assert len(mask) == len(index)
    assert mask.tolist() == expected


def test_leap_year_has_the_extra_day_and_the_right_row_count() -> None:
    index = pd.date_range(
        "2024-01-01 00:00", "2024-12-31 23:45", freq=f"{INTERVAL_MINUTES}min"
    )
    assert len(index) == 366 * 24 * 60 // INTERVAL_MINUTES
    mask = billed_mask(index)
    feb29 = index.normalize() == pd.Timestamp("2024-02-29")
    assert mask[feb29].sum() == intervals_per_billed_day()


def test_mask_matches_scalar_across_a_year_boundary_holiday() -> None:
    # Straddles the 31 Dec 2021 New Year's observance.
    index = pd.date_range(
        "2021-12-27 00:00", "2022-01-05 23:45", freq=f"{INTERVAL_MINUTES}min"
    )
    mask = billed_mask(index)
    expected = [is_billed_interval(ts.to_pydatetime()) for ts in index]
    assert mask.tolist() == expected
    assert mask[index.normalize() == pd.Timestamp("2021-12-31")].sum() == 0


def test_mask_handles_timezone_aware_index() -> None:
    index = pd.date_range(
        "2025-01-01 00:00",
        "2025-12-31 23:45",
        freq=f"{INTERVAL_MINUTES}min",
        tz="America/New_York",
    )
    mask = billed_mask(index)
    expected = [is_billed_interval(ts.to_pydatetime()) for ts in index]
    assert mask.tolist() == expected


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_mask_is_independent_of_datetime_resolution(unit: str) -> None:
    """pandas 3 keeps the incoming resolution instead of forcing nanoseconds.

    Reading the raw epoch integers without pinning a unit rescales every
    stamp, which silently reads a whole year as off-peak.
    """
    index = pd.date_range(
        "2025-01-01 00:00", "2025-12-31 23:45", freq=f"{INTERVAL_MINUTES}min"
    ).as_unit(unit)
    assert index.dtype == f"datetime64[{unit}]"
    days = sum(len(billed_days(2025, m)) for m in range(1, 13))
    assert billed_mask(index).sum() == days * intervals_per_billed_day()


def test_mask_treats_nat_as_unbilled() -> None:
    index = pd.DatetimeIndex(
        [pd.Timestamp("2025-06-11 10:00"), pd.NaT, pd.Timestamp("2025-06-11 03:00")]
    )
    assert billed_mask(index).tolist() == [True, False, False]
    assert billed_mask(pd.DatetimeIndex([pd.NaT])).tolist() == [False]


def test_mask_handles_empty_and_unsorted_input() -> None:
    empty = billed_mask(pd.DatetimeIndex([]))
    assert len(empty) == 0
    assert empty.dtype == bool

    scrambled = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-07-04 10:00"),  # Independence Day, Friday
            pd.Timestamp("2025-06-11 08:00"),
            pd.Timestamp("2025-06-14 12:00"),  # Saturday
            pd.Timestamp("2025-06-11 21:00"),
            pd.Timestamp("2025-06-11 20:45"),
        ]
    )
    assert billed_mask(scrambled).tolist() == [False, True, False, False, True]
