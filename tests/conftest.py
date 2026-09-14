"""Shared fixtures.

Scoring Worcester's 2,099 parcels takes about 25 seconds, and seven
integration tests each used to do it themselves -- 182 seconds of work in a
suite that ran in about 163. These fixtures do it once per session.

Treat what they return as READ-ONLY. Every consumer in the suite today
(`export.build_export`, `occupants.attach`, `occupants.coverage`,
`mapgeo.frame_for`, `mapgeo.paths_for`, `site_data.enrich`) copies before it
changes anything, and `test_shared_fixtures.py` checks that stays true. A test
that needs to mutate must `.copy()` first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORCESTER_DIR = Path("data/raw/M348_WORCESTER/L3_SHP_M348_Worcester")
WORCESTER_TOWN_ID = 348
HAS_WORCESTER = (WORCESTER_DIR / "M348TaxPar_CY26_FY26.shp").exists()


@pytest.fixture(scope="session")
def worcester_parcels():
    if not HAS_WORCESTER:
        pytest.skip("Worcester L3 extract not present (data/raw is gitignored)")
    from shave import crosswalk, ingest

    # test_crosswalk loads temporary tables through the same lru_cache. Its
    # autouse fixture clears either side, but a session fixture must not
    # depend on test order to get the committed crosswalk.
    crosswalk.load.cache_clear()
    return ingest.load_municipality(str(WORCESTER_DIR), town_id=WORCESTER_TOWN_ID)


@pytest.fixture(scope="session")
def worcester_scored(worcester_parcels):
    from shave import pipeline

    return pipeline.score_parcels(worcester_parcels)
