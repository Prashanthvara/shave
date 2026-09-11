"""The hand-resolved occupant table, and success criterion 2."""

import csv
from pathlib import Path

import pytest

from shave import occupants
from shave.occupants import OccupantError

HEADER = ["loc_id", "occupant", "occupant_source", "verified_on", "note"]

WORCESTER_DIR = Path("data/raw/M348_WORCESTER/L3_SHP_M348_Worcester")
needs_worcester = pytest.mark.skipif(
    not (WORCESTER_DIR / "M348TaxPar_CY26_FY26.shp").exists(),
    reason="Worcester L3 extract not present (data/raw is gitignored)",
)


@pytest.fixture(autouse=True)
def _clean_occupant_cache():
    occupants.load.cache_clear()
    yield
    occupants.load.cache_clear()


def write_occupants(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "occ.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HEADER})
    return path


def good_row(**overrides: str) -> dict[str, str]:
    base = {
        "loc_id": "F_573183_2919659",
        "occupant": "Price Rite Marketplace",
        "occupant_source": "https://example.com/listing",
        "verified_on": "2026-09-11",
        "note": "",
    }
    base.update(overrides)
    return base


def test_a_row_without_a_source_is_rejected(tmp_path):
    """An unsourced occupant name is a guess, and a guess on the top row is
    exactly the claim a domain expert would check first."""
    with pytest.raises(OccupantError, match="occupant_source"):
        occupants.load(write_occupants(tmp_path, [good_row(occupant_source="")]))


def test_a_row_without_a_verification_date_is_rejected(tmp_path):
    with pytest.raises(OccupantError, match="verified_on"):
        occupants.load(write_occupants(tmp_path, [good_row(verified_on="")]))


def test_a_malformed_date_is_rejected(tmp_path):
    with pytest.raises(OccupantError, match="verified_on"):
        occupants.load(write_occupants(tmp_path, [good_row(verified_on="11/09/2026")]))


def test_duplicate_loc_id_is_rejected(tmp_path):
    rows = [good_row(), good_row(occupant="Something Else")]
    with pytest.raises(OccupantError, match="duplicate"):
        occupants.load(write_occupants(tmp_path, rows))


def test_a_missing_column_is_rejected(tmp_path):
    path = tmp_path / "short.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["loc_id", "occupant"])
        writer.writeheader()
        writer.writerow({"loc_id": "A", "occupant": "B"})
    with pytest.raises(OccupantError, match="missing columns"):
        occupants.load(path)


def test_a_good_row_loads(tmp_path):
    loaded = occupants.load(write_occupants(tmp_path, [good_row()]))
    assert loaded["F_573183_2919659"].occupant == "Price Rite Marketplace"
    assert loaded["F_573183_2919659"].verified_on == "2026-09-11"


def test_attach_leaves_unresolved_rows_blank_not_owner_named(tmp_path):
    """Showing the holding company in a column labelled `occupant` would
    assert something the table does not know."""
    import pandas as pd

    path = write_occupants(tmp_path, [good_row(loc_id="A")])
    scored = pd.DataFrame([
        {"loc_id": "A", "keep": True, "annual_savings_usd": 10.0},
        {"loc_id": "B", "keep": True, "annual_savings_usd": 5.0},
    ])
    out = occupants.attach(scored, path)
    assert out.loc[out["loc_id"] == "A", "occupant"].iloc[0] == "Price Rite Marketplace"
    assert out.loc[out["loc_id"] == "B", "occupant"].iloc[0] == ""


def test_coverage_counts_the_head_of_the_ranking(tmp_path):
    import pandas as pd

    path = write_occupants(tmp_path, [good_row(loc_id="A")])
    scored = pd.DataFrame([
        {"loc_id": "A", "keep": True, "annual_savings_usd": 10.0},
        {"loc_id": "B", "keep": True, "annual_savings_usd": 5.0},
        {"loc_id": "C", "keep": False, "annual_savings_usd": 0.0},
    ])
    stats = occupants.coverage(scored, top_n=2, path=path)
    assert stats == {"resolved_total": 1, "top_n": 2, "top_n_resolved": 1}


#: How many of the top 50 are resolved today. This ratchets: raise it as rows
#: land. The spec's own bar is 40 of 50 and it is NOT met yet -- the remaining
#: rows are hand lookups, and the method page reports the real figure rather
#: than the target.
RESOLVED_TOP_50_TODAY = 4
SPEC_TARGET_TOP_50 = 40


def test_the_committed_table_is_valid():
    """The shipped CSV must load. It is domain work, and a typo in it is a
    wrong claim on a published page."""
    table = occupants.load()
    assert table, "data/occupants.csv has no rows"
    for loc_id, row in table.items():
        assert row.occupant_source.startswith(("http://", "https://")) or row.note, (
            f"{loc_id}: a non-URL source needs a note saying what the record is"
        )


@needs_worcester
def test_the_top_ranked_row_names_a_real_business():
    """Success criterion 2, as a test.

    The spec: 'The top-ranked site is a real, named Massachusetts operating
    business at a verifiable address, with a one-sentence checkable reason.'
    If the head of the ranking is a holding company, the deliverable does not
    meet its own bar and this must fail.
    """
    from shave import ingest, pipeline

    parcels = ingest.load_municipality(str(WORCESTER_DIR), town_id=348)
    scored = occupants.attach(pipeline.score_parcels(parcels))
    top = scored[scored["keep"]].nlargest(1, "annual_savings_usd").iloc[0]

    assert top["occupant"], f"top-ranked parcel {top['loc_id']} has no resolved occupant"
    assert top["occupant_source"], "and no source for it"


@needs_worcester
def test_occupant_coverage_of_the_top_fifty_only_ever_goes_up():
    """A ratchet, not a target.

    Resolving the top 50 is hand work and is not finished: the spec asks for
    40 of 50 and the table holds RESOLVED_TOP_50_TODAY. This test exists so
    that number cannot quietly fall -- a row deleted or a ranking change that
    drops a resolved parcel out of the top 50 fails here. Raise the constant
    as rows land; when it reaches SPEC_TARGET_TOP_50 the spec's bar is met.
    """
    from shave import ingest, pipeline

    parcels = ingest.load_municipality(str(WORCESTER_DIR), town_id=348)
    stats = occupants.coverage(pipeline.score_parcels(parcels), top_n=50)

    assert stats["top_n_resolved"] >= RESOLVED_TOP_50_TODAY, (
        f"coverage fell to {stats['top_n_resolved']} from {RESOLVED_TOP_50_TODAY}"
    )
    assert RESOLVED_TOP_50_TODAY <= SPEC_TARGET_TOP_50
