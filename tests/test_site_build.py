"""What the build writes for each town, and the index that lists them."""

import json
from pathlib import Path

from shave import site_build, site_data, towns


def test_the_index_lists_each_town_with_its_counts_and_defaults_to_the_first():
    payloads = [
        {"town": {"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026},
         "counts": {"kept": 737}},
        {"town": {"town_id": 160, "name": "Lowell", "slug": "lowell", "assess_fy": 2026},
         "counts": {"kept": 10}},
    ]

    index = site_build.index_payload(payloads)

    assert index["site_schema_version"] == site_data.SITE_SCHEMA_VERSION == "2.0.0"
    assert index["default"] == "worcester"
    assert [t["slug"] for t in index["towns"]] == ["worcester", "lowell"]
    assert index["towns"][1]["counts"] == {"kept": 10}


def test_a_town_payload_is_that_towns_own_export_in_its_own_frame(worcester_parcels, worcester_scored):
    town = towns.by_id(348)

    payload = site_build.town_payload(town, worcester_parcels, worcester_scored)

    assert payload["town"] == {"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026}
    assert "method" not in payload
    assert payload["site_schema_version"] == "2.0.0"
    assert payload["map"]["view_box"].startswith("0 0 620 ")
    rows = [r for l in payload["lists"].values() for r in l]
    assert rows and any(r["path"] for r in rows), "the town's map would draw nothing"
    json.dumps(payload)


def test_town_data_paths_are_per_slug():
    assert site_build.town_data_path(Path("public/data"), "fall-river") == Path(
        "public/data/towns/fall-river/ranked.json")
