"""The join: parcels in, scored rows out."""

import numpy as np
import pandas as pd
import pytest

from shave import pipeline
from shave.archetype import INTERVALS_PER_BILLED_DAY, FixtureArchetype
from shave.assumptions import (
    G2_DEMAND_CHARGE_PER_KW,
    PEAK_HOUR_END,
    PEAK_HOUR_START,
    RATED_POWER_KW,
    USABLE_ENERGY_KWH,
)


def _flat_archetype(peak_kw: float, offpeak_kw: float = 10.0) -> FixtureArchetype:
    """A load that sits at `peak_kw` for the whole billed window, every month."""
    return FixtureArchetype(
        monthly_peak_kw=np.full(12, peak_kw),
        windows=np.full((12, INTERVALS_PER_BILLED_DAY), peak_kw),
        offpeak_max_kw=np.full(12, offpeak_kw),
        source="comstock",
    )


def test_a_flat_load_saves_almost_nothing():
    """13 hours at 150 kW is 1,950 kWh above any useful threshold. The battery
    holds 413. A flat load is the wrong site and the score must say so."""
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _flat_archetype(150.0))

    assert row.rate_class == "G-2"

    # Against a flat load the ENERGY budget binds, not the 250 kW power
    # rating: the only way to hold a lower peak for all 13 billed hours is to
    # spread 413.4 kWh across them. 413.4 / 13 = 31.8 kW, which is 12.7% of
    # what the same battery takes off a spike. That gap is the whole reason
    # shape matters more than size, so the test pins the mechanism rather
    # than a round-number bound.
    window_hours = PEAK_HOUR_END - PEAK_HOUR_START
    expected_kw = USABLE_ENERGY_KWH / window_hours
    assert row.monthly_shaveable_kw[0] == pytest.approx(expected_kw, rel=1e-3)
    assert row.annual_savings_usd == pytest.approx(
        expected_kw * 12 * G2_DEMAND_CHARGE_PER_KW, rel=1e-3
    )
    assert row.annual_savings_usd < 0.15 * (
        RATED_POWER_KW * G2_DEMAND_CHARGE_PER_KW * 12
    )
    assert row.shaved_fraction < 0.25


def test_a_spiky_load_of_the_same_average_saves_far_more():
    """The thesis in one assertion. Two sites, same energy, different shape."""
    flat = np.full(INTERVALS_PER_BILLED_DAY, 100.0)
    spiky = np.full(INTERVALS_PER_BILLED_DAY, 60.0)
    # 48 intervals at 60 kW plus 4 at 580 is 5,200 kWh, the same as 52 at 100.
    # (The spike height has to be solved for, not guessed: 4x = 5200 - 2880.)
    spiky[20:24] = 580.0  # one hour of inrush, same daily kWh as flat

    assert spiky.sum() == pytest.approx(flat.sum())

    parcel = {"loc_id": "L1", "sqft": 20_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    flat_row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, flat.max()),
        windows=np.tile(flat, (12, 1)),
        offpeak_max_kw=np.full(12, 20.0),
    ))
    spiky_row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, spiky.max()),
        windows=np.tile(spiky, (12, 1)),
        offpeak_max_kw=np.full(12, 20.0),
    ))

    assert spiky_row.annual_savings_usd > 3 * flat_row.annual_savings_usd


def test_the_power_cap_is_flagged_not_hidden():
    """A site that saturates the battery every month is undersized for it.
    That is a finding — it wants two Powerblocks — not a top-ranked site."""
    window = np.full(INTERVALS_PER_BILLED_DAY, 200.0)
    window[10:12] = 2_000.0  # a very short, very tall spike
    parcel = {"loc_id": "L1", "sqft": 100_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "MED"}

    row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, 2_000.0),
        windows=np.tile(window, (12, 1)),
        offpeak_max_kw=np.full(12, 50.0),
    ))

    assert row.months_at_power_cap == 12
    assert "power_limited" in row.flags
    assert row.annual_savings_usd == pytest.approx(
        RATED_POWER_KW * row.demand_charge_per_kw * 12
    )


def test_sweet_spot_needs_both_the_rate_class_and_the_spikiness():
    """Neither half alone. The band comes from the tariff, not a kW window."""
    flat = pipeline.score_parcel(
        {"loc_id": "A", "sqft": 20_000.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "HIGH"},
        _flat_archetype(150.0),
    )
    assert flat.rate_class == "G-2"
    assert flat.sweet_spot is False, "G-2 but perfectly flat"

    peaks = np.full(12, 150.0)
    peaks[6] = 400.0  # one hot month; 12-month average stays under 200 kW
    spiky = pipeline.score_parcel(
        {"loc_id": "B", "sqft": 20_000.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "HIGH"},
        FixtureArchetype(
            monthly_peak_kw=peaks,
            windows=np.stack([np.full(INTERVALS_PER_BILLED_DAY, p) for p in peaks]),
            offpeak_max_kw=np.full(12, 20.0),
        ),
    )
    assert spiky.rate_class == "G-2"
    assert spiky.sweet_spot is True


def test_below_the_floor_is_dropped_with_a_stated_reason():
    row = pipeline.score_parcel(
        {"loc_id": "C", "sqft": 2_000.0, "archetype": "auto_service",
         "source": "modeled", "confidence": "LOW"},
        _flat_archetype(30.0),
    )
    assert row.keep is False
    assert "below floor" in row.band_reason


def test_a_parcel_with_no_floor_area_is_carried_not_dropped():
    gdf = pd.DataFrame([
        {"loc_id": "L1", "sqft": 0.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "LOW"},
    ])

    out = pipeline.score_parcels(gdf, archetype_factory=lambda p: _flat_archetype(100.0))

    assert len(out) == 1
    assert out["unscored_reason"].iloc[0] == "no_floor_area"
    assert out["annual_savings_usd"].iloc[0] == 0.0


def test_an_unanchored_archetype_is_carried_with_its_reason():
    gdf = pd.DataFrame([
        {"loc_id": "L1", "sqft": 40_000.0, "archetype": "data_hall",
         "source": "modeled", "confidence": "LOW"},
    ])

    out = pipeline.score_parcels(gdf)

    assert out["unscored_reason"].iloc[0] == "no_intensity_anchor"


def test_shaveable_is_measured_against_the_BILLED_peak_only():
    """An outside review of the spec found a 2x overstatement hiding here.

    `shaveable = L_peak(month) - T_month` is only correct when `L_peak` is the
    BILLED peak. If an unbilled spike — a Saturday overtime run, a 3 a.m.
    compressor start — reaches `monthly_peaks()`, the subtraction claims a
    reduction in a demand the customer was never charged for.

    Both implementations mask to billed intervals before taking a monthly
    maximum, so this passes today. It is asserted here because nothing else
    would notice if a future change to either reducer stopped masking.
    """
    window = np.full(INTERVALS_PER_BILLED_DAY, 250.0)
    parcel = {"loc_id": "L1", "sqft": 20_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, 250.0),          # the billed peak
        windows=np.tile(window, (12, 1)),
        offpeak_max_kw=np.full(12, 300.0),           # a HIGHER unbilled spike
    ))

    assert row.peak_kw == pytest.approx(250.0), "the unbilled 300 kW must not rank"
    for billed, shaved in zip(row.monthly_billed_demand_kw, row.monthly_shaveable_kw):
        assert shaved <= billed + 1e-9


def test_scale_extrapolation_is_flagged():
    class _Rep:
        sqft = 10_000.0

    arch = _flat_archetype(500.0)
    arch.profile = _Rep()

    row = pipeline.score_parcel(
        {"loc_id": "L1", "sqft": 120_000.0, "archetype": "retail_standalone",
         "source": "comstock", "confidence": "MED"},
        arch,
    )

    assert "scale_extrapolation" in row.flags


def _july_spike_archetype() -> FixtureArchetype:
    """Flat at 100 kW every month, except a one-hour 400 kW spike in July."""
    windows = np.full((12, INTERVALS_PER_BILLED_DAY), 100.0)
    windows[6, 20:24] = 400.0
    return FixtureArchetype(
        monthly_peak_kw=windows.max(axis=1),
        windows=windows,
        offpeak_max_kw=np.full(12, 60.0),
        source="comstock",
    )


def test_the_peak_day_is_the_month_the_battery_works_hardest():
    """July's spike is where the most kW come off, so July is the day the
    drawer draws -- the same month the recharge test already reads."""
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _july_spike_archetype())

    assert row.peak_day_month == 7
    assert len(row.peak_day_kw) == INTERVALS_PER_BILLED_DAY
    assert max(row.peak_day_kw) == pytest.approx(row.monthly_billed_demand_kw[6])


def test_the_held_level_is_the_billed_peak_less_what_the_battery_removes():
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _july_spike_archetype())

    m = row.peak_day_month - 1
    expected = row.monthly_billed_demand_kw[m] - row.monthly_shaveable_kw[m]
    assert row.peak_day_held_kw == pytest.approx(expected, abs=0.1)
    # 400 kW spike, 250 kW power cap: the battery holds it at 150.
    assert row.peak_day_held_kw == pytest.approx(150.0, abs=0.1)


def test_an_unscored_row_carries_no_day_rather_than_a_fake_one():
    gdf = pd.DataFrame([{"loc_id": "L9", "sqft": None, "archetype": "warehouse",
                         "source": "comstock"}])

    out = pipeline.score_parcels(gdf, archetype_factory=lambda p: _flat_archetype(100.0))

    assert out["peak_day_month"].iloc[0] == 0
    assert tuple(out["peak_day_kw"].iloc[0]) == ()
    assert out["peak_day_held_kw"].iloc[0] == 0.0


def test_the_default_factory_asks_comstock_for_the_parcels_own_county(monkeypatch):
    from shave import comstock

    seen = {}

    def fake_build(name, sqft, county_gisjoin=None, **kwargs):
        seen["county"] = county_gisjoin
        raise comstock.ComStockError("stop here")

    monkeypatch.setattr(comstock, "build_archetype", fake_build)
    base = {"archetype": "warehouse", "sqft": 1000.0, "source": "comstock", "loc_id": "L"}

    with pytest.raises(comstock.ComStockError):
        pipeline.default_archetype_factory({**base, "town_id": 160})
    assert seen["county"] == "G2500170"

    with pytest.raises(comstock.ComStockError):
        pipeline.default_archetype_factory(base)
    assert seen["county"] == "G2500270", "no town means Worcester, as before towns existed"
