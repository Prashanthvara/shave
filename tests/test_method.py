"""The method page, assembled from the code that ran."""

import json

import pandas as pd
import pytest

from shave import method


def test_every_limitation_the_spec_names_is_present():
    """Success criterion 6, verbatim: 'The method page states what the tool
    cannot do: no measurement, no interconnection feasibility, no per-feeder
    constraints, no underwriting, multi-tenant buildings overstated,
    industrial shapes modeled not measured.'"""
    required = {
        "no_measurement",
        "no_interconnection",
        "no_feeder_constraints",
        "no_underwriting",
        "multi_tenant_overstated",
        "industrial_modeled_not_measured",
    }
    present = {limitation.key for limitation in method.LIMITATIONS}
    assert required <= present, f"missing: {sorted(required - present)}"


def test_every_limitation_has_a_real_sentence():
    for limitation in method.LIMITATIONS:
        assert limitation.statement.endswith("."), limitation.key
        assert len(limitation.statement) > 40, (
            f"{limitation.key} is a label, not a statement"
        )


def test_limitation_keys_are_unique():
    keys = [limitation.key for limitation in method.LIMITATIONS + method.KNOWN_GAPS]
    assert len(keys) == len(set(keys))


def test_every_pipeline_flag_is_explained():
    """A flag on a published row with no explanation is a warning the reader
    cannot act on."""
    from shave import pipeline

    for reason in pipeline.UNSCORED_REASONS:
        assert reason in method.FLAG_MEANINGS, f"unscored reason {reason} unexplained"
    for flag in (
        "power_limited",
        "scale_extrapolation",
        "recharge_constrained",
        "thin_cohort",
    ):
        assert flag in method.FLAG_MEANINGS, f"row flag {flag} unexplained"


def _fake_scored() -> pd.DataFrame:
    return pd.DataFrame([
        {"loc_id": "A", "keep": True, "sweet_spot": True,
         "annual_savings_usd": 100.0, "unscored_reason": None, "assess_fy": 2026},
        {"loc_id": "B", "keep": True, "sweet_spot": False,
         "annual_savings_usd": 50.0, "unscored_reason": None, "assess_fy": 2026},
        {"loc_id": "C", "keep": False, "sweet_spot": False,
         "annual_savings_usd": 0.0, "unscored_reason": "no_floor_area",
         "assess_fy": 2026},
    ])


def test_payload_counts_match_the_frame():
    payload = method.method_payload(_fake_scored())
    assert payload["coverage"]["parcels_total"] == 3
    assert payload["coverage"]["kept"] == 2
    assert payload["coverage"]["sweet_spot"] == 1
    assert payload["coverage"]["unscored"] == {"no_floor_area": 1}


def test_payload_carries_every_published_assumption():
    from shave.assumptions import PUBLISHED

    payload = method.method_payload(_fake_scored())
    assert len(payload["assumptions"]) == len(PUBLISHED)
    for row in payload["assumptions"]:
        assert row["source"], f"{row['key']} has no source"
        assert row["provenance"] in ("FILED", "ASSUMED", "DERIVED")


def test_an_unrun_regression_says_so_rather_than_reporting_zero():
    payload = method.method_payload(_fake_scored())
    assert "not yet run" in payload["regression"]["status"]


def test_a_supplied_regression_is_passed_through():
    """The real shape is {ceiling, by_source}, one entry per ranked list --
    not a flat pair of figures. A test that models a shape the code never
    produces teaches the next reader the wrong thing."""
    report = {"ceiling": 0.9, "by_source": {
        "comstock": {"n": 528, "r2_size_and_rate": 0.614,
                     "r2_with_archetype": 0.878, "archetype_adds_little": False}}}
    payload = method.method_payload(_fake_scored(), regression=report)
    assert payload["regression"]["by_source"]["comstock"]["r2_size_and_rate"] == 0.614


def test_the_payload_is_json_serialisable():
    """It is going into a static file. A numpy scalar in here fails at deploy
    time, which is the worst time to find it."""
    json.dumps(method.method_payload(_fake_scored()))


def test_the_recharge_flag_explanation_says_it_cannot_currently_fire():
    """The flag is kept as a guard on the assumptions, not as a per-site
    finding. A reader who never sees it should know why."""
    text = method.FLAG_MEANINGS["recharge_constrained"]
    assert "cannot currently occur" in text


def test_the_unbilled_overnight_limitation_is_stated():
    """The finding that removed the headroom predicate has to reach the page,
    or the tool silently answers a question it never explains."""
    stated = {limitation.key: limitation.statement for limitation in method.LIMITATIONS}
    text = stated["recharge_is_unconstrained_service_capacity_is_not_checked"]
    assert "never billed" in text
    assert "service capacity" in text


def test_the_method_page_says_what_the_map_cannot_show():
    """The map draws parcel outlines. A reader will reasonably assume a shape
    on a map means a site was assessed for fit; nothing here checks that."""
    stated = {g.key: g.statement for g in method.KNOWN_GAPS}
    assert "map_shows_no_siting" in stated, sorted(stated)
    assert "no_siting_screen" not in stated, "the two would say overlapping things"
    text = stated["map_shows_no_siting"].lower()
    assert "wall" in text
    assert "outline" in text


def test_the_method_page_says_the_day_chart_is_one_day_and_blind_overnight():
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "day_chart_is_one_day" in stated, sorted(stated)
    text = stated["day_chart_is_one_day"].lower()
    assert "overnight" in text
    assert "not billed" in text
