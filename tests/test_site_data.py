"""What the page reads, adapted from the one export contract."""

import json

import pandas as pd
import pytest

from shave import site_data
from shave.archetype import INTERVALS_PER_BILLED_DAY, STEP_HOURS
from shave.assumptions import PEAK_HOUR_END, PEAK_HOUR_START


def _scored_stub(loc_id="L1"):
    return pd.DataFrame([{
        "loc_id": loc_id, "keep": True, "sweet_spot": False,
        "unscored_reason": None, "annual_savings_usd": 1.0,
    }])


def test_window_series_normalises_to_the_years_own_peak():
    """The page scales a 0-1 series to pixels and does no other arithmetic."""
    row = {"monthly_billed_demand_kw": [50.0, 100.0, 200.0] + [100.0] * 9}
    series = site_data.window_series(row)

    assert len(series) == 12
    assert max(series) == 1.0
    assert series[0] == pytest.approx(0.25)


def test_window_series_survives_a_month_with_no_billed_demand():
    """A month with no billed days bills nothing. That must not divide by zero."""
    assert site_data.window_series({"monthly_billed_demand_kw": [0.0] * 12}) == [0.0] * 12


def test_enrich_keeps_the_two_lists_separate_and_adds_what_the_page_needs():
    """The spec forbids merging the lists. enrich must not flatten them."""
    payload = {
        "schema_version": "1.1.0",
        "counts": {"kept": 2},
        "lists": {
            "comstock": [{
                "loc_id": "L1", "rank": 1, "annual_savings_usd": 9000.0,
                "monthly_billed_demand_kw": [100.0] * 12,
                "monthly_shaveable_kw": [30.0] * 12, "reason": "Because.",
            }],
            "modeled": [{
                "loc_id": "L2", "rank": 1, "annual_savings_usd": 12000.0,
                "monthly_billed_demand_kw": [80.0] * 12,
                "monthly_shaveable_kw": [25.0] * 12, "reason": "Because.",
            }],
        },
    }

    out = site_data.enrich(payload, _scored_stub())

    assert set(out["lists"]) == {"comstock", "modeled"}
    assert [r["loc_id"] for r in out["lists"]["comstock"]] == ["L1"]
    assert [r["loc_id"] for r in out["lists"]["modeled"]] == ["L2"]
    assert out["lists"]["comstock"][0]["rank"] == 1
    assert out["lists"]["modeled"][0]["rank"] == 1, "ranks restart per list"
    for row in out["lists"]["comstock"] + out["lists"]["modeled"]:
        assert len(row["window_kw"]) == 12
        assert "occupant" in row and "occupant_source" in row
        assert row["shaveable_kw"] > 0
    assert "method" in out
    assert out["site_schema_version"] == site_data.SITE_SCHEMA_VERSION


def test_enrich_carries_the_regression_the_export_already_ran():
    """The export runs the regression and puts it in the payload. Dropping it
    here would make the method page say "not yet run" while the numbers sit in
    the object it was just handed."""
    payload = {
        "schema_version": "1.1.0", "counts": {},
        "regression": {"ceiling": 0.9, "by_source": {
            "comstock": {"n": 528, "r2_size_and_rate": 0.614,
                         "r2_with_archetype": 0.878, "archetype_adds_little": False}}},
        "lists": {"comstock": [{"loc_id": "L1", "rank": 1,
                                "monthly_billed_demand_kw": [1.0] * 12,
                                "monthly_shaveable_kw": [1.0] * 12}], "modeled": []},
    }

    out = site_data.enrich(payload, _scored_stub())

    assert "status" not in out["method"]["regression"], "it HAS run"
    assert out["method"]["regression"]["by_source"]["comstock"]["r2_size_and_rate"] == 0.614


def test_enrich_does_not_mutate_the_export_it_was_given():
    payload = {"schema_version": "1.1.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}
    before = json.dumps(payload, sort_keys=True)

    site_data.enrich(payload, _scored_stub())

    assert json.dumps(payload, sort_keys=True) == before


def test_every_field_the_page_reads_is_present_on_every_row(
    worcester_parcels, worcester_scored
):
    """The consumer contract. A rename in the pipeline or the export must
    break the build, not the browser."""
    from shave import export

    raw = export.build_export(worcester_scored, worcester_parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, worcester_scored)

    for name, rows in enriched["lists"].items():
        assert rows, f"the {name} list is empty"
        for row in rows:
            missing = set(site_data.REQUIRED_ROW_FIELDS) - set(row)
            assert not missing, f"{name} row {row['loc_id']} missing {sorted(missing)}"


def test_the_payload_is_json_serialisable_and_small_enough_to_serve(
    worcester_parcels, worcester_scored
):
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    blob = json.dumps(enriched, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < export.MAX_BYTES


def test_the_top_row_of_each_list_carries_a_named_occupant_and_its_reason(
    worcester_parcels, worcester_scored
):
    """Success criterion 2, at the point the page reads it, on BOTH lists --
    because the lists are never merged, each one's head is a first row that
    someone will read first."""
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for name, rows in enriched["lists"].items():
        top = rows[0]
        assert top["rank"] == 1
        assert top["reason"].endswith("."), name
        assert top["occupant"], f"the top {name} row must name a real business"
        assert top["occupant_source"].startswith("http"), name


def test_each_list_is_ranked_by_dollars_within_itself(
    worcester_parcels, worcester_scored
):
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for rows in enriched["lists"].values():
        usd = [r["annual_savings_usd"] for r in rows]
        assert usd == sorted(usd, reverse=True)
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))


def test_every_exported_row_carries_a_map_path(worcester_parcels, worcester_scored):
    """One Worcester parcel has no geometry and must still be exported, with
    an empty path rather than a missing key."""
    from shave import export, mapgeo

    frame = mapgeo.frame_for(worcester_parcels)
    raw = export.build_export(worcester_scored, worcester_parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, worcester_scored,
                                paths=mapgeo.paths_for(worcester_parcels, frame),
                                view_box=frame.view_box)

    assert enriched["map"]["view_box"].startswith("0 0 620 ")
    drawn = 0
    for rows in enriched["lists"].values():
        for row in rows:
            assert "path" in row, f"{row['loc_id']} has no path key"
            if row["path"]:
                assert row["path"].startswith("M") and row["path"].endswith("Z")
                drawn += 1
    assert drawn > 0, "nothing would be drawn"


def test_day_profile_puts_load_held_level_and_overnight_on_one_scale():
    """The page draws all three on one axis and does no arithmetic, so they
    must arrive already sharing a scale."""
    row = {"peak_day_kw": [100.0, 400.0, 200.0], "peak_day_held_kw": 150.0,
           "offpeak_max_kw": 80.0}

    out = site_data.day_profile(row)

    assert out["day_kw"] == [0.25, 1.0, 0.5]
    assert out["day_held"] == pytest.approx(0.375)
    assert out["day_offpeak"] == pytest.approx(0.2)


def test_an_overnight_load_above_the_billed_peak_sets_the_scale():
    """A 3 a.m. process is free under this tariff, so overnight load can exceed
    the billed peak. It must not be drawn off the top of the chart."""
    out = site_data.day_profile(
        {"peak_day_kw": [50.0, 100.0], "peak_day_held_kw": 60.0, "offpeak_max_kw": 200.0}
    )

    assert out["day_offpeak"] == 1.0
    assert max(out["day_kw"]) == 0.5


def test_a_row_with_no_day_yields_an_empty_series_not_a_crash():
    assert site_data.day_profile({"offpeak_max_kw": 0.0}) == {
        "day_kw": [], "day_held": 0.0, "day_offpeak": 0.0,
    }


def test_the_payload_carries_the_tariff_axis_so_the_page_restates_nothing():
    payload = {"schema_version": "1.4.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub())

    assert out["day_axis"] == {
        "window_start_hour": PEAK_HOUR_START,
        "window_end_hour": PEAK_HOUR_END,
        "step_hours": STEP_HOURS,
    }


def test_every_exported_row_carries_its_worst_billed_day(
    worcester_parcels, worcester_scored
):
    """The day's own peak IS that month's billed demand. If `worst` were off by
    one month, this is the assertion that would say so."""
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for name, rows in enriched["lists"].items():
        for row in rows:
            m = row["peak_day_month"]
            assert 1 <= m <= 12, f"{name} {row['loc_id']} month {m}"
            assert len(row["day_kw"]) == INTERVALS_PER_BILLED_DAY
            assert max(row["peak_day_kw"]) == pytest.approx(
                row["monthly_billed_demand_kw"][m - 1], abs=0.1
            ), f"{name} {row['loc_id']}"
            assert 0.0 <= row["day_held"] <= max(row["day_kw"]) + 1e-3
            assert max(row["day_kw"] + [row["day_offpeak"]]) == pytest.approx(1.0)


def test_compass_labels_a_bearing_with_eight_points():
    assert site_data.compass(0) == "N"
    assert site_data.compass(228) == "SW"
    assert site_data.compass(100) == "E"
    assert site_data.compass(338) == "N"
    assert site_data.compass(None) == ""


def test_the_payload_carries_the_siting_rule_and_each_row_its_wall():
    from shave.assumptions import MIN_WALL_CLEARANCE_FT, MIN_WALL_RUN_FT

    payload = {"schema_version": "1.5.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12, "wall_bearing_deg": 228}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub(), walls={"L1": "M1,2L3,4"})

    row = out["lists"]["comstock"][0]
    assert row["wall"] == "M1,2L3,4"
    assert row["wall_facing"] == "SW"
    assert out["siting_rule"] == {
        "clearance_ft": MIN_WALL_CLEARANCE_FT, "min_wall_run_ft": MIN_WALL_RUN_FT,
    }


def test_every_exported_row_carries_its_siting_result(worcester_parcels, worcester_scored):
    from shave import export, mapgeo, siting

    frame = mapgeo.frame_for(worcester_parcels)
    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored, walls=mapgeo.walls_for(worcester_parcels, frame))

    rows = {r["loc_id"]: r for l in enriched["lists"].values() for r in l}
    for row in rows.values():
        assert row["siting"] in siting.SITING_STATUSES, row["loc_id"]
        if row["wall_run_ft"]:
            assert row["wall"].startswith("M"), row["loc_id"]
    walmart = rows["F_577265_2910122"]
    assert walmart["siting"] == "clear"
    assert walmart["wall_bearing_deg"] == 228
    assert walmart["wall_facing"] == "SW"
    screened = [r for r in rows.values() if r["siting"] == "screened_out"]
    assert 1 <= len(screened) <= 20


def test_enrich_carries_the_calibration_the_build_ran():
    payload = {"schema_version": "1.5.0", "counts": {},
               "calibration": {"year": 2025, "by_rate": {"G-2": {"passes": False}}},
               "lists": {"comstock": [{"loc_id": "L1", "rank": 1,
                                       "monthly_billed_demand_kw": [1.0] * 12,
                                       "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub())

    assert out["method"]["calibration"]["by_rate"]["G-2"]["passes"] is False
