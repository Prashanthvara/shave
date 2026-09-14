"""The address index: a reader checks a building they already know."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from shave import addresses, method, pipeline

CASES = json.loads(Path("tests/fixtures/address_cases.json").read_text())


def test_the_shared_cases_file_carries_the_same_abbreviations_as_the_code():
    """app.js is tested against this file's table and reads the index's copy
    at run time. If the two drifted, the page would parse differently from
    the keys it is matching against."""
    assert CASES["abbreviations"] == addresses.ABBREVIATIONS


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["query"] or "empty")
def test_a_pasted_address_parses_to_its_street_and_town(case):
    got = addresses.parse_query(case["query"], CASES["towns"])
    assert got == {"street": case["street"], "town": case["town"]}


def test_normalize_leaves_nothing_to_match_for_a_missing_address():
    assert addresses.normalize(None) == ""
    assert addresses.normalize(pd.NA) == ""
    assert addresses.normalize(float("nan")) == ""
    assert addresses.normalize("100 C STREET") == "100 C ST"


def _frames():
    parcels = pd.DataFrame([
        {"loc_id": "A", "site_addr": "385 PLANTATION ST", "confidence": "MED"},
        {"loc_id": "B", "site_addr": "70 JAMES STREET", "confidence": "HIGH"},
        {"loc_id": "C", "site_addr": "10 ELBRIDGE ST", "confidence": "LOW"},
        {"loc_id": "D", "site_addr": "440 LINCOLN ST", "confidence": "HIGH"},
        {"loc_id": "E", "site_addr": pd.NA, "confidence": "HIGH"},
    ])
    base = {"source": "comstock", "archetype": "warehouse", "rate_class": "G-2"}
    scored = pd.DataFrame([
        {**base, "loc_id": "A", "sqft": 50_000.0, "avg_12mo_kw": 300.0,
         "annual_savings_usd": 30_000.0, "keep": True, "unscored_reason": None},
        {**base, "loc_id": "B", "sqft": 2_000.0, "avg_12mo_kw": 12.0,
         "annual_savings_usd": 400.0, "keep": False, "unscored_reason": None},
        {**base, "loc_id": "C", "sqft": float("nan"), "avg_12mo_kw": 0.0,
         "annual_savings_usd": 0.0, "keep": False, "unscored_reason": "no_floor_area"},
        {**base, "loc_id": "D", "sqft": 20_000.0, "avg_12mo_kw": 90.0,
         "annual_savings_usd": 2_000.0, "keep": True, "unscored_reason": None},
        {**base, "loc_id": "E", "sqft": 20_000.0, "avg_12mo_kw": 90.0,
         "annual_savings_usd": 2_000.0, "keep": True, "unscored_reason": None},
    ])
    lists = {"comstock": [{"loc_id": "A", "rank": 1}], "modeled": []}
    return parcels, scored, lists


def test_every_screened_parcel_is_indexed_with_what_happened_to_it():
    """A match must say ranked, screened out, or unscored -- never just
    'not found' for a building the pipeline actually looked at."""
    parcels, scored, lists = _frames()

    index = addresses.build_index(parcels, scored, lists, towns=["WORCESTER"])
    by_id = {e["loc_id"]: e for e in index["entries"]}

    assert by_id["A"]["status"] == "ranked"
    assert (by_id["A"]["list"], by_id["A"]["rank"]) == ("comstock", 1)
    assert by_id["B"]["status"] == "below_floor"
    assert by_id["B"]["key"] == "70 JAMES ST"
    assert by_id["C"]["status"] == "no_floor_area"
    assert by_id["C"]["sqft"] is None, "NaN floor area must not become a number"
    assert by_id["D"]["status"] == "not_exported"
    assert (by_id["D"]["list"], by_id["D"]["rank"]) == ("", None)
    assert index["towns"] == ["WORCESTER"]
    assert index["abbreviations"] == addresses.ABBREVIATIONS
    assert index["index_schema_version"] == addresses.INDEX_SCHEMA_VERSION


def test_a_parcel_with_no_address_is_left_out_rather_than_indexed_under_nothing():
    parcels, scored, lists = _frames()
    index = addresses.build_index(parcels, scored, lists, towns=["WORCESTER"])
    assert "E" not in {e["loc_id"] for e in index["entries"]}
    assert all(e["key"] for e in index["entries"])


def test_every_status_a_parcel_can_carry_has_a_sentence():
    expected = {"ranked", "not_exported", "below_floor", *pipeline.UNSCORED_REASONS}
    assert set(addresses.STATUS_SENTENCES) == expected
    for reason in pipeline.UNSCORED_REASONS:
        assert addresses.STATUS_SENTENCES[reason] == method.FLAG_MEANINGS[reason]


def test_every_exported_worcester_row_is_found_by_its_own_address(
    worcester_parcels, worcester_scored
):
    """Criterion 7 at the build: paste the address of anything on the list
    and the index finds that parcel exactly."""
    from shave import export, site_data

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)
    index = addresses.build_index(worcester_parcels, worcester_scored,
                                  enriched["lists"], towns=["WORCESTER"])

    keys = {}
    for e in index["entries"]:
        keys.setdefault(e["key"], set()).add(e["loc_id"])
    for name, rows in enriched["lists"].items():
        for row in rows:
            q = addresses.parse_query(f"{row['site_addr']}, Worcester, MA", ["WORCESTER"])
            assert row["loc_id"] in keys.get(q["street"], set()), (name, row["site_addr"])

    assert len(index["entries"]) == len(worcester_parcels)  # zero null addresses today
    blob = json.dumps(index, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < 700 * 1024
    for e in index["entries"]:
        for field in ("sqft", "avg_12mo_kw", "annual_savings_usd"):
            v = e[field]
            assert v is None or not (isinstance(v, float) and math.isnan(v))
