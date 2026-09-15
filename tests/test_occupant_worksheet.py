"""Which rows need an operating business, and how research survives re-runs."""

import csv

import pandas as pd
import pytest

from shave import occupant_worksheet as ow


def _frames():
    rows = []
    # Worcester: 3 comstock, 1 modeled. Lowell: 1 comstock, 1 modeled. One dropped row.
    spec = [
        ("W1", 348, "comstock", 9000.0, True), ("W2", 348, "comstock", 8000.0, True),
        ("W3", 348, "comstock", 100.0, True), ("W4", 348, "modeled", 7000.0, True),
        ("L1", 160, "comstock", 50.0, True), ("L2", 160, "modeled", 40.0, True),
        ("X9", 348, "comstock", 99_999.0, False),
    ]
    for loc_id, town_id, source, usd, keep in spec:
        rows.append({"loc_id": loc_id, "source": source, "annual_savings_usd": usd, "keep": keep})
    scored = pd.DataFrame(rows)
    parcels = pd.DataFrame([{
        "loc_id": loc_id, "town_id": town_id, "site_addr": f"{loc_id} MAIN ST",
        "owner": f"{loc_id} REALTY TRUST", "use_desc": "Warehouse", "sqft": 10_000.0,
    } for loc_id, town_id, *_ in spec])
    return scored, parcels


def test_selection_is_the_top_n_plus_every_towns_list_heads_minus_resolved():
    scored, parcels = _frames()

    rows = ow.select_rows(scored, parcels, existing={"W2"}, top_n=2)

    ids = list(rows["loc_id"])
    # top 2 kept by dollars: W1, W2 (W2 already resolved); heads: W1, W4, L1, L2
    assert set(ids) == {"W1", "W4", "L1", "L2"}
    assert "X9" not in ids, "a dropped row is never on the list"
    assert ids == sorted(ids, key=lambda i: -dict(zip(scored.loc_id, scored.annual_savings_usd))[i])
    lowell_head = rows.set_index("loc_id").loc["L1"]
    assert (lowell_head["town"], lowell_head["list"], lowell_head["rank"]) == ("Lowell", "comstock", 1)


def test_rewriting_the_worksheet_keeps_every_research_cell(tmp_path):
    scored, parcels = _frames()
    path = tmp_path / "candidates.csv"
    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        table = list(csv.DictReader(fh))
    for row in table:
        if row["loc_id"] == "L1":
            row.update(candidate_occupant="Acme Mills", candidate_source="https://acme.example/lowell",
                       evidence="Contact page lists L1 MAIN ST.", status="verified", reviewer="PJ")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ow.FIELDS)
        writer.writeheader()
        writer.writerows(table)

    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        again = {r["loc_id"]: r for r in csv.DictReader(fh)}
    assert again["L1"]["candidate_occupant"] == "Acme Mills"
    assert again["L1"]["status"] == "verified" and again["L1"]["reviewer"] == "PJ"
    assert again["W4"]["status"] == "pending"


def test_a_new_row_starts_pending_with_empty_research():
    scored, parcels = _frames()
    rows = ow.select_rows(scored, parcels, existing=set(), top_n=1)
    assert set(rows["status"]) == {"pending"}
    assert set(rows["candidate_occupant"]) == {""}
