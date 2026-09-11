"""The published assumptions must be the computed ones, not lookalikes."""

import pytest

from shave import assumptions


def test_mecs_intensity_derives_each_subsector_from_the_published_figures():
    """MECS Table 3.2 net electricity in trillion Btu over Table 9.1 enclosed
    floorspace in million sq ft, at 3,412 Btu/kWh."""
    assert assumptions.mecs_intensity("332") == pytest.approx(23.753, abs=0.001)
    assert assumptions.mecs_intensity("333") == pytest.approx(22.964, abs=0.001)


def test_the_manufacturing_anchor_is_computed_not_asserted():
    """It is published with provenance DERIVED. If it were a literal, that
    label would be a claim the code does not back -- and this project has
    already shipped two of those.
    """
    expected = (assumptions.mecs_intensity("332") + assumptions.mecs_intensity("333")) / 2
    assert assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[
        "industrial_manufacturing"
    ] == pytest.approx(expected)


def test_the_btu_conversion_is_load_bearing():
    """BTU_PER_KWH sat in the file participating in nothing. If it is inert
    again, the derivation has been replaced by a literal again."""
    before = assumptions.mecs_intensity("332")
    original = assumptions.BTU_PER_KWH
    try:
        assumptions.BTU_PER_KWH = original * 2
        assert assumptions.mecs_intensity("332") == pytest.approx(before / 2)
    finally:
        assumptions.BTU_PER_KWH = original


def test_the_anchor_still_rounds_to_the_figure_the_method_page_published():
    """The value must not move: 23.4 is on the method page and in the ledger."""
    value = assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_manufacturing"]
    assert round(value, 1) == 23.4


def test_every_derived_assumption_names_a_source():
    for row in assumptions.published_rows():
        if row["provenance"] == "DERIVED":
            assert row["source"], f"{row['key']} is DERIVED with no source"
            assert len(row["note"]) > 40, f"{row['key']} does not say how it was derived"


def test_the_published_anchor_is_readable_not_a_raw_float():
    """The scorer uses the full derived value; the page shows it rounded.
    A lone 17-digit float beside siblings printed at one decimal reads as a
    leaked intermediate, not as a published assumption."""
    row = [r for r in assumptions.published_rows()
           if r["key"] == "intensity_industrial_manufacturing"][0]
    assert row["value"] == "23.36 kWh/sq ft/yr"
    # and the constant itself keeps full precision for the arithmetic
    assert assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[
        "industrial_manufacturing"] != 23.36
