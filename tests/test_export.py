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


def test_the_export_carries_every_sweet_spot_row_the_counts_line_promises():
    """The page prints a sweet-spot count and then filters the exported rows.
    If the export was cut by dollars first, the view shows a fraction of the
    number beside it -- and sweet-spot sites are small by construction, so
    they are exactly the rows a dollar cut removes. Measured on Worcester:
    172 promised, 68 shown, median sweet-spot dollar rank 316 of 526.
    """
    rows = [_row(f"L{i}", usd=100_000.0 - i) for i in range(60)]
    # Twenty sweet-spot sites, all ranked below the dollar cut.
    for i in range(60, 80):
        rows.append(_row(f"S{i}", usd=10.0 - i / 1000.0, sweet_spot=True))
    scored = pd.DataFrame(rows)
    parcels = _parcels([r["loc_id"] for r in rows])

    payload = export.build_export(scored, parcels,
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)

    exported = payload["lists"]["comstock"]
    sweet = [r for r in exported if r["sweet_spot"]]
    assert len(sweet) == 20, "every sweet-spot row must survive the dollar cut"
    assert payload["counts"]["sweet_spot"] == 20


def test_the_dollar_ranking_is_unchanged_by_the_sweet_spot_union():
    """Adding sweet-spot rows must not reorder the list or renumber its head."""
    rows = [_row(f"L{i}", usd=100_000.0 - i) for i in range(60)]
    rows.append(_row("S1", usd=5.0, sweet_spot=True))
    scored = pd.DataFrame(rows)

    payload = export.build_export(scored, _parcels([r["loc_id"] for r in rows]),
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)
    exported = payload["lists"]["comstock"]

    usd = [r["annual_savings_usd"] for r in exported]
    assert usd == sorted(usd, reverse=True), "still ranked by dollars"
    assert [r["rank"] for r in exported] == list(range(1, len(exported) + 1))
    assert exported[0]["loc_id"] == "L0", "the head of the list is untouched"
    assert exported[-1]["loc_id"] == "S1", "the sweet-spot row joins at its own rank"


def test_a_row_that_is_both_top_by_dollars_and_sweet_spot_appears_once():
    rows = [_row("A", usd=90_000.0, sweet_spot=True), _row("B", usd=80_000.0)]
    payload = export.build_export(pd.DataFrame(rows), _parcels(["A", "B"]),
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)
    ids = [r["loc_id"] for r in payload["lists"]["comstock"]]
    assert ids == ["A", "B"], f"duplicate or reordered: {ids}"


def test_the_reason_names_the_county_the_shape_actually_came_from():
    """Fall River is Bristol and Lowell is Middlesex. A sentence that says
    Worcester County for all three is a false provenance claim on a published
    page, which is the one thing the method page exists to prevent."""
    base = {
        "sqft": 100000.0, "use_desc": "Shopping Centers / Malls",
        "archetype": "strip_mall", "rate_class": "G-3",
        "demand_charge_per_kw": 10.48, "avg_12mo_kw": 500.0, "peak_kw": 700.0,
        "monthly_shaveable_kw": [100.0] * 12, "annual_savings_usd": 12000.0,
        "source": "comstock", "flags": [],
    }
    assert "Worcester County" in export.reason_sentence({**base, "town_id": 348})
    assert "Bristol County" in export.reason_sentence({**base, "town_id": 95})
    assert "Middlesex County" in export.reason_sentence({**base, "town_id": 160})


def test_a_widened_cohort_says_massachusetts_not_a_county():
    """When no county cohort existed the profile was pooled statewide, so
    naming that row's own county would claim a locality it does not have."""
    row = {
        "sqft": 100000.0, "use_desc": "Private Hospitals", "archetype": "hospital",
        "rate_class": "G-3", "demand_charge_per_kw": 10.48, "avg_12mo_kw": 500.0,
        "peak_kw": 700.0, "monthly_shaveable_kw": [100.0] * 12,
        "annual_savings_usd": 12000.0, "source": "comstock",
        "town_id": 95, "flags": ["thin_cohort"],
    }
    sentence = export.reason_sentence(row)
    assert "Massachusetts" in sentence
    assert "County" not in sentence


def test_a_modelled_row_claims_no_county_at_all():
    row = {
        "sqft": 100000.0, "use_desc": "Machine Shops", "archetype": "machine_shop",
        "rate_class": "G-2", "demand_charge_per_kw": 15.06, "avg_12mo_kw": 100.0,
        "peak_kw": 300.0, "monthly_shaveable_kw": [50.0] * 12,
        "annual_savings_usd": 9000.0, "source": "modeled",
        "town_id": 160, "flags": [],
    }
    assert "County" not in export.reason_sentence(row)
