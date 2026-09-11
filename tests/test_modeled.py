"""The modelled-industrial magnitude chain.

ComStock covers none of the industrial ICP. For those 653 Worcester parcels
magnitude comes from published intensity and shape comes from parameters, and
the load factor that joins them is derived from the shape rather than asserted.
"""

import numpy as np
import pytest

from shave import modeled
from shave.archetype import INTERVALS_PER_BILLED_DAY, ModeledArchetype
from shave.assumptions import (
    ELECTRIC_INTENSITY_KWH_PER_SQFT_YR,
    PEAK_HOUR_END,
    PEAK_HOUR_START,
    UNANCHORED_ARCHETYPES,
)


def test_full_day_shape_agrees_with_the_billed_window():
    """One shape function, two views. If these drift, every modelled magnitude
    is computed against a shape the scorer never sees."""
    params = modeled.SHAPE_PARAMS["industrial_manufacturing"]
    full = modeled.full_day_shape(params, "weekday", 6)

    assert full.shape == (96,)

    # Same parcel id on both sides. `full_day_shape` probes with a fixed id,
    # and the per-parcel jitter is applied as an array roll, so comparing two
    # different ids compares two different rolls -- see
    # test_jitter_does_not_change_anything_the_scorer_computes below.
    arch = ModeledArchetype(
        parcel_id="__shape_probe__", peak_kw=1.0, **modeled.archetype_kwargs(params)
    )
    window = arch._day_shape("weekday", 6)

    start = PEAK_HOUR_START * 4
    end = PEAK_HOUR_END * 4
    assert end - start == INTERVALS_PER_BILLED_DAY
    np.testing.assert_allclose(full[start:end], window, rtol=1e-12)


def test_the_billed_window_is_a_slice_of_the_day_for_every_parcel():
    """The invariant the magnitude chain rests on.

    `peak_kw` is the true 24-hour peak, and billed demand is the billed
    window measured against that peak. That only means anything if the window
    and the day are the same function of clock time for the same parcel.

    Jitter used to be applied as `np.roll` on whichever grid was requested,
    which permuted the 52-point window and the 96-point day differently: a
    laboratory's 08:00 start could land at 07:45 on the day grid while staying
    inside the window on the window grid. The window was then not a slice of
    the day and the two maxima were not comparable. Jitter is now a shift in
    time, so this holds for every parcel id.
    """
    start, end = PEAK_HOUR_START * 4, PEAK_HOUR_END * 4
    for name in modeled.SHAPE_PARAMS:
        params = modeled.SHAPE_PARAMS[name]
        for parcel_id in ("__shape_probe__", "x", "LOC1", "M_348_9999", "M_348_12"):
            arch = ModeledArchetype(
                parcel_id=parcel_id, peak_kw=1.0, **modeled.archetype_kwargs(params)
            )
            day = arch._day_shape("weekday", 6, hours=modeled.FULL_DAY_HOURS)
            window = arch._day_shape("weekday", 6)
            np.testing.assert_allclose(
                day[start:end], window, rtol=1e-12,
                err_msg=f"{name} / {parcel_id}: window is not a slice of the day",
            )


def test_jitter_actually_moves_the_shape():
    """The diversity the jitter exists to create must be real, or every
    modelled parcel of a type peaks at the same minute and any aggregate
    check is meaningless."""
    params = modeled.SHAPE_PARAMS["industrial_manufacturing"]
    kw = dict(peak_kw=137.0, **modeled.archetype_kwargs(params))
    a = ModeledArchetype(parcel_id="__shape_probe__", **kw)   # jitter 0
    b = ModeledArchetype(parcel_id="x", **kw)                 # jitter -2
    assert not np.allclose(a.peak_day_window(6), b.peak_day_window(6))

def test_every_modeled_archetype_has_a_plausible_load_factor():
    """A guard rail on the parameters, not on the code. A shape that implies a
    load factor no real building has means the parameters are wrong."""
    low, high = modeled.LOAD_FACTOR_BAND
    for name, params in modeled.SHAPE_PARAMS.items():
        lf = modeled.implied_load_factor(params)
        assert low <= lf <= high, f"{name} implies a load factor of {lf:.3f}"


def test_the_chain_reproduces_the_published_annual_energy():
    """Magnitude is only defensible if the round trip closes: a peak derived
    from an intensity must integrate back to that intensity's annual kWh."""
    name, sqft = "industrial_manufacturing", 20_000.0
    params = modeled.SHAPE_PARAMS[name]

    peak = modeled.peak_kw_for(name, sqft)
    lf = modeled.implied_load_factor(params)
    recovered = peak * lf * 8760.0

    expected = ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[name] * sqft
    assert recovered == pytest.approx(expected, rel=1e-9)


def test_peak_scales_linearly_with_floor_area():
    a = modeled.peak_kw_for("laboratory", 10_000.0)
    b = modeled.peak_kw_for("laboratory", 20_000.0)
    assert b == pytest.approx(2.0 * a)


def test_a_machine_shop_lands_in_the_g2_band():
    """The thesis, as a test. A mid-size single-shift manufacturer should come
    out near the 200 kW rate boundary, which is where the expensive tariff and
    the spiky shape overlap. If this drifts far, the parameters have."""
    peak = modeled.peak_kw_for("industrial_manufacturing", 20_000.0)
    assert 150.0 <= peak <= 260.0, f"20k sq ft machine shop peaks at {peak:.0f} kW"


def test_an_unanchored_archetype_refuses_rather_than_guessing():
    for name in UNANCHORED_ARCHETYPES:
        with pytest.raises(modeled.ModeledMagnitudeError, match="no published"):
            modeled.peak_kw_for(name, 10_000.0)


def test_every_modeled_crosswalk_type_is_anchored_or_named_unanchored():
    """The crosswalk and this module must not disagree about what is
    scoreable. A type in neither dict is a row that fails at scoring time."""
    from shave.crosswalk import MODELED_TYPES

    covered = set(ELECTRIC_INTENSITY_KWH_PER_SQFT_YR) | set(UNANCHORED_ARCHETYPES)
    assert MODELED_TYPES <= covered, f"unhandled: {MODELED_TYPES - covered}"
    assert set(modeled.SHAPE_PARAMS) == set(ELECTRIC_INTENSITY_KWH_PER_SQFT_YR)


def test_zero_and_negative_floor_area_raise():
    for bad in (0.0, -1.0):
        with pytest.raises(modeled.ModeledMagnitudeError, match="positive"):
            modeled.peak_kw_for("auto_service", bad)


def test_modeled_archetype_reports_a_positive_overnight_load():
    """A laboratory starts at 08:00 and LOC42 has zero jitter, so its inrush
    sits at the first billed interval and the overnight base is below it."""
    arch = modeled.build_modeled_archetype("laboratory", "LOC42", 20_000.0)

    night = arch.offpeak_max(6)
    day = float(arch.peak_day_window(6).max())

    assert 0.0 < night < day, "overnight base is real but below the shift peak"
    with pytest.raises(ValueError):
        arch.offpeak_max(0)


def test_an_unbilled_peak_never_sets_billed_magnitude():
    """The rule the measured half already follows, now pinned for the
    modelled half.

    `peak_kw` is the true 24-hour annual peak. A machine shop starts at 06:30,
    so its startup inrush — the spikiest thing it does — happens before the
    billed window opens and is never billed. Its billed peak must therefore be
    STRICTLY BELOW peak_kw. Scaling the billed window to peak_kw instead would
    inflate billed demand 1.55x for the 115 Worcester parcels on this
    archetype, and 1.22x for the 112 on cold storage.
    """
    for name, floor in (("industrial_manufacturing", 1.4), ("industrial_warehouse_process", 1.1)):
        arch = modeled.build_modeled_archetype(name, "LOC1", 20_000.0)
        billed = float(arch.monthly_peaks().max())
        assert billed > 0
        assert billed < arch.peak_kw, f"{name}: unbilled peak is setting billed demand"
        assert arch.peak_kw / billed > floor, (
            f"{name}: expected the pre-08:00 inrush to sit well above the billed "
            f"plateau, got a ratio of {arch.peak_kw / billed:.3f}"
        )
        # And the overnight maximum is that unbilled inrush, above the billed peak.
        assert arch.offpeak_max(6) > billed


def test_an_in_window_peak_still_equals_peak_kw():
    """Where a parcel's true peak does fall inside 08:00-21:00, billed demand
    equals peak_kw and nothing has changed. LOC42 has zero jitter and these
    five archetypes start at or after 08:00."""
    for name in ("laboratory", "ice_rink", "auto_service", "auto_dealership", "university"):
        arch = modeled.build_modeled_archetype(name, "LOC42", 20_000.0)
        assert float(arch.monthly_peaks().max()) == pytest.approx(arch.peak_kw, rel=1e-9)


def test_billed_demand_never_exceeds_the_true_annual_peak():
    """The universal guarantee, over every archetype and a spread of jitters.

    Billed demand is the billed window measured against the building's true
    24-hour peak, so it can equal that peak but must never exceed it. Before
    the scaling was fixed it exceeded it by 1.55x for a machine shop.
    """
    for name in modeled.SHAPE_PARAMS:
        for parcel_id in ("LOC42", "LOC1", "x", "LOC7", "M_348_9999", "P100"):
            arch = modeled.build_modeled_archetype(name, parcel_id, 20_000.0)
            billed = float(arch.monthly_peaks().max())
            assert 0.0 < billed <= arch.peak_kw * (1 + 1e-9), (
                f"{name} / {parcel_id}: billed {billed:.2f} exceeds true peak "
                f"{arch.peak_kw:.2f}"
            )


def test_a_boundary_start_can_have_its_inrush_pushed_out_of_the_window():
    """Jitter is a real shift in time, so an archetype starting exactly at
    08:00 can have its startup inrush moved to 07:45 for some parcels — and
    that inrush is then genuinely unbilled.

    This is the same phenomenon as the machine shop's 06:30 start, reached by
    a different route, and it is why billed demand is a per-parcel quantity
    rather than a per-archetype one.
    """
    early = modeled.build_modeled_archetype("laboratory", "LOC1", 20_000.0)   # jitter -1
    on_time = modeled.build_modeled_archetype("laboratory", "LOC42", 20_000.0)  # jitter 0

    assert float(early.monthly_peaks().max()) < float(on_time.monthly_peaks().max())
    assert early.peak_kw == pytest.approx(on_time.peak_kw), (
        "the building is the same size; only when it starts differs"
    )


def test_modeled_archetype_satisfies_the_protocol_again():
    """Task 1 added `offpeak_max` to the protocol and implemented it on the
    ComStock side only, leaving this one structurally incomplete on purpose.
    This closes that gap."""
    from shave.archetype import Archetype

    arch = modeled.build_modeled_archetype("laboratory", "LOC2", 15_000.0)
    assert isinstance(arch, Archetype)
    assert arch.source == "modeled"
    assert arch.monthly_peaks().shape == (12,)
    assert arch.peak_day_window(7).shape == (INTERVALS_PER_BILLED_DAY,)
    assert isinstance(arch.offpeak_max(7), float)


def test_the_superseded_asserted_intensity_api_is_gone():
    """`scale_to_floor_area(archetype, sqft, kw_per_1000sqft)` took an ASSERTED
    intensity. The shipped chain derives the load factor from the declared
    shape and takes magnitude from published intensity -- the opposite, and
    the whole point of the modelled-magnitude work.

    It survived with zero callers. A superseded mechanism left in the public
    surface is a trap: the next reader uses it and gets a magnitude this
    project deliberately stopped producing.
    """
    from shave import archetype

    assert not hasattr(archetype, "scale_to_floor_area"), (
        "the asserted-intensity path is back; magnitude must come from "
        "modeled.peak_kw_for, which derives the load factor rather than "
        "taking one"
    )
