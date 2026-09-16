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


def test_the_method_page_says_what_the_siting_screen_cannot_see():
    """The spec: 'State on the method page what this cannot see.' The gap that
    said no screen had been run is retired now that one has."""
    gaps = {g.key for g in method.KNOWN_GAPS}
    assert "map_shows_no_siting" not in gaps
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "siting_screens_out_only" in stated, sorted(stated)
    text = stated["siting_screens_out_only"].lower()
    for blind_spot in ("loading dock", "fire lane", "egress", "setback", "service entrance"):
        assert blind_spot in text, blind_spot
    assert "not a green light" in text or "does not confirm" in text


def test_the_method_page_says_the_day_chart_is_one_day_and_blind_overnight():
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "day_chart_is_one_day" in stated, sorted(stated)
    text = stated["day_chart_is_one_day"].lower()
    assert "overnight" in text
    assert "not billed" in text


def test_the_method_page_says_what_the_address_box_searches():
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "address_box_is_the_screen_only" in stated, sorted(stated)
    text = stated["address_box_is_the_screen_only"].lower()
    assert "residential" in text
    assert "not screened" in text


def test_the_class_shape_check_is_a_stated_limitation_not_a_gap():
    gaps = {g.key for g in method.KNOWN_GAPS}
    assert "no_class_shape_check" not in gaps
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "class_shape_check_is_modest" in stated, sorted(stated)
    text = stated["class_shape_check_is_modest"].lower()
    for words in ("not validation", "2018", "modelled"):
        assert words in text, words


def test_the_method_payload_carries_the_calibration_it_was_given():
    payload = method.method_payload(_fake_scored(), calibration={"year": 2025, "by_rate": {}})
    assert payload["calibration"] == {"year": 2025, "by_rate": {}}
    assert "status" in method.method_payload(_fake_scored())["calibration"]


def test_the_method_page_states_the_town_swap_and_why():
    assert "one_municipality" not in {g.key for g in method.KNOWN_GAPS}
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    text = stated["three_towns_not_the_design_docs_three"]
    for words in ("Fall River", "Lowell", "New Bedford", "Chicopee", "Eversource", "municipal light plant"):
        assert words in text, words


def test_the_method_payload_carries_the_towns_it_was_given():
    towns = [{"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026, "counts": {}}]
    assert method.method_payload(_fake_scored(), towns=towns)["towns"] == towns
    assert method.method_payload(_fake_scored())["towns"] == []


def test_the_method_page_describes_the_occupant_pipeline_without_overclaiming(
    worcester_scored,
):
    """The agent drafts and a person verifies. A reader who cannot see that
    split cannot judge what the occupant column is worth. It must also not
    claim any row has been through the agent until one has."""
    payload = method.method_payload(worcester_scored)
    text = " ".join(
        item["statement"]
        for key in ("limitations", "known_gaps")
        for item in payload[key]
    )
    assert "drafted by an agent" in text
    assert "initialled" in text or "initials" in text
    # The published figure is the real one, never the mechanism's promise.
    assert "published only after" not in text


def test_the_method_page_says_the_reason_sentence_is_templated(worcester_scored):
    payload = method.method_payload(worcester_scored)
    text = " ".join(
        item["statement"]
        for key in ("limitations", "known_gaps")
        for item in payload[key]
    )
    assert "templated" in text
