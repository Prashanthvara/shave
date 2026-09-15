"""The covered municipalities, and the proof that the tariff applies to each."""

import pytest

from shave import towns


def test_three_towns_are_covered_in_order():
    assert [(t.town_id, t.name, t.slug) for t in towns.TOWNS] == [
        (348, "Worcester", "worcester"),
        (95, "Fall River", "fall-river"),
        (160, "Lowell", "lowell"),
    ]
    assert towns.by_id(160).county_gisjoin == "G2500170"
    assert towns.by_id("95").county_gisjoin == "G2500050"
    assert towns.county_for(None) == "G2500270"
    with pytest.raises(KeyError):
        towns.by_id(201)


def test_every_covered_town_is_national_grid_territory():
    """The G-2/G-3 tariff every dollar figure rests on is National Grid's."""
    elec = towns.utilities()
    for town in towns.TOWNS:
        assert elec[town.town_id] == towns.NATIONAL_GRID, town.name


def test_the_design_docs_new_bedford_and_chicopee_are_not():
    """Recorded so the swap to Fall River and Lowell is checkable, not asserted."""
    elec = towns.utilities()
    assert elec[201] == "Eversource Energy (NSTAR Electric)"             # New Bedford
    assert "Chicopee Municipal Lighting Plant" in elec[61]              # Chicopee
    assert len(elec) == 351


def test_extract_urls_follow_the_massgis_pattern():
    assert towns.by_id(95).l3_url == (
        "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
        "shapefiles/l3parcels/L3_SHP_M095_FALLRIVER.zip"
    )

from pathlib import Path


@pytest.mark.parametrize("town_id", [95, 160])
def test_each_new_town_scores_both_lists_with_no_missing_profile(town_id):
    from shave import ingest, pipeline, siting

    town = towns.by_id(town_id)
    if not Path(town.l3_dir).is_dir() or not siting.structures_path(town_id).exists():
        pytest.skip(f"{town.name} extract or roofprints not present")

    parcels = ingest.load_municipality(
        town.l3_dir, town_id, structures_path=siting.structures_path(town_id))
    scored = pipeline.score_parcels(parcels)
    kept = scored[scored["keep"].astype(bool)]

    assert parcels.attrs["roofprints_graded"] is True
    assert set(kept["source"]) == {"comstock", "modeled"}
    assert "no_archetype_profile" not in set(scored["unscored_reason"].dropna())
    hospitals = scored[(scored["archetype"] == "hospital") & scored["unscored_reason"].isna()]
    assert all("thin_cohort" in flags for flags in hospitals["flags"]), "pooled hospital shapes say so"
