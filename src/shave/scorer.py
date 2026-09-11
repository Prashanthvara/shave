"""Scores how much billed demand a fixed battery can shave, and what that saves.

The one idea that shapes every function here: a utility bills demand as a
MONTHLY MAXIMUM, not as a per-day figure. So the question is never "how much
could the battery shave on the worst day". It is "what threshold could the
battery hold on EVERY billed day of the month", because the single day it
fails to hold sets the bill for all thirty of them.

That changes the math in two places.

  1. The monthly threshold is the WORST of the daily thresholds:
         T_month = max over billed days d of T_min(d)
     Each day gets its own energy budget (the battery recharges overnight), so
     the daily solves are independent, but the monthly answer is their max.
     Scoring only the peak day overstates savings, sometimes badly, because a
     lower-peak day with a long plateau can need a HIGHER threshold than the
     spiky day that sets the bill.

  2. The rate class test is the 12-MONTH AVERAGE of monthly billed demand, not
     the annual peak. For a spiky load the peak sits far above the average, so
     testing on the peak wrongly moves sites onto G-3 at the lower $/kW. G-2
     costs MORE per kW than G-3, so that error silently cuts the score of
     exactly the spiky mid-size sites the product is looking for.

Per day the battery must satisfy two constraints at once:

    energy:  sum(max(0, load - T)) * dt  <=  e_usable
    power:   max(load - T)               <=  p_max

Both left-hand sides are non-increasing in T, so the feasible set is a
half-line [T_min, inf). The energy constraint is solved with a bracketed root
find; the power constraint is closed form (T >= peak - p_max).

There is deliberately no damping term for large sites. The energy constraint
already penalises long plateaus on its own, and an invented weight would
corrupt a ranking that is meant to be read in dollars.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import brentq

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

RateClass = Literal["G-2", "G-3"]

#: Hours per metering interval, from the filed billing determinant.
DEFAULT_DT_HOURS: float = INTERVAL_MINUTES / 60.0

#: Absolute tolerance on the root find, in kW of threshold.
_ROOT_XTOL = 1e-10


def _as_load(load_kw: ArrayLike) -> NDArray[np.float64]:
    """Coerce a load trace to a 1-D float array. Empty stays empty."""
    arr = np.asarray(load_kw, dtype=np.float64).ravel()
    return arr


def energy_above_threshold(
    load_kw: ArrayLike,
    threshold_kw: float,
    dt_hours: float = DEFAULT_DT_HOURS,
) -> float:
    """kWh the battery must deliver to hold the load at or below threshold_kw."""
    arr = _as_load(load_kw)
    if arr.size == 0:
        return 0.0
    return float(np.sum(np.clip(arr - threshold_kw, 0.0, None)) * dt_hours)


def shave_threshold(
    load_kw: ArrayLike,
    dt_hours: float = DEFAULT_DT_HOURS,
    e_usable: float = USABLE_ENERGY_KWH,
    p_max: float = RATED_POWER_KW,
) -> float:
    """Lowest threshold one day's trace can be held to, given energy and power.

    Returns T_min >= 0 such that both the energy and the power constraint hold
    at T_min and at every T above it. Never returns a negative threshold: a
    threshold below zero has no physical reading, and the site cannot bill less
    than nothing.
    """
    arr = _as_load(load_kw)
    if arr.size == 0:
        return 0.0

    peak = float(arr.max())
    if peak <= 0.0:
        # All zero (or all negative, e.g. an export-heavy trace). Nothing to shave.
        return 0.0

    # Power constraint, closed form: max(load - T) = peak - T <= p_max.
    t_power = max(0.0, peak - max(p_max, 0.0))

    # Energy constraint. E(T) is convex, piecewise linear and non-increasing.
    total_above_zero = energy_above_threshold(arr, 0.0, dt_hours)
    if e_usable <= 0.0:
        # No usable energy at all: the battery cannot discharge, so the only
        # holdable threshold is the peak itself.
        t_energy = peak
    elif total_above_zero <= e_usable:
        # The whole day's above-zero energy fits in the battery. The energy
        # constraint never binds and the threshold clamps at zero.
        t_energy = 0.0
    else:
        # f(0) > 0 and f(peak) = -e_usable < 0, so [0, peak] brackets the root.
        t_energy = float(
            brentq(
                lambda t: energy_above_threshold(arr, t, dt_hours) - e_usable,
                0.0,
                peak,
                xtol=_ROOT_XTOL,
                maxiter=200,
            )
        )

    return max(0.0, t_power, t_energy)


def shaveable_kw(
    load_kw: ArrayLike,
    dt_hours: float = DEFAULT_DT_HOURS,
    e_usable: float = USABLE_ENERGY_KWH,
    p_max: float = RATED_POWER_KW,
) -> float:
    """kW of one day's peak the battery can remove. Always >= 0."""
    arr = _as_load(load_kw)
    if arr.size == 0:
        return 0.0
    peak = float(arr.max())
    if peak <= 0.0:
        return 0.0
    reduction = peak - shave_threshold(arr, dt_hours, e_usable, p_max)
    assert reduction >= -_ROOT_XTOL, "shaveable_kw went negative"
    return max(0.0, reduction)


def monthly_billed_demand(day_traces: Sequence[ArrayLike]) -> float:
    """Billing demand for a month: the max across every billed day.

    A month with no billed days (all holidays filtered out, or a meter gap)
    bills no demand, so this returns 0.0 rather than raising or returning NaN.
    Downstream that reads as "nothing to shave and nothing to save", which is
    the honest answer for a month we have no data for.
    """
    peaks = [
        float(a.max()) for a in map(_as_load, day_traces) if a.size and a.max() > 0.0
    ]
    return max(peaks) if peaks else 0.0


def month_threshold(
    day_traces: Sequence[ArrayLike],
    dt_hours: float = DEFAULT_DT_HOURS,
    e_usable: float = USABLE_ENERGY_KWH,
    p_max: float = RATED_POWER_KW,
) -> float:
    """The threshold holdable on EVERY billed day: max of the daily thresholds."""
    thresholds = [
        shave_threshold(a, dt_hours, e_usable, p_max)
        for a in map(_as_load, day_traces)
        if a.size
    ]
    return max(thresholds) if thresholds else 0.0


def monthly_shaveable_kw(
    day_traces: Sequence[ArrayLike],
    dt_hours: float = DEFAULT_DT_HOURS,
    e_usable: float = USABLE_ENERGY_KWH,
    p_max: float = RATED_POWER_KW,
) -> float:
    """kW off the month's billed demand: month peak minus the holdable threshold."""
    peak = monthly_billed_demand(day_traces)
    if peak <= 0.0:
        return 0.0
    reduction = peak - month_threshold(day_traces, dt_hours, e_usable, p_max)
    # The month threshold is the max of per-day thresholds and every per-day
    # threshold is at most that day's peak, so it cannot exceed the month peak.
    assert reduction >= -_ROOT_XTOL, "monthly shaveable_kw went negative"
    return max(0.0, reduction)


def average_billed_demand(monthly_billed_demand: Sequence[float]) -> float:
    """The 12-month average that the tariff's rate class test reads."""
    values = np.asarray(list(monthly_billed_demand), dtype=np.float64)
    if values.size == 0:
        return 0.0
    return float(values.mean())


def peak_to_average(values: ArrayLike) -> float:
    """Spikiness ratio. Zero mean returns 0.0 rather than dividing by zero."""
    arr = _as_load(values)
    if arr.size == 0:
        return 0.0
    mean = float(arr.mean())
    if mean <= 0.0:
        return 0.0
    return float(arr.max()) / mean


def assign_rate_class(monthly_billed_demand: Sequence[float]) -> RateClass:
    """G-2 or G-3 from the 12-month AVERAGE of monthly billed demand.

    The tariff test is the average, not the annual peak. Testing on the peak
    moves spiky sites onto G-3, whose demand charge is roughly a third lower,
    and so understates their savings by roughly a third. That inversion (the
    smaller rate class costing MORE per kW) is the whole reason the target band
    is mid-size rather than large.
    """
    avg_12mo = average_billed_demand(monthly_billed_demand)
    return "G-3" if avg_12mo >= G3_THRESHOLD_KW else "G-2"


def demand_charge_for(rate_class: str) -> float:
    """Distribution demand charge in $/kW-month for a rate class."""
    if rate_class == "G-2":
        return G2_DEMAND_CHARGE_PER_KW
    if rate_class == "G-3":
        return G3_DEMAND_CHARGE_PER_KW
    raise ValueError(f"unknown rate class: {rate_class!r}")


def required_charge_kw(e_used_kwh: float, offpeak_hours: float) -> float:
    """The average rate that refills `e_used_kwh` across the off-peak window.

    This is what the site actually has to draw, which is never more than
    USABLE_ENERGY_KWH / OFFPEAK_HOURS ~= 37.6 kW. The charger's 250 kW rating
    is what it *could* draw, and using the rating where the requirement
    belongs is a 6.6x overstatement of the recharge footprint.
    """
    if offpeak_hours <= 0.0:
        return float("inf")
    return e_used_kwh / offpeak_hours


def recharge_feasible(
    e_used_kwh: float,
    offpeak_hours: float,
    l_offpeak_max_kw: float,
    t_month: float,
) -> bool:
    """Can the battery refill off-peak without creating a new billed peak?

    Two independent predicates, both required:

      1. There is enough off-peak time: the required rate is within what the
         charger can deliver. CHARGER_KW is the right bound here -- it is a
         capability question.
      2. Charging on top of the existing off-peak load stays strictly below
         the monthly threshold, so the recharge does not become the new
         billing determinant. The REQUIRED rate is the right term here, not
         the charger rating: the site draws what it needs, not what the
         hardware could take. Testing the rating made this flag fire on 98%
         of kept Worcester rows and told the reader nothing.

    Returns False rather than raising so the caller can flag the row
    "recharge-constrained" and keep it in the table.
    """
    if offpeak_hours <= 0.0:
        return False
    needed = required_charge_kw(e_used_kwh, offpeak_hours)
    time_ok = needed <= CHARGER_KW
    headroom_ok = (l_offpeak_max_kw + needed) < t_month
    return bool(time_ok and headroom_ok)


def annual_savings_usd(
    shaveable_kw_by_month: Sequence[float],
    rate_class: str,
) -> float:
    """Total annual demand-charge saving. This is the ranking key, in dollars.

    No composite score and no weights: a dollar is already comparable across
    sites, and any weighting we invented would only make it less so.
    """
    charge = demand_charge_for(rate_class)
    values = np.asarray(list(shaveable_kw_by_month), dtype=np.float64)
    if values.size == 0:
        return 0.0
    return float(np.sum(np.clip(values, 0.0, None)) * charge)


def band_filter(
    avg_12mo: float,
    peak_to_avg: float,
    rate_class: str,
) -> dict[str, object]:
    """Screening flags. Returns flags, never raises.

    drop        below the demand floor there is not enough demand charge to
                be worth a conversation, whatever the shape.
    sweet_spot  G-2 (the expensive rate) plus a spiky shape. Both halves come
                from the tariff rather than from an invented window.
    """
    drop = avg_12mo < MIN_AVG_DEMAND_KW
    sweet_spot = (
        not drop and rate_class == "G-2" and peak_to_avg > SWEET_SPOT_PEAK_TO_AVG
    )
    reason: str | None = None
    if drop:
        reason = f"avg_12mo {avg_12mo:.1f} kW below floor {MIN_AVG_DEMAND_KW:.1f} kW"
    return {
        "drop": drop,
        "keep": not drop,
        "sweet_spot": sweet_spot,
        "reason": reason,
    }
