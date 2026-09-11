"""What the page reads, adapted from the one export contract."""

import json
from pathlib import Path

import pandas as pd
import pytest

from shave import site_data

WORCESTER_DIR = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
needs_worcester = pytest.mark.skipif(
    not Path(WORCESTER_DIR + "/M348TaxPar_CY26_FY26.shp").exists(),
    reason="Worcester L3 extract not present (data/raw is gitignored)",
)


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


@needs_worcester
def test_every_field_the_page_reads_is_present_on_every_row():
    """The consumer contract. A rename in the pipeline or the export must
    break the build, not the browser."""
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    raw = export.build_export(scored, parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, scored)

    for name, rows in enriched["lists"].items():
        assert rows, f"the {name} list is empty"
        for row in rows:
            missing = set(site_data.REQUIRED_ROW_FIELDS) - set(row)
            assert not missing, f"{name} row {row['loc_id']} missing {sorted(missing)}"


@needs_worcester
def test_the_payload_is_json_serialisable_and_small_enough_to_serve():
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    blob = json.dumps(enriched, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < export.MAX_BYTES


@needs_worcester
def test_the_top_row_of_each_list_carries_a_named_occupant_and_its_reason():
    """Success criterion 2, at the point the page reads it, on BOTH lists --
    because the lists are never merged, each one's head is a first row that
    someone will read first."""
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    for name, rows in enriched["lists"].items():
        top = rows[0]
        assert top["rank"] == 1
        assert top["reason"].endswith("."), name
        assert top["occupant"], f"the top {name} row must name a real business"
        assert top["occupant_source"].startswith("http"), name


@needs_worcester
def test_each_list_is_ranked_by_dollars_within_itself():
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    for rows in enriched["lists"].values():
        usd = [r["annual_savings_usd"] for r in rows]
        assert usd == sorted(usd, reverse=True)
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
