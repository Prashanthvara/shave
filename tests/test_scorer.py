"""Tests for the shave scorer.

The regression test at the top of this file guards the bug that mattered most:
rate class assigned from the annual peak instead of the 12-month average.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from shave import scorer
from shave.assumptions import (
    CHARGER_KW,
    G2_DEMAND_CHARGE_PER_KW,
    G3_DEMAND_CHARGE_PER_KW,
    G3_THRESHOLD_KW,
    INTERVAL_MINUTES,
    MIN_AVG_DEMAND_KW,
    RATED_POWER_KW,
    SWEET_SPOT_PEAK_TO_AVG,
    USABLE_ENERGY_KWH,
)
from shave.scorer import (
    DEFAULT_DT_HOURS,
    annual_savings_usd,
    assign_rate_class,
    average_billed_demand,
    band_filter,
    demand_charge_for,
    energy_above_threshold,
    month_threshold,
    monthly_billed_demand,
    monthly_shaveable_kw,
    peak_to_average,
    recharge_feasible,
    required_charge_kw,
    shave_threshold,
    shaveable_kw,
)

DT = DEFAULT_DT_HOURS  # 0.25 h
PEAK_INTERVALS = 52  # 08:00-21:00 at 15 minutes


def flat_day(kw: float, n: int = PEAK_INTERVALS) -> np.ndarray:
    return np.full(n, float(kw))


def spike_day(base: float, peak: float, spike_intervals: int, n: int = PEAK_INTERVALS):
    trace = np.full(n, float(base))
    trace[n // 2 : n // 2 + spike_intervals] = float(peak)
    return trace


# ---------------------------------------------------------------------------
# MANDATORY REGRESSION TEST
# ---------------------------------------------------------------------------


def test_REGRESSION_rate_class_uses_12mo_average_not_annual_peak():
    """REGRESSION: 240 kW monthly peaks, 150 kW 12-month average -> G-2.

    An earlier revision assigned the rate class from the annual peak. The peak
    here (240 kW) is above G3_THRESHOLD_KW, so that revision returned G-3 and
    priced this site at $10.48/kW instead of $15.06/kW, cutting its score by
    about 30% and pushing the whole sweet-spot population out of the band.
    The tariff test is the AVERAGE, and this site's average is 150 kW.
    """
    monthly = [240.0, 240.0] + [132.0] * 10
    assert max(monthly) == 240.0
    assert average_billed_demand(monthly) == pytest.approx(150.0)

    # The exact conditions that fooled the old code.
    assert max(monthly) >= G3_THRESHOLD_KW
    assert average_billed_demand(monthly) < G3_THRESHOLD_KW

    rate_class = assign_rate_class(monthly)
    assert rate_class == "G-2"
    assert demand_charge_for(rate_class) == pytest.approx(15.06)
    assert demand_charge_for(rate_class) == G2_DEMAND_CHARGE_PER_KW

    # And the price of getting it wrong, stated in dollars.
    shaveable = [40.0] * 12
    right = annual_savings_usd(shaveable, "G-2")
    wrong = annual_savings_usd(shaveable, "G-3")
    assert right > wrong
    assert (right - wrong) / right > 0.25


def test_g2_costs_more_per_kw_than_g3():
    """The core product insight. If this ever inverts, the ranking is wrong."""
    assert G2_DEMAND_CHARGE_PER_KW > G3_DEMAND_CHARGE_PER_KW


# ---------------------------------------------------------------------------
# Rate class boundary
# ---------------------------------------------------------------------------


def test_average_exactly_at_threshold_is_g3():
    """The tariff test is >=, so exactly 200.0 kW average lands on G-3."""
    monthly = [G3_THRESHOLD_KW] * 12
    assert average_billed_demand(monthly) == pytest.approx(200.0)
    assert assign_rate_class(monthly) == "G-3"


def test_average_just_below_threshold_is_g2():
    monthly = [199.99] * 12
    assert assign_rate_class(monthly) == "G-2"


def test_rate_class_boundary_is_driven_by_the_mean_of_a_mixed_year():
    # Mean is exactly 200.0 despite wildly different months.
    monthly = [400.0] * 6 + [0.0] * 6
    assert average_billed_demand(monthly) == pytest.approx(200.0)
    assert assign_rate_class(monthly) == "G-3"


def test_empty_year_falls_back_to_g2():
    assert assign_rate_class([]) == "G-2"
    assert average_billed_demand([]) == 0.0


def test_demand_charge_rejects_unknown_class():
    with pytest.raises(ValueError):
        demand_charge_for("G-1")


# ---------------------------------------------------------------------------
# shave_threshold: degenerate inputs
# ---------------------------------------------------------------------------


def test_empty_array_returns_zero():
    assert shave_threshold(np.array([])) == 0.0
    assert shaveable_kw(np.array([])) == 0.0


def test_all_zeros_returns_zero():
    zeros = np.zeros(PEAK_INTERVALS)
    assert shave_threshold(zeros) == 0.0
    assert shaveable_kw(zeros) == 0.0


def test_threshold_is_never_negative():
    tiny = np.array([1.0, 2.0, 1.5])
    assert shave_threshold(tiny, DT, e_usable=1e9, p_max=1e9) == 0.0


def test_zero_usable_energy_means_nothing_shaved():
    load = spike_day(80.0, 300.0, 2)
    t = shave_threshold(load, DT, e_usable=0.0, p_max=RATED_POWER_KW)
    assert t == pytest.approx(300.0)
    assert shaveable_kw(load, DT, e_usable=0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# shave_threshold: which constraint binds
# ---------------------------------------------------------------------------


def test_flat_load_is_limited_by_power_when_energy_is_free():
    """Flat load with unlimited energy: only the inverter rating binds."""
    load = flat_day(400.0)
    t = shave_threshold(load, DT, e_usable=1e9, p_max=RATED_POWER_KW)
    assert t == pytest.approx(400.0 - RATED_POWER_KW)
    assert shaveable_kw(load, DT, e_usable=1e9) == pytest.approx(RATED_POWER_KW)


def test_flat_load_is_limited_by_energy_with_the_real_battery():
    """13 h of flat load needs far more energy than the pack holds."""
    load = flat_day(100.0)
    hours = PEAK_INTERVALS * DT
    t = shave_threshold(load)
    assert t == pytest.approx(100.0 - USABLE_ENERGY_KWH / hours)
    assert energy_above_threshold(load, t) == pytest.approx(USABLE_ENERGY_KWH)
    # Only about a third of a small flat load comes off.
    assert shaveable_kw(load) < 35.0


def test_energy_larger_than_all_available_clamps_threshold_to_zero():
    """e_usable exceeds every kWh above any threshold, and peak <= p_max."""
    load = spike_day(10.0, 200.0, 2, n=8)
    assert load.max() <= RATED_POWER_KW
    total = energy_above_threshold(load, 0.0)
    t = shave_threshold(load, DT, e_usable=total * 2.0, p_max=RATED_POWER_KW)
    assert t == 0.0
    assert shaveable_kw(load, DT, e_usable=total * 2.0) == pytest.approx(load.max())


def test_peak_below_p_max_means_power_never_binds():
    load = spike_day(60.0, 240.0, 6)
    assert load.max() < RATED_POWER_KW
    t = shave_threshold(load)
    # The threshold sits exactly where the energy budget is exhausted.
    assert energy_above_threshold(load, t) == pytest.approx(USABLE_ENERGY_KWH, rel=1e-9)
    # Raising p_max changes nothing, which is what "never binds" means.
    assert shave_threshold(load, DT, USABLE_ENERGY_KWH, 1e9) == pytest.approx(t)


def test_power_binds_when_the_spike_towers_over_the_rating():
    load = spike_day(50.0, 900.0, 1)
    t = shave_threshold(load)
    assert t >= 900.0 - RATED_POWER_KW
    assert shaveable_kw(load) == pytest.approx(RATED_POWER_KW)


def test_returned_threshold_satisfies_both_constraints():
    load = spike_day(90.0, 520.0, 5)
    t = shave_threshold(load)
    assert energy_above_threshold(load, t) <= USABLE_ENERGY_KWH + 1e-6
    assert float(load.max()) - t <= RATED_POWER_KW + 1e-9


# ---------------------------------------------------------------------------
# THE PRODUCT THESIS: shape beats size
# ---------------------------------------------------------------------------


def test_machine_shop_spike_shaves_far_more_than_hospital_plateau():
    """Same peak kW, opposite outcomes. This is the entire product thesis.

    Machine shop: 80 kW base with a short 300 kW spike.
    Hospital:     80 kW base with a six-hour 300 kW plateau.
    Both peak at 300 kW, so a peak-only screen would rank them identically.
    The energy constraint is what separates them.
    """
    machine_shop = spike_day(80.0, 300.0, 2)  # 30 minutes at peak
    hospital = spike_day(80.0, 300.0, 24)  # 6 hours at peak

    assert machine_shop.max() == hospital.max() == 300.0

    shop_kw = shaveable_kw(machine_shop)
    hosp_kw = shaveable_kw(hospital)

    assert shop_kw > hosp_kw
    assert shop_kw / 300.0 > 0.75  # most of the peak comes off
    assert hosp_kw / 300.0 < 0.30  # barely dents it
    assert shop_kw > 3.0 * hosp_kw

    # And in dollars, on the same rate class.
    shop_savings = annual_savings_usd([shop_kw] * 12, "G-2")
    hosp_savings = annual_savings_usd([hosp_kw] * 12, "G-2")
    assert shop_savings > 3.0 * hosp_savings


# ---------------------------------------------------------------------------
# Monthly aggregation
# ---------------------------------------------------------------------------


def test_monthly_billed_demand_is_the_max_across_billed_days():
    days = [flat_day(100.0), spike_day(80.0, 260.0, 2), flat_day(120.0)]
    assert monthly_billed_demand(days) == pytest.approx(260.0)


def test_month_with_zero_billed_days_is_zero_not_an_error():
    """Defined behaviour: no billed days bills no demand and saves nothing."""
    assert monthly_billed_demand([]) == 0.0
    assert month_threshold([]) == 0.0
    assert monthly_shaveable_kw([]) == 0.0
    # Same for a month whose day traces are all empty arrays.
    empty_days = [np.array([]), np.array([])]
    assert monthly_billed_demand(empty_days) == 0.0
    assert monthly_shaveable_kw(empty_days) == 0.0
    assert annual_savings_usd([monthly_shaveable_kw([])] * 12, "G-2") == 0.0


def test_month_threshold_is_set_by_the_hardest_day_not_the_peak_day():
    """The bug this guards: scoring only the peak day overstates savings.

    The peak day is a short 300 kW spike, easy to shave. A different day peaks
    lower at 260 kW but holds it for six hours, so it needs a much higher
    threshold. The month is billed on the threshold that holds on both.
    """
    peak_day = spike_day(80.0, 300.0, 2)
    hard_day = spike_day(80.0, 260.0, 24)
    days = [peak_day, hard_day]

    t_peak_day_only = shave_threshold(peak_day)
    t_month = month_threshold(days)

    assert t_month > t_peak_day_only
    assert t_month == pytest.approx(shave_threshold(hard_day))

    peak_day_only_estimate = shaveable_kw(peak_day)
    honest = monthly_shaveable_kw(days)
    assert honest < peak_day_only_estimate
    assert honest == pytest.approx(300.0 - t_month)


def test_monthly_shaveable_is_never_negative():
    """Invariant, across a deliberately awkward mix of days."""
    cases = [
        [flat_day(500.0), spike_day(10.0, 900.0, 1), flat_day(1.0)],
        [np.zeros(4), flat_day(0.0)],
        [flat_day(1000.0, n=96)],
        [spike_day(0.0, 1e5, 1)],
    ]
    for days in cases:
        assert monthly_shaveable_kw(days) >= 0.0
        assert monthly_shaveable_kw(days) <= monthly_billed_demand(days) + 1e-9


def test_annual_savings_is_a_plain_dollar_sum():
    shaveable = [10.0, 20.0, 30.0] + [0.0] * 9
    assert annual_savings_usd(shaveable, "G-2") == pytest.approx(
        60.0 * G2_DEMAND_CHARGE_PER_KW
    )
    assert annual_savings_usd(shaveable, "G-3") == pytest.approx(
        60.0 * G3_DEMAND_CHARGE_PER_KW
    )
    assert annual_savings_usd([], "G-2") == 0.0


# ---------------------------------------------------------------------------
# recharge_feasible
# ---------------------------------------------------------------------------


def test_recharge_feasible_when_the_window_is_long_enough():
    assert recharge_feasible(e_used_kwh=USABLE_ENERGY_KWH, offpeak_hours=11.0)


def test_recharge_infeasible_when_the_energy_cannot_fit_the_window():
    """413 kWh into 1 h needs more than the charger can deliver."""
    e_used = CHARGER_KW * 1.0 + 50.0
    assert e_used / 1.0 > CHARGER_KW
    assert not recharge_feasible(e_used, 1.0)
    assert not recharge_feasible(5000.0, 1.0)


def test_recharge_with_no_offpeak_window_returns_false_not_zero_division():
    assert not recharge_feasible(100.0, 0.0)
    assert not recharge_feasible(100.0, -3.0)


def test_the_charger_rating_boundary_is_inclusive():
    """Exactly at the rating is deliverable; a hair above is not.

    Inherited from the deleted headroom-strictness test: the boundary was
    worth pinning, and the time predicate is where a boundary now lives.
    """
    hours = 2.0
    at_rating = CHARGER_KW * hours
    assert recharge_feasible(at_rating, hours)
    assert not recharge_feasible(at_rating + 1.0, hours)


def test_overnight_load_cannot_veto_a_recharge_because_it_is_never_billed():
    """REGRESSION, and the reason the headroom predicate was removed.

    Earlier revisions also asked whether charging would push the site's
    overnight load above the threshold it is holding. It cannot: the filed
    tariff bills the greatest fifteen-minute peak *during the Peak hours
    period*, 08:00-21:00 weekdays, so load between 21:00 and 08:00 is never
    billed at any magnitude.

    That test compared an unbilled quantity against a billed threshold. On
    real Worcester data it failed 661 of 737 kept rows, and 300 of 300
    sampled rows failed on it alone -- not because the recharge was large
    (37.6 kW against a 250 kW charger) but because most commercial buildings
    draw more overnight than the daytime level they shave to. A warning on
    90% of a table about a charge the tariff does not levy is misinformation.

    `recharge_feasible` therefore takes no overnight-load argument at all. If
    someone reintroduces one, this test is the record of why they should not.
    """
    import inspect

    params = set(inspect.signature(recharge_feasible).parameters)
    assert params == {"e_used_kwh", "offpeak_hours"}, (
        f"recharge_feasible grew a parameter: {sorted(params)}. Overnight load "
        "is unbilled under this tariff; the real limit is service capacity, "
        "which is not in any public assessor record."
    )

    # A site drawing an enormous overnight load still recharges fine.
    assert recharge_feasible(e_used_kwh=USABLE_ENERGY_KWH, offpeak_hours=11.0)


# ---------------------------------------------------------------------------
# band_filter
# ---------------------------------------------------------------------------


def test_band_filter_drops_below_the_demand_floor():
    flags = band_filter(MIN_AVG_DEMAND_KW - 0.01, 3.0, "G-2")
    assert flags["drop"] is True
    assert flags["keep"] is False
    assert flags["sweet_spot"] is False  # a dropped site is never sweet spot
    assert flags["reason"]


def test_band_filter_keeps_a_flat_g2_site_without_calling_it_sweet_spot():
    flags = band_filter(120.0, SWEET_SPOT_PEAK_TO_AVG, "G-2")
    assert flags["drop"] is False
    assert flags["keep"] is True
    assert flags["sweet_spot"] is False  # ratio must exceed, not equal


def test_band_filter_flags_the_sweet_spot():
    flags = band_filter(150.0, SWEET_SPOT_PEAK_TO_AVG + 0.5, "G-2")
    assert flags["drop"] is False
    assert flags["sweet_spot"] is True


def test_band_filter_spiky_g3_site_is_kept_but_not_sweet_spot():
    """G-3 pays less per kW, so a spiky large site is not the target."""
    flags = band_filter(600.0, 3.0, "G-3")
    assert flags["keep"] is True
    assert flags["sweet_spot"] is False


def test_band_filter_at_the_floor_exactly_is_kept():
    assert band_filter(MIN_AVG_DEMAND_KW, 2.0, "G-2")["drop"] is False


def test_band_filter_never_raises_on_junk():
    for flags in (
        band_filter(0.0, 0.0, "G-2"),
        band_filter(float("nan"), float("nan"), "G-3"),
        band_filter(-10.0, 99.0, "unknown"),
    ):
        assert set(flags) == {"drop", "keep", "sweet_spot", "reason"}


def test_peak_to_average_helper():
    assert peak_to_average([100.0, 100.0, 400.0]) == pytest.approx(2.0)
    assert peak_to_average([]) == 0.0
    assert peak_to_average([0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

loads = st.lists(
    st.floats(min_value=0.0, max_value=5_000.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=96,
)
budgets = st.floats(
    min_value=0.0, max_value=50_000.0, allow_nan=False, allow_infinity=False
)
powers = st.floats(
    min_value=0.0, max_value=5_000.0, allow_nan=False, allow_infinity=False
)


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(load=loads, e_usable=budgets, p_max=powers)
def test_property_threshold_is_feasible_and_non_negative(load, e_usable, p_max):
    arr = np.asarray(load)
    t = shave_threshold(arr, DT, e_usable, p_max)

    assert t >= 0.0
    assert np.isfinite(t)
    assert t <= arr.max() + 1e-9

    scale = max(1.0, e_usable, float(arr.max()) * arr.size * DT)
    assert energy_above_threshold(arr, t, DT) <= e_usable + 1e-6 * scale
    assert float(arr.max()) - t <= p_max + 1e-6 * max(1.0, p_max)

    assert shaveable_kw(arr, DT, e_usable, p_max) >= 0.0


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(load=loads, e_small=budgets, extra=budgets, p_max=powers)
def test_property_threshold_is_monotone_in_usable_energy(load, e_small, extra, p_max):
    """More storage never makes the holdable threshold worse."""
    arr = np.asarray(load)
    e_big = e_small + extra

    t_small = shave_threshold(arr, DT, e_small, p_max)
    t_big = shave_threshold(arr, DT, e_big, p_max)

    tol = 1e-6 * max(1.0, float(arr.max()))
    assert t_big <= t_small + tol


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(load=loads, e_usable=budgets, p_small=powers, extra=powers)
def test_property_threshold_is_monotone_in_rated_power(load, e_usable, p_small, extra):
    """A bigger inverter never makes the holdable threshold worse."""
    arr = np.asarray(load)
    t_small = shave_threshold(arr, DT, e_usable, p_small)
    t_big = shave_threshold(arr, DT, e_usable, p_small + extra)
    assert t_big <= t_small + 1e-6 * max(1.0, float(arr.max()))


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    days=st.lists(loads, min_size=1, max_size=6),
    e_usable=budgets,
    p_max=powers,
)
def test_property_month_threshold_dominates_every_day(days, e_usable, p_max):
    """The monthly answer is never more optimistic than any single day."""
    traces = [np.asarray(d) for d in days]
    t_month = month_threshold(traces, DT, e_usable, p_max)
    for trace in traces:
        assert t_month >= shave_threshold(trace, DT, e_usable, p_max) - 1e-9
    assert monthly_shaveable_kw(traces, DT, e_usable, p_max) >= 0.0


# ---------------------------------------------------------------------------
# Constants are imported, not restated
# ---------------------------------------------------------------------------


def test_interval_constant_drives_the_default_timestep():
    assert DEFAULT_DT_HOURS == pytest.approx(INTERVAL_MINUTES / 60.0)


def test_required_charge_rate_is_energy_over_the_window():
    assert scorer.required_charge_kw(413.4, 11.0) == pytest.approx(37.5818, rel=1e-4)
    assert scorer.required_charge_kw(0.0, 11.0) == 0.0

