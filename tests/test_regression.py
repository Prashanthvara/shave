"""Does the archetype layer earn its place, and does the tool say so honestly."""

import numpy as np
import pandas as pd
import pytest

from shave import regression


def test_r_squared_is_one_for_an_exact_linear_relationship():
    x = np.arange(50, dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    y = 3.0 * x + 7.0

    assert regression.r_squared(y, X) == pytest.approx(1.0)


def test_r_squared_is_zero_for_a_constant_predictor_against_noise():
    rng = np.random.default_rng(0)
    y = rng.normal(size=200)
    X = np.ones((200, 1))

    assert regression.r_squared(y, X) == pytest.approx(0.0, abs=1e-12)


def _frame(n=60, seed=0):
    rng = np.random.default_rng(seed)
    sqft = rng.uniform(5_000, 80_000, n)
    archetype = rng.choice(["warehouse", "strip_mall", "small_office"], n)
    intensity = pd.Series(archetype).map(
        {"warehouse": 1.8, "strip_mall": 9.1, "small_office": 3.9}
    ).to_numpy()
    peak = sqft * intensity / 1000.0
    return pd.DataFrame({
        "sqft": sqft,
        "archetype": archetype,
        "source": "comstock",
        "rate_class": np.where(peak >= 200.0, "G-3", "G-2"),
        "annual_savings_usd": peak * 40.0,
        "keep": True,
        "unscored_reason": pd.Series([None] * n, dtype=object),
    })


def test_archetype_terms_raise_r_squared_when_shape_matters():
    """Three archetypes with different intensities: size alone cannot explain
    the spread, and adding the archetype must close the gap."""
    scored = _frame()

    result = regression.run(scored)["by_source"]["comstock"]

    assert result["r2_with_archetype"] > result["r2_size_and_rate"]
    assert result["r2_with_archetype"] == pytest.approx(1.0, abs=1e-6)


def test_the_verdict_fires_when_size_alone_explains_everything():
    """One archetype, so savings are a pure function of size. The declared
    threshold must trip, and the rendered page must say so."""
    scored = _frame()
    scored["archetype"] = "warehouse"
    scored["annual_savings_usd"] = scored["sqft"] * 0.5

    result = regression.run(scored)
    assert result["by_source"]["comstock"]["archetype_adds_little"] is True
    assert "adding little" in regression.render_markdown(result)


def test_a_short_list_is_skipped_rather_than_fitted():
    scored = _frame(n=4)
    assert "skipped" in regression.run(scored)["by_source"]["comstock"]


def test_unscored_and_dropped_rows_are_excluded_from_the_fit():
    scored = _frame()
    scored.loc[scored.index[:10], "keep"] = False
    scored.loc[scored.index[10:20], "unscored_reason"] = "no_floor_area"

    assert regression.run(scored)["by_source"]["comstock"]["n"] == len(scored) - 20


def test_the_rendered_page_always_explains_the_r2_of_one():
    """The ~1.000 figure is indefensible without the sentence next to it."""
    page = regression.render_markdown(regression.run(_frame()))

    assert "by construction" in page
    assert "structured prior" in page


def test_the_page_never_claims_a_figure_its_own_table_contradicts():
    """The rendered text asserted "~1.000 by construction" while the real fit
    comes out at 0.878 on Worcester, because the scorer is not linear in floor
    area: a root-find against a fixed energy budget and a 250 kW power cap put
    a kink in it. A method page that contradicts its own table is the one
    thing this artifact cannot afford."""
    result = regression.run(_frame())
    page = regression.render_markdown(result)

    full = result["by_source"]["comstock"]["r2_with_archetype"]
    assert f"{full:.3f}" in page, "the stated figure must be the computed one"
    assert "~1.000 by construction" not in page
    assert "power cap" in page, "and it must say why it is not 1.000"
