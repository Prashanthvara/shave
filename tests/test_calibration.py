"""The MECOLS class-shape check, on synthetic data only.

Nothing here reads the real workbook or real Worcester parcels. The criterion
and the arithmetic are committed before the first real run, which is the
point of declaring a pass criterion in advance.
"""

import calendar
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from shave import assumptions, calibration
from shave.archetype import INTERVALS_PER_BILLED_DAY
from shave.billing_window import billed_days

HOURS = [f"HR_{h}_KW_AVG" for h in range(1, 25)]


def _synthetic_mecols(tmp_path, year=2025):
    """G-2 at a flat 10 kW, with three spikes per month:
    - 30 kW at hour-start 14 on the first billed day  (the billed peak)
    - 50 kW at hour-start 14 on the first Saturday      (not billed)
    - 60 kW at hour-start 3 on the first billed day     (outside the window)
    """
    rows = []
    for m in range(1, 13):
        first_billed = billed_days(year, m)[0]
        first_saturday = next(
            date(year, m, d) for d in range(1, 8) if date(year, m, d).weekday() == 5
        )
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            day = date(year, m, d)
            kw = [10.0] * 24
            if day == first_billed:
                kw[14] = 30.0   # HR_15 is hour-start 14
                kw[3] = 60.0    # HR_4 is hour-start 3
            if day == first_saturday:
                kw[14] = 50.0
            rows.append({"Rate": "G-2", "Date": pd.Timestamp(day), **dict(zip(HOURS, kw))})
    path = tmp_path / "MECOLS.xlsx"
    pd.DataFrame(rows).to_excel(path, sheet_name=calibration.MECOLS_SHEET, index=False)
    return path


def test_the_criterion_is_published_with_the_assumptions():
    keys = {a.key for a in assumptions.PUBLISHED}
    assert "mecols_pass_criterion" in keys
    assert assumptions.MECOLS_MONTHS_REQUIRED == 9
    assert assumptions.MECOLS_HOUR_TOLERANCE_H == 1
    assert assumptions.MECOLS_LOAD_FACTOR_TOLERANCE == 0.15


def test_the_billed_peak_ignores_weekends_and_hours_outside_the_window(tmp_path):
    frame = calibration.load_mecols(_synthetic_mecols(tmp_path))

    shape = calibration.mecols_monthly(frame, "G-2", 2025)

    assert list(shape.peak_hour) == [14] * 12, "not the Saturday, not 03:00"
    np.testing.assert_allclose(shape.peak_kw, 30.0)


def test_energy_counts_every_hour_and_load_factor_uses_the_billed_peak(tmp_path):
    frame = calibration.load_mecols(_synthetic_mecols(tmp_path))

    shape = calibration.mecols_monthly(frame, "G-2", 2025)

    jan_hours = 31 * 24
    jan_energy = jan_hours * 10.0 + (30 - 10) + (60 - 10) + (50 - 10)
    assert shape.hours[0] == jan_hours
    assert shape.energy_kwh[0] == pytest.approx(jan_energy)
    assert shape.load_factor[0] == pytest.approx(jan_energy / (jan_hours * 30.0))


class _Stub:
    """A ComStock-like archetype: flat `level`, tripled at hour-start 14."""

    def __init__(self, level: float):
        self.level = level

    def peak_day_window(self, month):
        w = np.full(INTERVALS_PER_BILLED_DAY, self.level)
        w[24:28] = self.level * 3.0  # intervals 24-27 are 14:00-14:45
        return w

    def monthly_energy_kwh(self):
        return np.full(12, 1000.0 * self.level)


def test_the_aggregate_sums_comstock_kept_rows_by_rate_as_hourly_averages():
    scored = pd.DataFrame([
        {"source": "comstock", "keep": True, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
        {"source": "comstock", "keep": True, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
        {"source": "modeled", "keep": True, "rate_class": "G-2", "archetype": "university", "sqft": 1.0},
        {"source": "comstock", "keep": False, "rate_class": "G-2", "archetype": "warehouse", "sqft": 1.0},
    ])

    out = calibration.bottom_up_monthly(scored, archetype_factory=lambda row: _Stub(10.0))

    assert set(out) == {"G-2"}, "no G-3 rows, so no G-3 shape"
    g2 = out["G-2"]
    np.testing.assert_allclose(g2.peak_kw, 60.0)           # two parcels x 30 kW
    assert list(g2.peak_hour) == [14] * 12
    np.testing.assert_allclose(g2.energy_kwh, 20_000.0)     # modeled and dropped rows excluded
    assert g2.hours[0] == 31 * 24 and g2.hours[1] == 28 * 24  # 2018


def test_an_aggregate_with_missing_energy_refuses_rather_than_reporting():
    class NoEnergy(_Stub):
        def monthly_energy_kwh(self):
            return np.full(12, np.nan)

    scored = pd.DataFrame([{"source": "comstock", "keep": True, "rate_class": "G-3",
                            "archetype": "hospital", "sqft": 1.0}])
    with pytest.raises(ValueError, match="refresh_comstock_energy"):
        calibration.bottom_up_monthly(scored, archetype_factory=lambda row: NoEnergy(1.0))


def _shape(peak_hour, load_factor):
    hours = np.full(12, 720.0)
    peak = np.full(12, 100.0)
    return calibration.MonthlyShape(
        peak_kw=peak, peak_hour=np.asarray(peak_hour), energy_kwh=np.asarray(load_factor) * hours * peak,
        hours=hours,
    )


def test_compare_applies_the_declared_thresholds():
    ours = _shape([14] * 12, [0.50] * 12)
    close = _shape([15] * 9 + [17] * 3, [0.44] * 12)   # 9 hour matches; LF within 13.6%
    far = _shape([15] * 8 + [17] * 4, [0.40] * 12)     # 8 hour matches; LF off by 25%

    good = calibration.compare(ours, close)
    bad = calibration.compare(ours, far)

    assert (good["months_hour_ok"], good["months_load_factor_ok"], good["passes"]) == (9, 12, True)
    assert (bad["months_hour_ok"], bad["months_load_factor_ok"], bad["passes"]) == (8, 0, False)
    assert max(good["peak_shape_ours"]) == 1.0 and max(good["peak_shape_mecols"]) == 1.0
    json.dumps(good)


def test_run_without_the_workbook_reports_unrun_not_failed(tmp_path):
    out = calibration.run(pd.DataFrame(), mecols_path=tmp_path / "absent.xlsx")
    assert "status" in out
    assert "not failed" in out["status"]


def test_the_real_check_reports_both_rates_over_twelve_months(worcester_scored, mecols_path):
    """Structure only. The verdict is published, never asserted: a test that
    required a pass would be a threshold tuned after the fact."""
    out = calibration.run(worcester_scored, mecols_path=mecols_path)

    assert out["year"] == 2025
    assert set(out["by_rate"]) == {"G-2", "G-3"}
    assert out["by_rate"]["G-2"]["n_parcels"] == 380
    assert out["by_rate"]["G-3"]["n_parcels"] == 148
    for rate in ("G-2", "G-3"):
        r = out["by_rate"][rate]
        assert len(r["peak_hour_ours"]) == len(r["load_factor_mecols"]) == 12
        assert isinstance(r["passes"], bool)
    json.dumps(out)
