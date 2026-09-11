"""The versioned contract between the Python half and whatever renders it."""

import json

import pandas as pd
import pytest

from shave import export


def _row(loc_id="L1", usd=10_000.0, source="comstock", **over):
    base = dict(
        loc_id=loc_id, archetype="warehouse", source=source, sqft=20_000.0,
        monthly_billed_demand_kw=[180.0] * 12, monthly_shaveable_kw=[60.0] * 12,
        avg_12mo_kw=180.0, peak_kw=250.0, peak_to_avg=1.39, rate_class="G-2",
        demand_charge_per_kw=15.06, annual_savings_usd=usd, shaved_fraction=0.33,
        sweet_spot=False, keep=True, band_reason=None, recharge_feasible=True,
        offpeak_max_kw=40.0, months_at_power_cap=0, flags=[], unscored_reason=None,
    )
    base.update(over)
    return base


def _parcels(loc_ids):
    return pd.DataFrame([
        {"loc_id": i, "prop_id": f"P{i}", "site_addr": f"{n} MAIN ST",
         "city": "WORCESTER", "zip": "01610", "owner": f"OWNER {n}",
         "use_code": "4000", "use_desc": "Manufacturing", "icp_sector": "3",
         "assess_fy": 2026, "confidence": "HIGH", "confidence_reasons": (),
         "lon": -71.8 - n / 1000, "lat": 42.26 + n / 1000}
        for n, i in enumerate(loc_ids)
    ])


def test_the_export_carries_a_schema_version_and_two_separate_lists():
    """The spec forbids merging modelled and measured rows into one ranking:
    the industrial magnitude chain is two steps deeper than ComStock's."""
    scored = pd.DataFrame([_row("L1", 9_000.0), _row("L2", 12_000.0, source="modeled")])

    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert payload["schema_version"] == export.SCHEMA_VERSION
    assert set(payload["lists"]) == {"comstock", "modeled"}
    assert [r["loc_id"] for r in payload["lists"]["comstock"]] == ["L1"]
    assert [r["loc_id"] for r in payload["lists"]["modeled"]] == ["L2"]
    assert payload["lists"]["comstock"][0]["rank"] == 1
    assert payload["lists"]["modeled"][0]["rank"] == 1, "ranks restart per list"


def test_unscored_rows_never_reach_a_ranked_list():
    scored = pd.DataFrame([
        _row("L1", 9_000.0),
        _row("L2", 0.0, keep=False, unscored_reason="no_intensity_anchor"),
    ])

    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert [r["loc_id"] for r in payload["lists"]["comstock"]] == ["L1"]
    assert payload["counts"]["unscored"] == {"no_intensity_anchor": 1}


def test_rows_are_ranked_by_dollars_descending():
    scored = pd.DataFrame([_row("L1", 5_000.0), _row("L2", 20_000.0), _row("L3", 9_000.0)])

    payload = export.build_export(scored, _parcels(["L1", "L2", "L3"]),
                                  town={"name": "Worcester", "town_id": 348})

    usd = [r["annual_savings_usd"] for r in payload["lists"]["comstock"]]
    assert usd == sorted(usd, reverse=True)
    assert [r["rank"] for r in payload["lists"]["comstock"]] == [1, 2, 3]


def test_every_row_carries_a_checkable_reason():
    scored = pd.DataFrame([_row("L1", 14_321.0)])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})
    reason = payload["lists"]["comstock"][0]["reason"]

    assert "G-2" in reason
    assert "$15.06/kW" in reason
    assert "14,321" in reason
    assert "measured" in reason


def test_a_modeled_row_says_it_is_modelled():
    scored = pd.DataFrame([_row("L1", 8_000.0, source="modeled")])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert "modelled, not measured" in payload["lists"]["modeled"][0]["reason"]


def test_the_assumptions_travel_with_the_payload():
    """P6: published assumptions must be provably the computed ones."""
    scored = pd.DataFrame([_row("L1")])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})
    keys = {a["key"] for a in payload["assumptions"]}

    assert {"g2_demand_charge", "g3_demand_charge", "g3_threshold"} <= keys


def test_the_payload_is_json_serialisable_and_round_trips(tmp_path):
    scored = pd.DataFrame([_row("L1"), _row("L2", source="modeled")])
    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    path = export.write_export(payload, tmp_path / "ranked.json")
    back = json.loads(path.read_text())

    assert back["schema_version"] == export.SCHEMA_VERSION
    assert back["lists"]["comstock"][0]["loc_id"] == "L1"


def test_an_oversized_payload_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="ceiling"):
        export.write_export({"schema_version": "1.0.0", "pad": "x" * 500},
                            tmp_path / "ranked.json")
