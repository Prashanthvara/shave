import pytest

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


def test_selects_the_median_sqft_building_of_the_cohort():
    idx = _index([(i, "Warehouse", float(sqft))
                  for i, sqft in enumerate(range(1000, 1000 + 31 * 100, 100))])
    rep = comstock.select_representative(idx, "Warehouse")
    assert rep.cohort_size == 31
    assert rep.widened is False
    assert rep.sqft == 2500.0  # the 16th of 31, the exact median


def test_median_of_an_even_cohort_takes_the_lower_of_the_two_middles():
    # Deterministic tie-break: never interpolate, always name a real building.
    idx = _index([(i, "Warehouse", float(s)) for i, s in enumerate([10, 20, 30, 40] * 8)])
    rep = comstock.select_representative(idx, "Warehouse", min_cohort=4)
    assert rep.sqft == 20.0
    assert rep.bldg_id in set(idx["bldg_id"])


def test_small_cohort_widens_and_says_so():
    idx = _index([(1, "Hospital", 300000.0), (2, "Hospital", 375000.0)])
    rep = comstock.select_representative(idx, "Hospital", min_cohort=30)
    assert rep.widened is True
    assert rep.cohort_size == 2


def test_unknown_building_type_raises():
    idx = _index([(1, "Warehouse", 10000.0)])
    with pytest.raises(comstock.ComStockError, match="no ComStock buildings"):
        comstock.select_representative(idx, "Hospital")


def test_selection_is_deterministic():
    idx = _index([(i, "Warehouse", float(s))
                  for i, s in enumerate([500, 900, 700, 1100, 300] * 8)])
    picks = {comstock.select_representative(idx, "Warehouse", min_cohort=5).bldg_id
             for _ in range(10)}
    assert len(picks) == 1
