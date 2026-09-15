import pytest
from dataclasses import replace

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


@pytest.mark.network
def test_worcester_county_index_matches_the_probed_shape():
    # Re-probed 2026-09-10. The brief's 19,077 is the raw row count of the
    # county metadata parquet, which holds one row per (building, census
    # tract) -- ComStock apportions each simulated building across the tracts
    # it stands in. Distinct buildings number 2,443. The brief asserted both
    # 19,077 rows and a unique bldg_id, which the file cannot satisfy at once;
    # load_county_index returns one row per building, so uniqueness is the
    # half that holds.
    idx = comstock.load_county_index()
    assert len(idx) == 2443
    assert idx["bldg_id"].is_unique
    counts = idx["building_type"].value_counts()
    assert counts["SmallOffice"] == 367  # 4,586 building-tract rows
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


import pandas as pd


def _index(rows):
    return pd.DataFrame(rows, columns=["bldg_id", "building_type", "sqft"])





def test_unknown_building_type_raises():
    idx = _index([(1, "Warehouse", 10000.0)])
    with pytest.raises(comstock.ComStockError, match="no ComStock buildings"):
        comstock.select_representative(idx, "Hospital")


import numpy as np

from shave.archetype import INTERVALS_PER_BILLED_DAY
from shave.assumptions import INTERVAL_MINUTES, PEAK_HOUR_START
from shave.billing_window import billed_days


def _synthetic_year(peak_by_month, offpeak_spike_kw=0.0):
    """A year of 15-minute energy readings with a known billed peak per month."""
    idx = pd.date_range("2018-01-01 00:00", periods=35040, freq="15min")
    kw = pd.Series(10.0, index=idx)
    for month, peak in enumerate(peak_by_month, start=1):
        # No fixed day-of-month is a weekday in every month of 2018 (April,
        # July, September and December each land the 15th on a weekend), so
        # the injected peak has to land on a real billed day, discovered at
        # runtime rather than hard-coded.
        day = billed_days(2018, month)[0]
        sel = (idx.month == month) & (idx.day == day.day) & (idx.hour == 14)
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


def _slot(hour, minute=0):
    """Expected position within the billed window, from the tariff constants."""
    return ((hour - PEAK_HOUR_START) * 60 + minute) // INTERVAL_MINUTES


def test_window_is_the_real_peak_day_not_a_per_slot_composite():
    """A per-slot maximum across days must not be able to pass this.

    Day 1 has a broad 80 kW plateau (its own max is 80). Day 2 has a single
    120 kW spike and is otherwise at baseline (its own max is 120, so day 2
    is the true peak day). A correct implementation returns day 2's whole
    shape: baseline everywhere except the spike slot. An implementation that
    instead took the per-slot maximum across all billed days would show 80
    kW in the plateau slots too, because day 1's plateau beats the
    baseline there. Asserting the plateau slots are baseline -- not 80 --
    is what a composite-day bug cannot satisfy.
    """
    month = 1
    days = billed_days(2018, month)
    day1, day2 = days[0], days[1]

    idx = pd.date_range("2018-01-01 00:00", periods=35040, freq="15min")
    kw = pd.Series(10.0, index=idx)

    plateau_hours = [9, 10, 11, 12]
    plateau_slots = [_slot(h) for h in plateau_hours]
    kw[(idx.day == day1.day) & (idx.month == month) & idx.hour.isin(plateau_hours)] = 80.0

    spike_hour = 15
    spike_slot = _slot(spike_hour)
    kw[(idx.day == day2.day) & (idx.month == month) & (idx.hour == spike_hour)
       & (idx.minute == 0)] = 120.0

    df = pd.DataFrame({
        "timestamp": idx,
        comstock.TOTAL_ELECTRICITY_COL: kw.to_numpy() / comstock.KWH_PER_INTERVAL_TO_KW,
    })
    prof = comstock.reduce_from_frame(1, df)

    assert prof.monthly_peak_kw[month - 1] == pytest.approx(120.0)
    assert prof.windows[month - 1][spike_slot] == pytest.approx(120.0)
    # The plateau slots belong to day 1, which lost. A composite-across-days
    # implementation would show 80.0 here; the real peak day (day 2) is at
    # baseline in these slots.
    for s in plateau_slots:
        assert prof.windows[month - 1][s] == pytest.approx(10.0), (
            f"slot {s} is {prof.windows[month - 1][s]}, not the day-2 "
            "baseline -- looks like a per-slot composite across days"
        )


def test_slot_index_matches_the_tariff_derived_formula():
    """An off-by-one in the slot formula shifts every curve and must be caught.

    Injects distinguishable values at the first billed minute (08:00), a
    mid-window time (14:00) and the last billed interval's start (20:45) on
    one known billed day, and asserts each lands at the position the tariff
    constants say it should -- not merely somewhere in the 52-length array.
    """
    month = 1
    day = billed_days(2018, month)[0]

    idx = pd.date_range("2018-01-01 00:00", periods=35040, freq="15min")
    kw = pd.Series(10.0, index=idx)

    on_day = (idx.day == day.day) & (idx.month == month)
    kw[on_day & (idx.hour == PEAK_HOUR_START) & (idx.minute == 0)] = 101.0
    kw[on_day & (idx.hour == 14) & (idx.minute == 0)] = 102.0
    kw[on_day & (idx.hour == 20) & (idx.minute == 45)] = 103.0

    df = pd.DataFrame({
        "timestamp": idx,
        comstock.TOTAL_ELECTRICITY_COL: kw.to_numpy() / comstock.KWH_PER_INTERVAL_TO_KW,
    })
    prof = comstock.reduce_from_frame(1, df)
    window = prof.windows[month - 1]

    assert _slot(PEAK_HOUR_START) == 0
    assert _slot(20, 45) == INTERVALS_PER_BILLED_DAY - 1 == 51

    assert window[0] == pytest.approx(101.0)                       # 08:00
    assert window[_slot(14)] == pytest.approx(102.0)                # 14:00 -> 24
    assert window[INTERVALS_PER_BILLED_DAY - 1] == pytest.approx(103.0)  # 20:45


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
    # A real profile is not a flat schedule -- it swings across the year.
    # The brief's original check assumed summer cooling always beats winter
    # heating (`monthly_peak_kw[6] > monthly_peak_kw[0]`). Verified against
    # the actual representative -- Worcester County SmallOffice bldg_id
    # 94133, sqft-median of the cohort -- and against a spread sample of
    # four other SmallOffice buildings in the same cohort: the direction
    # flips by building (electric-resistance-heated offices run hotter in
    # January than July; more cooling-dominant ones run the other way), so
    # asserting a fixed season would be asserting a coincidence, not a
    # property of the reduction. Real month-to-month variation is the part
    # that's actually true of every building.
    assert prof.monthly_peak_kw.std() > 0


def test_committed_fixture_loads_and_has_a_real_shape():
    df = pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet")
    prof = comstock.ReducedProfile.from_frame(df)
    assert prof.monthly_peak_kw.shape == (12,)
    assert prof.windows.shape == (12, INTERVALS_PER_BILLED_DAY)
    assert (prof.monthly_peak_kw > 0).all()
    # A real office is not flat across the billed day.
    assert prof.windows[6].std() > 0


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


class _StubConn:
    """A connect() stand-in whose only job is to survive conn.close()."""

    def close(self) -> None:
        pass


def test_cache_hit_preserves_widened_and_cohort_size(tmp_path, monkeypatch):
    """The thin-cohort flag must survive a cache round trip.

    Hospital's cohort in Worcester County is exactly 2 buildings, so
    select_representative marks that Representative widened=True,
    cohort_size=2. A cache MISS must carry that onto the returned
    ComStockArchetype, and a cache HIT that reads the same cached parquet
    back -- with every network-touching function replaced by an
    AssertionError -- must report the identical flag, not silently drop back
    to the dataclass default. That silent drop is exactly the bug this test
    exists to catch.
    """
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))

    rep = comstock.Representative(
        bldg_id=prof.bldg_id,
        building_type="Hospital",
        sqft=prof.sqft,
        cohort_size=2,
        widened=True,
    )

    monkeypatch.setattr(comstock, "connect", lambda: _StubConn())
    # One Hospital row: the county "has the type", so the statewide-pool
    # branch is not taken and this test keeps exercising the flag round trip.
    monkeypatch.setattr(
        comstock, "load_county_index",
        lambda *a, **k: pd.DataFrame(
            [{"bldg_id": 1, "building_type": "Hospital", "sqft": 10_000.0}]))
    monkeypatch.setattr(comstock, "select_representative", lambda *a, **k: rep)
    monkeypatch.setattr(comstock, "reduce_timeseries", lambda *a, **k: prof)

    miss = comstock.build_archetype(
        "hospital", sqft=50_000.0, county_gisjoin="G2500270", cache_dir=tmp_path)
    assert miss.widened is True
    assert miss.cohort_size == 2

    def explode(*a, **k):
        raise AssertionError("cache hit: the network was used")
    monkeypatch.setattr(comstock, "connect", explode)
    monkeypatch.setattr(comstock, "load_county_index", explode)
    monkeypatch.setattr(comstock, "select_representative", explode)
    monkeypatch.setattr(comstock, "reduce_timeseries", explode)

    hit = comstock.build_archetype(
        "hospital", sqft=50_000.0, county_gisjoin="G2500270", cache_dir=tmp_path)
    assert hit.widened == miss.widened is True
    assert hit.cohort_size == miss.cohort_size == 2


def test_missing_widened_and_cohort_size_columns_default_safely():
    """A column-less frame must default to False/None, not merely not crash.

    The committed fixture predates the widened/cohort_size columns, so
    from_frame has to tolerate their absence. But tolerating absence and
    defaulting to the RIGHT values are different claims -- silently
    defaulting widened=False on a column-less file would report a thin
    cohort as well-sampled, exactly what the flag exists to catch. This
    builds a frame with those two columns stripped out and asserts the
    specific values from_frame falls back to, rather than only asserting
    the load doesn't raise.
    """
    prof = comstock.reduce_from_frame(
        1, _synthetic_year([100.0] * 12), sqft=5000.0)
    df = prof.to_frame().drop(columns=["widened", "cohort_size"])
    back = comstock.ReducedProfile.from_frame(df)
    assert back.widened is False
    assert back.cohort_size is None


def test_committed_fixture_defaults_widened_and_cohort_size():
    """The real, committed old-format fixture also gets the safe defaults."""
    df = pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet")
    assert "widened" not in df.columns and "cohort_size" not in df.columns
    prof = comstock.ReducedProfile.from_frame(df)
    assert prof.widened is False
    assert prof.cohort_size is None


def test_scale_rejects_zero_or_negative_parcel_sqft():
    """A malformed parcel area must raise, not quietly produce a $0 building.

    ComStockArchetype._scale already guarded the representative's floor
    area (profile.sqft); it did not guard the parcel's own sqft. A parcel
    with sqft=0 silently yielded an all-zero profile, and a negative sqft
    yielded negative "peaks" -- both look like a parcel that legitimately
    has nothing to shave rather than a data error, so nothing downstream
    would ever flag it.
    """
    prof = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))
    for bad_sqft in (0.0, -100.0):
        a = comstock.ComStockArchetype(profile=prof, sqft=bad_sqft)
        with pytest.raises(comstock.ComStockError, match="parcel sqft must be positive"):
            a.monthly_peaks()
        with pytest.raises(comstock.ComStockError, match="parcel sqft must be positive"):
            a.peak_day_window(1)


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


def _reader(intensities=None):
    """A fake timeseries read. `intensities` maps bldg_id -> W/sqft; anything
    absent is flat at 4.0, so a test that does not care about intensity gets a
    cohort the tie-break orders by bldg_id."""
    intensities = intensities or {}

    def read(bldg_id, conn=None, sqft=None):
        w = intensities.get(bldg_id, 4.0)
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, w * sqft / 1000.0),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    return read


def test_cohort_size_counts_the_whole_cohort_not_the_sample():
    """Selection reads 15 buildings; `cohort_size` must still report all 31.
    If it reported the sample, every cohort would look thin and `widened`
    would fire on well-sampled types."""
    idx = _index([(i, "Warehouse", float(sqft))
                  for i, sqft in enumerate(range(1000, 1000 + 31 * 100, 100))])
    rep = comstock.select_representative(idx, "Warehouse", read_profile=_reader())
    assert rep.cohort_size == 31
    assert rep.widened is False
    assert rep.bldg_id in set(idx["bldg_id"]), "must name a real building"


def test_median_of_an_even_sample_takes_the_lower_of_the_two_middles():
    # Deterministic tie-break: never interpolate, always name a real building.
    idx = _index([(i, "Warehouse", 1000.0) for i in range(4)])
    intensities = {0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0}
    rep = comstock.select_representative(
        idx, "Warehouse", min_cohort=4, read_profile=_reader(intensities)
    )
    assert rep.peak_intensity_w_per_sqft == pytest.approx(2.0), "lower middle of 4"
    assert rep.bldg_id == 1


def test_small_cohort_widens_and_says_so():
    idx = _index([(1, "Hospital", 300000.0), (2, "Hospital", 375000.0)])
    rep = comstock.select_representative(
        idx, "Hospital", min_cohort=30, read_profile=_reader()
    )
    assert rep.widened is True
    assert rep.cohort_size == 2


def test_selection_is_deterministic():
    idx = _index([(i, "Warehouse", float(s))
                  for i, s in enumerate([500, 900, 700, 1100, 300] * 8)])
    read = _reader({i: 1.0 + (i % 7) for i in range(40)})
    picks = {comstock.select_representative(
        idx, "Warehouse", min_cohort=5, read_profile=read).bldg_id
        for _ in range(10)}
    assert len(picks) == 1


def test_reduce_captures_the_overnight_maximum():
    """The recharge test needs the off-peak load, which the billed mask drops."""
    index = pd.date_range("2018-01-01", "2018-12-31 23:45", freq="15min")
    kw = np.full(index.size, 10.0)
    # A 300 kW spike at 03:00 on 8 March: outside the billed window, so it must
    # not reach monthly_peak_kw, and must reach offpeak_max_kw for March.
    night = (index.month == 3) & (index.day == 8) & (index.hour == 3)
    kw[night] = 300.0
    raw = pd.DataFrame({
        "timestamp": index,
        comstock.TOTAL_ELECTRICITY_COL: kw / comstock.KWH_PER_INTERVAL_TO_KW,
    })

    profile = comstock.reduce_from_frame(1, raw, sqft=1000.0)

    assert profile.offpeak_max_kw.shape == (12,)
    assert profile.offpeak_max_kw[2] == pytest.approx(300.0)
    assert profile.monthly_peak_kw[2] == pytest.approx(10.0)
    # Every other month sees only the flat 10 kW overnight.
    assert profile.offpeak_max_kw[0] == pytest.approx(10.0)


def test_representative_is_the_median_by_peak_intensity_not_by_size():
    """Median floor area picks a typical-sized building that can be an
    intensity outlier. Worcester's SmallOffice pick sat at 12.3 W/sqft against
    a cohort median of 3.9 — a 3x magnitude inflation on 231 parcels."""
    index = pd.DataFrame({
        "bldg_id": [1, 2, 3],
        "building_type": ["SmallOffice"] * 3,
        "sqft": [1_000.0, 2_000.0, 3_000.0],
    })
    # Building 2 is the median by SIZE but the extreme by INTENSITY.
    intensities = {1: 3.0, 2: 12.0, 3: 5.0}

    def fake_read(bldg_id, conn=None, sqft=None):
        peak = intensities[bldg_id] * sqft / 1000.0  # W/sqft -> kW
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, peak),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    rep = comstock.select_representative(
        index, "SmallOffice", min_cohort=1, read_profile=fake_read
    )

    assert rep.bldg_id == 3, "median intensity is 5.0 W/sqft, which is building 3"
    assert rep.peak_intensity_w_per_sqft == pytest.approx(5.0)


def test_representative_sampling_spans_the_size_range():
    """A sample drawn off one end of the size range is not a cohort median."""
    n = 100
    index = pd.DataFrame({
        "bldg_id": list(range(n)),
        "building_type": ["Warehouse"] * n,
        "sqft": [1_000.0 * (i + 1) for i in range(n)],
    })
    seen: list[int] = []

    def fake_read(bldg_id, conn=None, sqft=None):
        seen.append(bldg_id)
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, 1.0),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    comstock.select_representative(
        index, "Warehouse", min_cohort=1, sample_size=5, read_profile=fake_read
    )

    assert len(seen) == 5
    assert min(seen) < n // 4, "sample must reach the small end"
    assert max(seen) > 3 * n // 4, "sample must reach the large end"


def test_representative_sample_larger_than_cohort_reads_every_building():
    index = pd.DataFrame({
        "bldg_id": [7, 8],
        "building_type": ["Hospital"] * 2,
        "sqft": [100_000.0, 200_000.0],
    })
    seen: list[int] = []

    def fake_read(bldg_id, conn=None, sqft=None):
        seen.append(bldg_id)
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, 2.0),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    rep = comstock.select_representative(
        index, "Hospital", min_cohort=30, sample_size=15, read_profile=fake_read
    )

    assert sorted(seen) == [7, 8]
    assert rep.widened is True, "a 2-building cohort is still thin"
    assert rep.cohort_size == 2


def test_comstock_archetype_still_satisfies_the_protocol():
    profile = comstock.ReducedProfile(
        bldg_id=1,
        monthly_peak_kw=np.full(12, 50.0),
        windows=np.full((12, comstock.INTERVALS_PER_BILLED_DAY), 40.0),
        sqft=10_000.0,
        offpeak_max_kw=np.full(12, 12.0),
    )
    arch = comstock.ComStockArchetype(profile=profile, sqft=20_000.0)

    assert isinstance(arch, Archetype)
    assert arch.offpeak_max(1) == pytest.approx(24.0), "scales with the parcel"
    with pytest.raises(ValueError):
        arch.offpeak_max(13)


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


# ---------------------------------------------------------------------------
# a county without the type
# ---------------------------------------------------------------------------

from dataclasses import replace as _replace


class _Conn:
    def close(self):
        pass


def _offline(monkeypatch, index_rows):
    calls = []

    def fake_index(county, conn=None):
        calls.append(county)
        return pd.DataFrame(index_rows(county), columns=["bldg_id", "building_type", "sqft"])

    base = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))

    def fake_reduce(bldg_id, conn=None, sqft=None):
        return _replace(base, bldg_id=int(bldg_id), sqft=sqft)

    monkeypatch.setattr(comstock, "load_county_index", fake_index)
    monkeypatch.setattr(comstock, "reduce_timeseries", fake_reduce)
    monkeypatch.setattr(comstock, "connect", lambda: _Conn())
    return calls


def test_a_county_without_the_type_pools_every_massachusetts_county(tmp_path, monkeypatch):
    """Neither Bristol nor Middlesex County has a ComStock hospital."""
    def rows(county):
        out = [{"bldg_id": 1, "building_type": "Warehouse", "sqft": 10_000.0}]
        if county == "G2500090":  # Essex
            out += [{"bldg_id": 100 + i, "building_type": "Hospital", "sqft": 200_000.0 + i}
                    for i in range(5)]
        return out

    calls = _offline(monkeypatch, rows)

    a = comstock.build_archetype("hospital", 50_000.0, county_gisjoin="G2500050", cache_dir=tmp_path)

    assert calls[0] == "G2500050"
    assert set(calls[1:]) == set(comstock.MA_COUNTY_GISJOINS)
    assert a.profile.bldg_id in {100, 101, 102, 103, 104}
    assert a.widened is True and a.cohort_size == 5


def test_a_county_with_the_type_is_not_pooled(tmp_path, monkeypatch):
    calls = _offline(monkeypatch, lambda county: [
        {"bldg_id": 7, "building_type": "Warehouse", "sqft": 10_000.0}])

    comstock.build_archetype("warehouse", 50_000.0, county_gisjoin="G2500170", cache_dir=tmp_path)

    assert calls == ["G2500170"]


def test_every_massachusetts_county_is_in_the_pool():
    assert len(comstock.MA_COUNTY_GISJOINS) == 14
    assert comstock.MA_COUNTY_GISJOINS[0] == "G2500010"
    assert comstock.WORCESTER_COUNTY_GISJOIN in comstock.MA_COUNTY_GISJOINS
