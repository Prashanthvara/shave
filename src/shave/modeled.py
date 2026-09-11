"""Magnitude for the archetypes ComStock does not model.

ComStock covers 14 commercial building types and no industry. Against
Powertown's published ICP that is 3 sectors of 11. For the rest, this module
supplies a peak kW from two published inputs and one derivation:

    annual_kwh = intensity x sqft                 published, CBECS or MECS
    implied_LF = annual_energy / (8760 x peak)    derived from the shape
    peak_kw    = annual_kwh / 8760 / implied_LF

`peak_kw` is the building's TRUE annual peak, over all 24 hours -- not
its billed peak. Both the load factor above and `ModeledArchetype`'s
scaling are measured against the full day, so a peak that falls outside
08:00-21:00 never sets billed magnitude. For a machine shop starting at
06:30 the startup inrush is genuinely unbilled, and the billed window
sees only the plateau that follows it.

The load factor is not asserted anywhere. It falls out of the shape
parameters, which are declared below with the reasoning behind each. That
matters: an asserted load factor and an asserted intensity would put the
chain two assumptions deep with no way to see either.

These shapes remain the weakest link in the project and the method page says
so in those words. There is no US industrial ground truth to check them
against.
"""

from __future__ import annotations

import calendar

import numpy as np

from shave.archetype import (
    FULL_DAY_HOURS,
    INTERVALS_PER_DAY,
    STEP_HOURS,
    ModeledArchetype,
)
from shave.assumptions import (
    ELECTRIC_INTENSITY_KWH_PER_SQFT_YR,
    HOURS_PER_YEAR,
    UNANCHORED_ARCHETYPES,
)

__all__ = [
    "FULL_DAY_HOURS",
    "INTERVALS_PER_DAY",
    "LOAD_FACTOR_BAND",
    "ModeledMagnitudeError",
    "SHAPE_PARAMS",
    "STEP_HOURS",
    "archetype_kwargs",
    "build_modeled_archetype",
    "full_day_shape",
    "implied_load_factor",
    "peak_kw_for",
]

#: Sanity band on the derived load factor. A shape outside this produced a
#: load factor no real commercial or light-industrial building has, which
#: means the parameters are wrong rather than the building being unusual.
#: Trips loudly at import-time test, not silently at scoring time.
LOAD_FACTOR_BAND = (0.20, 0.80)


class ModeledMagnitudeError(ValueError):
    """This archetype cannot be given a defensible magnitude."""


#: Shape parameters per modelled archetype. These are the four numbers a
#: measured industrial dataset supplies -- load factor, hour of peak, spike
#: duration, base/process split -- expressed as the template parameters that
#: produce them. EWELD values swap in here if its licence clears; nothing
#: else changes when they do.
SHAPE_PARAMS: dict[str, dict[str, float | bool]] = {
    # Single day shift with a hard inrush at start-up. The inrush is the whole
    # reason a machine shop is a better battery site than a bigger flat load.
    "industrial_manufacturing": dict(
        base_fraction=0.25, shift_start_hour=6.5, shift_end_hour=15.5,
        spike_minutes=20.0, spike_fraction=0.55,
        refrigeration=False, cooling_fraction=0.15,
    ),
    # Compressors run around the clock, so the base is high and the shape is
    # flat -- which is exactly why cold storage saves less per kW of battery
    # than its intensity suggests. The model should show that, not hide it.
    "industrial_warehouse_process": dict(
        base_fraction=0.55, shift_start_hour=6.0, shift_end_hour=18.0,
        spike_minutes=15.0, spike_fraction=0.25,
        refrigeration=True, cooling_fraction=0.30,
    ),
    # Fume hoods and environmental rooms never stop; the occupied block adds
    # comparatively little.
    "laboratory": dict(
        base_fraction=0.60, shift_start_hour=8.0, shift_end_hour=18.0,
        spike_minutes=10.0, spike_fraction=0.15,
        refrigeration=False, cooling_fraction=0.25,
    ),
    # Ice plant cycles continuously; the occupied block is evening skate and
    # league play, which runs past the billed window's close.
    "ice_rink": dict(
        base_fraction=0.50, shift_start_hour=9.0, shift_end_hour=22.0,
        spike_minutes=15.0, spike_fraction=0.30,
        refrigeration=True, cooling_fraction=0.20,
    ),
    # Lifts, compressors and welders on a short day, near-nothing overnight.
    "auto_service": dict(
        base_fraction=0.20, shift_start_hour=8.0, shift_end_hour=17.0,
        spike_minutes=15.0, spike_fraction=0.35,
        refrigeration=False, cooling_fraction=0.15,
    ),
    # Showroom lighting runs long and evenly; the service bay adds the morning
    # step. Lot lighting is the overnight base.
    "auto_dealership": dict(
        base_fraction=0.30, shift_start_hour=8.0, shift_end_hour=20.0,
        spike_minutes=10.0, spike_fraction=0.20,
        refrigeration=False, cooling_fraction=0.25,
    ),
    # Campus load is long and flat, with research and residential base.
    "university": dict(
        base_fraction=0.45, shift_start_hour=8.0, shift_end_hour=21.0,
        spike_minutes=10.0, spike_fraction=0.15,
        refrigeration=False, cooling_fraction=0.22,
    ),
}


def archetype_kwargs(params: dict[str, float | bool]) -> dict[str, float | bool]:
    """The subset of `params` that `ModeledArchetype` accepts as keywords."""
    return dict(params)


def full_day_shape(
    params: dict[str, float | bool], day_type: str, month: int
) -> np.ndarray:
    """The normalised 24-hour shape, at the tariff's interval resolution.

    Delegates to `ModeledArchetype._day_shape` with a full-day hour grid, so
    there is exactly one implementation of the shape. A second one here would
    drift from the one the scorer reads, and the magnitude would then be
    computed against a building that does not exist.

    The parcel id is fixed, so the per-parcel jitter does not move the derived
    load factor from parcel to parcel. Jitter shifts when a peak happens; it
    does not change how much energy a day uses.
    """
    probe = ModeledArchetype(
        parcel_id="__shape_probe__", peak_kw=1.0, **archetype_kwargs(params)
    )
    return probe._day_shape(day_type, month, hours=FULL_DAY_HOURS)


def implied_load_factor(params: dict[str, float | bool], year: int = 2018) -> float:
    """Annual load factor implied by the shape parameters alone.

    Counts real weekdays, Saturdays and Sundays in `year` -- the default is
    2018 to match the ComStock AMY2018 weather year the measured half uses --
    integrates the shape over each, and divides the mean by the annual peak.
    """
    peak = max(float(full_day_shape(params, "weekday", m).max()) for m in range(1, 13))
    if peak <= 0.0:
        raise ModeledMagnitudeError("shape has no positive peak")

    total_kwh = 0.0
    for month in range(1, 13):
        counts = {"weekday": 0, "saturday": 0, "sunday": 0}
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            weekday = calendar.weekday(year, month, day)
            key = "weekday" if weekday < 5 else ("saturday" if weekday == 5 else "sunday")
            counts[key] += 1
        for day_type, n in counts.items():
            total_kwh += (
                n * float(full_day_shape(params, day_type, month).sum()) * STEP_HOURS
            )

    return total_kwh / (HOURS_PER_YEAR * peak)


def peak_kw_for(archetype_name: str, sqft: float) -> float:
    """Peak kW for one parcel, by the published chain.

    Raises rather than guessing when the archetype has no anchor. A silently
    invented magnitude is worse than a row the table marks unscored: the row
    ranks, and nothing on the page says it should not have.
    """
    if sqft <= 0:
        raise ModeledMagnitudeError(f"sqft must be positive, got {sqft}")
    if archetype_name in UNANCHORED_ARCHETYPES:
        raise ModeledMagnitudeError(
            f"{archetype_name!r} has no published electricity intensity; "
            "score it as unscored rather than inventing one"
        )
    try:
        intensity = ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[archetype_name]
        params = SHAPE_PARAMS[archetype_name]
    except KeyError as exc:
        raise ModeledMagnitudeError(
            f"{archetype_name!r} has no modelled shape or intensity"
        ) from exc

    annual_kwh = intensity * sqft
    return annual_kwh / HOURS_PER_YEAR / implied_load_factor(params)


def build_modeled_archetype(
    archetype_name: str, parcel_id: str, sqft: float
) -> ModeledArchetype:
    """A modelled archetype scaled to one parcel, magnitude from the chain."""
    return ModeledArchetype(
        parcel_id=parcel_id,
        peak_kw=peak_kw_for(archetype_name, sqft),
        **archetype_kwargs(SHAPE_PARAMS[archetype_name]),
    )
