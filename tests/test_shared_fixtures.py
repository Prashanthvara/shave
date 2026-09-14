"""The shared Worcester frames stay what the pipeline produced.

Session-scoped fixtures turn one test's in-place edit into every later test's
wrong input, and the failure shows up far from its cause. This runs every
consumer the suite uses against the shared frames and checks nothing moved.
"""

import pandas as pd

from shave import export, mapgeo, occupants, site_data


def test_consumers_do_not_mutate_the_shared_worcester_frames(
    worcester_parcels, worcester_scored
):
    parcels_before = worcester_parcels.copy(deep=True)
    scored_before = worcester_scored.copy(deep=True)

    raw = export.build_export(
        worcester_scored, worcester_parcels,
        town={"name": "Worcester", "town_id": 348}, top_n=25,
    )
    frame = mapgeo.frame_for(worcester_parcels)
    site_data.enrich(
        raw, worcester_scored,
        paths=mapgeo.paths_for(worcester_parcels, frame), view_box=frame.view_box,
    )
    occupants.attach(worcester_scored)
    occupants.coverage(worcester_scored, top_n=50)

    pd.testing.assert_frame_equal(worcester_scored, scored_before)
    pd.testing.assert_frame_equal(
        pd.DataFrame(worcester_parcels.drop(columns="geometry")),
        pd.DataFrame(parcels_before.drop(columns="geometry")),
    )
    assert worcester_parcels.crs == parcels_before.crs
    assert worcester_parcels.geometry.to_wkb().equals(parcels_before.geometry.to_wkb())
