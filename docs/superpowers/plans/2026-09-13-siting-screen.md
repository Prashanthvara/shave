# Siting Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Join MassGIS roofprints to every parcel so the pipeline can state the longest clear wall run and its bearing, grade the spec's single-roofprint confidence predicate, fall back to roofprint area when the assessor records no floor area, and show all of it in the drawer and on the map.

**Architecture:** One new module, `src/shave/siting.py`, holds the geometry: loading `STRUCTURES_POLY`, assigning each roof to a parcel, and the wall-run screen. `ingest.build_parcels` calls it once, after the geometry join, so roofprint counts can feed confidence and roofprint area can feed floor area. The export carries the continuous result; `mapgeo` turns the wall into an SVG segment at build time; the page draws text and a hatched mark and computes nothing.

**Tech Stack:** Python 3.11, geopandas 1.1.4, shapely 2.1.2 (vectorised predicates), pyogrio, vanilla ES2020 + inline SVG, vitest, Cloudflare Workers static assets.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`. Specifically:
- Stage 1 step 2: *"`BLDG_AREA` null/zero handling… Fall back to roofprint area × estimated stories; drop to LOW confidence."*
- Stage 1 step 3: *"STRUCTURES_POLY spatial join: roofprint count per parcel, footprint area, and the siting geometry."*
- "Confidence tiers": HIGH requires *"exactly one roofprint on the parcel"*.
- "Siting screen — a screen-out, not a green light", in full. It is quoted in "Verified facts" below.
- Test plan, `siting` row: *"zero-lot-line → 0 ft; footprint ≈ parcel; collinear merge on a noisy roofprint"*.
- Design review D2, map channels: *"Hatched wall segment | the clear wall run and bearing from the siting screen"*.
- Interaction States, Site detail, Error: *"Longest clear run 0 ft — screened out, stated as a finding."*

**Prior plans:** `2026-09-13-finish-and-ship.md` is complete and live at `407eae0`. Its "What the next plans pick up" table names this plan first.

## Global Constraints

- Python `>=3.11`. **Do not add any Python or JavaScript dependency.** geopandas, shapely and pyogrio are already in `pyproject.toml`.
- **The page computes no figure it displays.** Distances, bearings, compass labels and wall paths are all computed in Python.
- **Never restate a constant.** Clearance, required run and default stories live in `src/shave/assumptions.py` and reach the page through the payload.
- **A screen-out, not a green light.** No output, field name or sentence may say a site *is* suitable. `clear` means "not screened out".
- **`--signal` is spent on exactly three things** (DESIGN.md): the shaved peak on a sparkline, parcel fill weight on the map, and the selected-row rail. The wall mark uses `--ink`.
- Radius 3px (`var(--r)`), no shadows, touch targets ≥ 44px, every assessor-derived string through `esc()`.
- **`data/raw/` is gitignored.** Source data is downloaded by script, never committed.
- **`node`, `npm` and `npx` are nvm shell functions.** Always call them through the full path:
  ```bash
  NB="$HOME/.nvm/versions/node/v22.18.0/bin"
  "$NB/npx" vitest run
  ```
- **Run pytest with no `-q`.** `pyproject.toml`'s `addopts` already passes `-q`, and a second one suppresses the `N passed` summary line.
- Baselines, measured 2026-09-13 on `main` at `407eae0`: **Python 992 passed, 4 deselected** (about 38 s); **render 50 passed**.
- Work on a branch: `git checkout -b feat/siting-screen` before Task 1.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts, measured 2026-09-13

Do not re-derive these. Do verify the checks each task names. The probes that produced them are in the session scratchpad and are not part of the plan.

**The source.** MassGIS Building Structures (2-D), layer `STRUCTURES_POLY`, is published per municipality at:

```
https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/structures/structures_poly_348.zip
```

- **Size:** 6.8 MB zipped, 33 MB unzipped.
- **Contents:** 50,241 features for Worcester. 50,240 are `Polygon` and 1 is `MultiPolygon`.
- **CRS:** EPSG:26986, the same as `TaxPar`.
- **Read time:** 0.8 s with pyogrio.
- **Fields:** `STRUCT_ID`, `SOURCE`, `SOURCETYPE`, `SOURCEDATE`, `SOURCEDATA`, `MOVED`, `AREA_SQ_FT`, `TOWN_ID`, `TOWN_ID2`, `TOWN_ID3`, `LOCAL_ID`, `EDIT_DATE`, `EDIT_BY`, `COMMENTS`, `SHAPE_AREA`, `SHAPE_LEN`.
- **`SOURCETYPE`:** `ROOFPRINT` 32,179; `ROOFPRINT_SHIFTED` 18,002; `FOOTPRINT` 60.

So almost everything is a **roof** outline: overhangs are included, and the wall below sits slightly inside it. Measured clearance is therefore a slight **under**estimate, which is the safe direction for a screen-out.

**Assigning a roof to a parcel.** The rule is the parcel containing the roof's **representative point**. Across Worcester's 2,098 mapped parcels:

| rule | 0 roofs | 1 roof | 2+ roofs | exported rows with 0 |
|---|---|---|---|---|
| representative point | **187** | **1,541** | 370 | **58** |
| largest overlap ≥ 50% | 214 | 1,515 | 369 | 64 |

Representative point is simpler and leaves fewer roofless parcels, so it is the rule. Of the 58 roofless exported parcels, **54 touch a roof** whose largest share inside the parcel is a median of **0.27**. In other words, the building sits mostly on a neighbouring lot. That is the parcel ≠ building case the single-roofprint predicate exists to catch, not a join bug.

**The screen.** The spec: *"simplify the footprint and merge near-collinear edges first… then offset each edge outward, test containment in the parcel polygon, take the longest passing run and its bearing."* The prototype of that algorithm, which `siting.wall_run` implements below:
- **Simplify:** 0.5 m.
- **Cells:** each wall is cut into 1 m cells, each extending from 0.05 m to 10 ft (3.048 m) outward.
- **Pass test:** a cell passes if it lies inside the parcel and touches no roofprint that touches the parcel.
- **Result:** the longest unbroken chain of passing cells on any one edge.

On exported rows:
- **Runtime:** vectorised, all **2,098 parcels in 5.2 s**. A per-cell shapely loop over only the 562 exported parcels took 23.8 s.
- **Clear-wall distribution:** 5th percentile **45 ft**, 25th **85 ft**, median **138 ft**, 90th **299 ft**.
- **Under the 13.1 ft two cabinets need:** **7** exported rows, **3** of them at exactly 0. Across all mapped parcels with a roofprint, **39 of 1,884**.

That is what the spec predicted: rarely discriminating, and correct when it is.

- The ComStock list's rank 1, `F_577265_2910122` (RK Worcester Crossing): **88 m = 288.7 ft**, facing **228°**.
- The modelled list's rank 1, `F_585218_2926290` (UMass Chan): **130 m = 426.5 ft**, facing **100°**.

**The confidence shift is large, and it is the spec's own rule.** Adding `single_roofprint` as a seventh predicate:

| | HIGH | MED | LOW |
|---|---|---|---|
| all 2,099, before | 794 | 984 | 321 |
| all 2,099, after | **605** | **905** | **589** |
| 563 exported, before | 121 | 221 | 221 |
| 563 exported, after | **87** | **177** | **299** |

**Confidence never feeds scoring or ranking.** It appears in `export.PARCEL_FIELDS` only, and in no expression in `scorer.py`, `pipeline.py` or `regression.py`. No rank, dollar figure or R² changes.

**The floor-area fallback has no Worcester case today.** Every Worcester parcel with a polygon has a recorded floor area. The one `no_floor_area` parcel is the one with no geometry (`missing_geometry: 1`). The fallback is built and tested synthetically, and the real-data test pins its Worcester count at **0**. It matters when New Bedford and Chicopee land.

**Map scale.** One SVG unit is about 17 m across Worcester (620 units over ~10.7 km), so a median 138 ft (42 m) wall draws about 2.4 units long. Hatching all 172 sweet-spot walls at once would be noise. **The wall is drawn for the selected parcel only.** Parcels smaller than `mapgeo.MIN_SPAN_UNITS` are grown about their own centre, so the wall must be grown with the same centre and scale or it will float off its building.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/assumptions.py` *(modify)* | `MIN_WALL_RUN_FT`, `DEFAULT_STORIES`, both published. |
| `src/shave/siting.py` *(new)* | Loading roofprints, assigning them to parcels, the wall-run screen. One concern: parcel geometry against building geometry. |
| `scripts/fetch_structures.py` *(new)* | Download and unzip one town's layer. |
| `tests/test_siting.py` *(new)* | The spec's three siting cases plus assignment, statuses and real data. |
| `tests/conftest.py` *(modify)* | Session fixture for the structures layer; Worcester parcels loaded with it. |
| `src/shave/ingest.py` *(modify)* | Calls the screen, grades `single_roofprint`, applies the fallback. |
| `src/shave/mapgeo.py` *(modify)* | `wall_path_for`, `walls_for`, sharing the parcel's growth transform. |
| `src/shave/export.py`, `src/shave/site_data.py`, `scripts/build_site.py` *(modify)* | Carry the result, the wall path, the facing label and the rule. |
| `docs/ranked-json-schema.md` *(modify)* | Schema `1.5.0`. |
| `public/app.js`, `public/index.html`, `public/app.css` *(modify)* | Drawer sentence, selected-parcel wall mark, legend. |
| `src/shave/method.py` *(modify)* | The screen's limits replace the "map shows no siting" gap. |
| `docs/spec-coverage.md` *(modify)* | Steps 2 and 3 complete. |

---

## Task 1: The siting screen, on its own

**Files:**
- Create: `src/shave/siting.py`
- Create: `scripts/fetch_structures.py`
- Create: `tests/test_siting.py`
- Modify: `src/shave/assumptions.py` (the "Siting" block, lines 125–137; `PUBLISHED`, after the `wall_clearance` entry)
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces:
  - `assumptions.MIN_WALL_RUN_FT: float = 13.1`
  - `siting.STRUCTURES_URL: str`, `siting.CRS_EPSG = 26986`, `siting.SQFT_PER_SQM: float`
  - `siting.SITING_STATUSES = ("clear", "screened_out", "no_roofprint", "no_geometry")`
  - `siting.SCREEN_COLUMNS = ("loc_id", "roofprint_count", "roofprint_sqft", "wall_run_ft", "wall_bearing_deg", "wall_segment", "siting")`
  - `siting.structures_url(town_id: int) -> str`
  - `siting.structures_path(town_id: int, root: str | Path = "data/raw") -> Path`
  - `siting.load_structures(path) -> GeoDataFrame` with columns `STRUCT_ID` and `geometry`, EPSG:26986
  - `siting.assign_roofprints(parcels: GeoDataFrame, structures: GeoDataFrame) -> pd.Series`, which maps `loc_id` to a list of row positions into `structures`
  - `siting.WallRun(run_ft: float, bearing_deg: int | None, segment: LineString | None)`, a frozen dataclass
  - `siting.wall_run(parcel, roofs, obstacles) -> WallRun`
  - `siting.screen(parcels: GeoDataFrame, structures: GeoDataFrame) -> pd.DataFrame`, with exactly `SCREEN_COLUMNS` and one row per input parcel
  - conftest fixture `worcester_structures`, session-scoped, which skips when the file is absent

- [ ] **Step 1: Branch and fetch the data**

```bash
git checkout -b feat/siting-screen
```

Create `scripts/fetch_structures.py` first. It needs `siting.structures_url`, so it will not run until Step 5; write it now so the data path is fixed before any test names it:

```python
"""Download one town's MassGIS Building Structures (2-D) layer.

    uv run python scripts/fetch_structures.py --town-id 348

Writes data/raw/M<town_id>_STRUCTURES/structures_poly_<town_id>.shp and its
sidecar files. data/raw is gitignored: this is regenerable source data, and
the address it comes from is `siting.STRUCTURES_URL`.
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile

from shave import siting


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--root", default="data/raw")
    args = parser.parse_args()

    url = siting.structures_url(args.town_id)
    target = siting.structures_path(args.town_id, root=args.root).parent
    target.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as response:
        blob = response.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        archive.extractall(target)
    print(f"{url}\n{len(blob) / 1e6:.1f} MB -> {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add the required wall run to `assumptions.py`**

Directly after the line `MIN_WALL_CLEARANCE_FT = 10.0`, add:

```python

# Linear wall two cabinets need side by side, with working separation between
# and beside them. The design doc: "two side by side plus separation need
# roughly 4 linear metres of wall". Four metres is 13.1 ft.
MIN_WALL_RUN_FT = 13.1
```

In `PUBLISHED`, directly after the `Assumption("wall_clearance", …)` entry, add:

```python
    Assumption(
        "min_wall_run", MIN_WALL_RUN_FT, "ft", "ASSUMED",
        "design doc, from the cabinet footprint",
        "Two 39.4 in cabinets side by side plus working separation, read as "
        "roughly four linear metres. Below this a site is screened out; above "
        "it nothing is confirmed.",
    ),
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_siting.py`:

```python
"""The siting screen: a screen-out, not a green light."""

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

from shave import siting
from shave.assumptions import MIN_WALL_RUN_FT

FT_PER_M = 1 / 0.3048


def _parcels(**geoms) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"loc_id": list(geoms)}, geometry=list(geoms.values()), crs="EPSG:26986"
    )


def _structures(*geoms) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"STRUCT_ID": [f"S{i}" for i in range(len(geoms))]},
        geometry=list(geoms), crs="EPSG:26986",
    )


# --- the spec's three cases ------------------------------------------------


def test_a_zero_lot_line_building_has_no_clear_wall():
    """Spec test plan: zero-lot-line -> 0 ft."""
    parcel = box(0, 0, 30, 30)
    roof = box(0, 0, 30, 30)

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft == 0.0
    assert result.segment is None
    assert result.bearing_deg is None


def test_a_footprint_that_fills_the_parcel_has_no_clear_wall():
    """Spec test plan: footprint ~= parcel. Half a metre of side yard is not
    ten feet of working space."""
    parcel = box(0, 0, 30, 30)
    roof = box(0.5, 0.5, 29.5, 29.5)

    assert siting.wall_run(parcel, [roof], [roof]).run_ft == 0.0


def test_near_collinear_vertices_are_merged_before_measuring():
    """Spec test plan: collinear merge on a noisy roofprint. Imagery-derived
    walls zig-zag by tens of centimetres every metre; unmerged, a 30 m wall is
    thirty 1 m walls and the longest run would be 1 m."""
    bottom = [(float(x), 20.0 + (0.2 if x % 2 else 0.0)) for x in range(31)]
    roof = Polygon(bottom + [(30.0, 40.0), (0.0, 40.0)])
    parcel = box(0, 0, 30, 40)

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft > 90.0
    assert result.bearing_deg == 180


# --- the measurement itself ------------------------------------------------


def test_a_clear_south_yard_gives_the_full_wall_and_its_bearing():
    parcel = box(0, 0, 30, 40)
    roof = box(0, 20, 30, 40)  # flush to three lot lines, 20 m yard to the south

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft == pytest.approx(30 * FT_PER_M, abs=0.1)
    assert result.bearing_deg == 180
    (x1, y1), (x2, y2) = result.segment.coords
    assert (y1, y2) == (pytest.approx(20.0), pytest.approx(20.0))
    assert abs(x2 - x1) == pytest.approx(30.0)


def test_a_shed_in_the_yard_breaks_the_run():
    """An obstruction is anything with a roof, including the site's own
    outbuildings."""
    parcel = box(0, 0, 30, 40)
    roof = box(0, 20, 30, 40)
    shed = box(12.5, 17.0, 17.5, 19.5)

    result = siting.wall_run(parcel, [roof], [roof, shed])

    # cells 12..17 touch the shed, leaving two 12 m runs either side
    assert result.run_ft == pytest.approx(12 * FT_PER_M, abs=0.1)


def test_screen_gives_every_parcel_a_status_and_never_a_green_light():
    parcels = _parcels(
        A=box(0, 0, 30, 40),        # clear south yard
        B=box(100, 0, 130, 30),     # zero lot line
        C=box(200, 0, 230, 30),     # empty lot
        D=None,                     # no polygon
    )
    structures = _structures(box(0, 20, 30, 40), box(100, 0, 130, 30))

    out = siting.screen(parcels, structures).set_index("loc_id")

    assert list(out.reset_index().columns) == list(siting.SCREEN_COLUMNS)
    assert out.loc["A", "siting"] == "clear"
    assert out.loc["A", "roofprint_count"] == 1
    assert out.loc["A", "roofprint_sqft"] == pytest.approx(600 * siting.SQFT_PER_SQM, abs=1)
    assert out.loc["B", "siting"] == "screened_out"
    assert out.loc["B", "wall_run_ft"] == 0.0
    assert out.loc["C", "siting"] == "no_roofprint"
    assert out["wall_run_ft"].isna()["C"], "no roof means no measurement, not 0 ft"
    assert out.loc["D", "siting"] == "no_geometry"
    assert set(out["siting"]) <= set(siting.SITING_STATUSES)
    assert MIN_WALL_RUN_FT > 0


def test_a_roof_straddling_a_lot_line_is_counted_once():
    """Assigned to the parcel holding its representative point, never to both."""
    parcels = _parcels(L=box(0, 0, 10, 10), R=box(10, 0, 20, 10))
    structures = _structures(box(3, 2, 13, 8))  # 70% of it on L

    assigned = siting.assign_roofprints(parcels, structures)

    assert list(assigned.get("L", [])) == [0]
    assert "R" not in assigned.index


def test_the_download_address_and_local_path_follow_the_massgis_pattern():
    assert siting.structures_url(348) == (
        "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
        "shapefiles/structures/structures_poly_348.zip"
    )
    assert str(siting.structures_path(348)) == (
        "data/raw/M348_STRUCTURES/structures_poly_348.shp"
    )


def test_a_layer_in_the_wrong_crs_is_refused(tmp_path):
    wrong = _structures(box(0, 0, 1, 1)).set_crs(4326, allow_override=True)
    path = tmp_path / "wrong.shp"
    wrong.to_file(path)

    with pytest.raises(ValueError, match="EPSG:26986"):
        siting.load_structures(path)


# --- real data -------------------------------------------------------------


def test_the_top_ranked_worcester_sites_measure_as_the_prototype_did(
    worcester_parcels, worcester_structures
):
    """RK Worcester Crossing and UMass Chan, measured 2026-09-13."""
    wanted = worcester_parcels[
        worcester_parcels["loc_id"].isin(["F_577265_2910122", "F_585218_2926290"])
    ][["loc_id", "geometry"]]

    out = siting.screen(wanted, worcester_structures).set_index("loc_id")

    one_cell_ft = 1.0 * FT_PER_M
    assert out.loc["F_577265_2910122", "wall_run_ft"] == pytest.approx(288.7, abs=one_cell_ft)
    assert out.loc["F_577265_2910122", "wall_bearing_deg"] == 228
    assert out.loc["F_585218_2926290", "wall_run_ft"] == pytest.approx(426.5, abs=one_cell_ft)
    assert out.loc["F_585218_2926290", "wall_bearing_deg"] == 100
    assert set(out["siting"]) == {"clear"}
```

In `tests/conftest.py`, add below `HAS_WORCESTER = ...`:

```python
STRUCTURES_PATH = Path("data/raw/M348_STRUCTURES/structures_poly_348.shp")
HAS_STRUCTURES = STRUCTURES_PATH.exists()
```

and append:

```python
@pytest.fixture(scope="session")
def worcester_structures():
    if not HAS_STRUCTURES:
        pytest.skip(
            "Worcester STRUCTURES_POLY not present (data/raw is gitignored); "
            "run scripts/fetch_structures.py --town-id 348"
        )
    from shave import siting

    return siting.load_structures(STRUCTURES_PATH)
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv run pytest tests/test_siting.py`
Expected: FAIL — `ImportError: cannot import name 'siting' from 'shave'`

- [ ] **Step 5: Write `src/shave/siting.py`**

```python
"""The siting screen: a screen-out, not a green light.

Two cabinets side by side need roughly four metres of wall, and nearly every
commercial building in Massachusetts has that. A yes/no "sitable" flag would be
true almost everywhere and would claim a viability a domain expert can refute
from one aerial photo. So this module outputs the continuous fact instead --
the longest wall run with MIN_WALL_CLEARANCE_FT of unobstructed parcel-side
clearance, and the direction it faces -- and uses it only to screen out the
impossible: zero-lot-line buildings, footprints that fill the parcel, no side
yard.

The source is MassGIS Building Structures (2-D), STRUCTURES_POLY: roof outlines
digitised from aerial imagery. A roofprint includes overhangs, so the wall
below sits a little inside it and the clearance measured here is a slight
underestimate. That is the safe direction for a screen-out.

Measured on Worcester, 2026-09-13: 50,241 roofprints. A representative-point
join puts exactly one on 1,541 of 2,098 mapped parcels, several on 370 and
none on 187. The screen runs over every parcel in about five seconds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import LineString

from shave.assumptions import MIN_WALL_CLEARANCE_FT, MIN_WALL_RUN_FT

#: MassGIS publishes one shapefile per municipality at this address.
STRUCTURES_URL = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
    "shapefiles/structures/structures_poly_{town_id}.zip"
)

#: Massachusetts State Plane, metres: the CRS of TaxPar and STRUCTURES_POLY.
CRS_EPSG = 26986

M_PER_FT = 0.3048
FT_PER_M = 1.0 / M_PER_FT
SQFT_PER_SQM = FT_PER_M * FT_PER_M

#: Deviation below which a wall is treated as straight. Imagery-derived
#: roofprints carry dozens of spurious vertices; unmerged, a 30 m wall is thirty
#: 1 m walls and the longest run comes out as 1 m.
SIMPLIFY_M = 0.5

#: Length of each clearance cell tested along a wall.
STEP_M = 1.0

#: Gap between a wall and its cells, so a cell never touches the roof it is
#: measured from.
WALL_GAP_M = 0.05

SITING_STATUSES: tuple[str, ...] = ("clear", "screened_out", "no_roofprint", "no_geometry")

SCREEN_COLUMNS: tuple[str, ...] = (
    "loc_id", "roofprint_count", "roofprint_sqft", "wall_run_ft",
    "wall_bearing_deg", "wall_segment", "siting",
)


def structures_url(town_id: int) -> str:
    return STRUCTURES_URL.format(town_id=int(town_id))


def structures_path(town_id: int, root: str | Path = "data/raw") -> Path:
    tid = int(town_id)
    return Path(root) / f"M{tid}_STRUCTURES" / f"structures_poly_{tid}.shp"


def load_structures(path: str | Path) -> gpd.GeoDataFrame:
    """`STRUCT_ID` and geometry, in EPSG:26986. Refuses any other CRS: a
    metre-based clearance test on degrees would pass everything."""
    gdf = pyogrio.read_dataframe(path, columns=["STRUCT_ID"])
    epsg = gdf.crs.to_epsg() if gdf.crs is not None else None
    if epsg != CRS_EPSG:
        raise ValueError(f"{path}: expected EPSG:{CRS_EPSG}, got {gdf.crs}")
    keep = gdf.geometry.notna() & ~gdf.geometry.is_empty
    return gdf.loc[keep].reset_index(drop=True)


def assign_roofprints(parcels: gpd.GeoDataFrame, structures: gpd.GeoDataFrame) -> pd.Series:
    """Row positions in `structures`, grouped by the parcel that holds each
    roof's representative point.

    A roof straddling a lot line is counted once, never on both parcels.
    Measured on Worcester this leaves fewer parcels roofless (187) than
    assigning by majority overlap (214). Parcels with no roof are absent from
    the result.
    """
    mapped = parcels.loc[
        parcels.geometry.notna() & ~parcels.geometry.is_empty, ["loc_id", "geometry"]
    ]
    points = gpd.GeoDataFrame(
        {"row": np.arange(len(structures))},
        geometry=structures.geometry.representative_point(),
        crs=structures.crs,
    )
    joined = gpd.sjoin(points, mapped, predicate="within", how="inner")
    return joined.groupby("loc_id")["row"].apply(list)


@dataclass(frozen=True)
class WallRun:
    #: Longest unbroken wall with full clearance, in feet. 0.0 when none.
    run_ft: float
    #: The direction that wall faces, degrees clockwise from grid north.
    bearing_deg: int | None
    #: The run itself, along the wall, in EPSG:26986.
    segment: LineString | None


def _longest_true_run(ok: np.ndarray) -> tuple[int, int]:
    """(length, start index) of the longest run of consecutive True values."""
    best_len = best_start = current = 0
    for i, passed in enumerate(ok):
        current = current + 1 if passed else 0
        if current > best_len:
            best_len, best_start = current, i - current + 1
    return best_len, best_start


def wall_run(parcel, roofs, obstacles) -> WallRun:
    """The longest wall on `roofs` with clearance to the parcel line.

    Each exterior edge of each simplified roof is cut into STEP_M cells. A cell
    is the rectangle from just off the wall out to MIN_WALL_CLEARANCE_FT; it
    passes when it lies inside the parcel and touches no obstacle. The answer
    is the longest unbroken chain of passing cells on any one edge.

    `obstacles` is every roofprint touching the parcel, including `roofs`
    themselves: an L-shaped building's own wing blocks the wall in its corner,
    and a neighbour's garage across the lot line blocks just as well.
    """
    clearance = MIN_WALL_CLEARANCE_FT * M_PER_FT
    shapely.prepare(parcel)
    blocking = shapely.union_all(list(obstacles)) if len(obstacles) else None
    if blocking is not None:
        shapely.prepare(blocking)

    best = WallRun(0.0, None, None)
    for roof in roofs:
        simple = shapely.simplify(roof, SIMPLIFY_M, preserve_topology=True)
        for poly in shapely.get_parts(simple):
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
            coords = np.asarray(poly.exterior.coords)
            if not poly.exterior.is_ccw:
                coords = coords[::-1]
            for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
                length = math.hypot(x2 - x1, y2 - y1)
                n = int(length // STEP_M)
                if n == 0:
                    continue
                ux, uy = (x2 - x1) / length, (y2 - y1) / length
                nx, ny = uy, -ux  # the outward normal of a counter-clockwise ring
                k = np.arange(n)
                ax, ay = x1 + ux * k * STEP_M, y1 + uy * k * STEP_M
                bx, by = ax + ux * STEP_M, ay + uy * STEP_M
                rings = np.stack(
                    [
                        np.c_[ax + nx * WALL_GAP_M, ay + ny * WALL_GAP_M],
                        np.c_[bx + nx * WALL_GAP_M, by + ny * WALL_GAP_M],
                        np.c_[bx + nx * clearance, by + ny * clearance],
                        np.c_[ax + nx * clearance, ay + ny * clearance],
                        np.c_[ax + nx * WALL_GAP_M, ay + ny * WALL_GAP_M],
                    ],
                    axis=1,
                )
                cells = shapely.polygons(rings)
                ok = shapely.contains(parcel, cells)
                if blocking is not None:
                    ok &= ~shapely.intersects(blocking, cells)
                cell_count, start = _longest_true_run(ok)
                run_m = cell_count * STEP_M
                run_ft = round(run_m * FT_PER_M, 1)
                if run_ft > best.run_ft:
                    sx, sy = x1 + ux * start * STEP_M, y1 + uy * start * STEP_M
                    best = WallRun(
                        run_ft=run_ft,
                        bearing_deg=int(round(math.degrees(math.atan2(nx, ny)))) % 360,
                        segment=LineString([(sx, sy), (sx + ux * run_m, sy + uy * run_m)]),
                    )
    return best


def screen(parcels: gpd.GeoDataFrame, structures: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per parcel, in input order, with exactly SCREEN_COLUMNS.

    `clear` means only "not screened out". Nothing here can see loading docks,
    fire lanes, egress, wall openings, setbacks or the service entrance.
    """
    epsg = parcels.crs.to_epsg() if parcels.crs is not None else None
    if epsg != CRS_EPSG:
        raise ValueError(f"parcels: expected EPSG:{CRS_EPSG}, got {parcels.crs}")

    assigned = assign_roofprints(parcels, structures)
    geoms = list(structures.geometry)
    index = structures.sindex

    rows = []
    for loc_id, parcel in zip(parcels["loc_id"], parcels.geometry):
        if parcel is None or parcel.is_empty:
            rows.append((loc_id, 0, 0.0, None, None, None, "no_geometry"))
            continue
        own = list(assigned.get(loc_id, []))
        if not own:
            rows.append((loc_id, 0, 0.0, None, None, None, "no_roofprint"))
            continue
        area_sqft = round(sum(geoms[i].area for i in own) * SQFT_PER_SQM, 0)
        touching = index.query(parcel, predicate="intersects")
        result = wall_run(parcel, [geoms[i] for i in own], [geoms[i] for i in touching])
        status = "clear" if result.run_ft >= MIN_WALL_RUN_FT else "screened_out"
        rows.append((
            loc_id, len(own), area_sqft, result.run_ft,
            result.bearing_deg, result.segment, status,
        ))
    return pd.DataFrame(rows, columns=list(SCREEN_COLUMNS))
```

- [ ] **Step 6: Fetch the data and run the tests**

```bash
uv run python scripts/fetch_structures.py --town-id 348
uv run pytest tests/test_siting.py
```

Expected: the fetch prints `6.8 MB -> data/raw/M348_STRUCTURES`, and **10 passed**. If the data was already fetched during planning, the script overwrites it identically.

- [ ] **Step 7: Measure the whole town**

```bash
uv run python -c "
import time, collections
from shave import ingest, siting
p = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
s = siting.load_structures(siting.structures_path(348))
t = time.perf_counter(); out = siting.screen(p, s); el = time.perf_counter() - t
print(f'screened {len(out)} parcels in {el:.1f}s')
print(dict(collections.Counter(out['siting'])))
print('roofprints per parcel:', dict(collections.Counter(out['roofprint_count'].clip(upper=2))))
"
```

**Pass conditions, declared in advance:**
- 2,099 rows, screened in under **15 s**;
- `no_geometry` exactly **1**;
- roofprint counts of **0 = 187 + 1** (the unmapped parcel counts as 0), **1 = 1,541**, **2+ = 370**.

Report the status counts.

- [ ] **Step 8: Run the full suite and commit**

```bash
uv run pytest
git add src/shave/siting.py src/shave/assumptions.py scripts/fetch_structures.py \
        tests/test_siting.py tests/conftest.py
git commit -m "feat: the siting screen, a screen-out and not a green light

Joins MassGIS STRUCTURES_POLY roofprints to parcels by representative point
and measures the longest wall with ten feet of unobstructed parcel-side
clearance, with the direction it faces. Imagery-derived roofprints are
simplified first, so a zig-zagging 30 m wall measures as 30 m rather than as
thirty 1 m walls. Anything with a roof touching the parcel is an obstruction,
the site's own wings and outbuildings included.

Measured on Worcester: 50,241 roofprints, all 2,098 mapped parcels screened in
about five seconds, median exported clear run 138 ft, seven exported rows
under the 13.1 ft two cabinets need.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **1002 passed, 4 deselected** (992 + 10).

---

## Task 2: Roofprints feed confidence and floor area

The spec's HIGH tier requires *"exactly one roofprint on the parcel"*, and step 2 requires the roofprint fallback. Both need the geometry join, so grading moves after it.

**Files:**
- Modify: `src/shave/ingest.py`
  - the assumptions import, line 90
  - `PREDICATES` and its comment, lines 125–141
  - `OUTPUT_COLUMNS`, lines 143–148
  - `build_parcels`: signature at lines 276–282, office band and confidence at lines 397–403, geometry block ending line 441, final schema at lines 444–497
  - `_apply_confidence`, lines 508–557
  - `load_municipality`, lines 565–626
- Modify: `src/shave/assumptions.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `siting.screen`, `siting.SCREEN_COLUMNS`, `siting.load_structures` (Task 1).
- Produces:
  - `assumptions.DEFAULT_STORIES: float = 1.0`
  - `ingest.PREDICATES` gains `"single_roofprint"` as its seventh entry
  - `ingest.FALLBACK_REASON = "floor_area_from_roofprint"`
  - `build_parcels(assess, taxpar=None, *, town_id=None, assess_fy_hint=None, structures=None)`
  - `load_municipality(dir_path, town_id, structures_path=None)`
  - output columns gain `sqft_source` ("assessor" | "roofprint"), `roofprint_count` (Int64), `roofprint_sqft` (Float64), `wall_run_ft` (Float64), `wall_bearing_deg` (Int64), `siting` (string), `wall_segment` (shapely LineString or None)
  - `gdf.attrs` gains `roofprints_graded: bool` and `fallback_floor_area: int`
  - conftest `worcester_parcels` is loaded **with** structures, and skips if either file is absent

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ingest.py`:

```python
# ---------------------------------------------------------------------------
# roofprints: the seventh predicate and the floor-area fallback
# ---------------------------------------------------------------------------

from shave import siting
from shave.ingest import FALLBACK_REASON


def roofs(*geoms) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"STRUCT_ID": [f"S{i}" for i in range(len(geoms))]},
        geometry=list(geoms), crs="EPSG:26986",
    )


def test_exactly_one_roofprint_keeps_a_clean_parcel_high():
    row = only(build_parcels(
        assess(record()), taxpar("F_100000_900000"),
        town_id=WORCESTER_TOWN_ID, structures=roofs(square(2, 2, 4)),
    ))
    assert row.roofprint_count == 1
    assert row.confidence == "HIGH"
    assert row.confidence_reasons == ()


def test_two_roofprints_fail_single_roofprint():
    row = only(build_parcels(
        assess(record()), taxpar("F_100000_900000"),
        town_id=WORCESTER_TOWN_ID, structures=roofs(square(1, 1, 2), square(6, 6, 2)),
    ))
    assert row.roofprint_count == 2
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("single_roofprint",)


def test_no_roofprint_fails_single_roofprint():
    row = only(build_parcels(
        assess(record()), taxpar("F_100000_900000"),
        town_id=WORCESTER_TOWN_ID, structures=roofs(square(500, 500, 4)),
    ))
    assert row.roofprint_count == 0
    assert row.siting == "no_roofprint"
    assert row.confidence_reasons == ("single_roofprint",)


def test_without_structures_the_roofprint_predicate_is_not_graded():
    """Synthetic frames without a structures layer grade the other six. The
    real pipeline always supplies one; the attrs say which happened."""
    gdf = build_parcels(assess(record()), taxpar("F_100000_900000"), town_id=WORCESTER_TOWN_ID)
    row = only(gdf)
    assert gdf.attrs["roofprints_graded"] is False
    assert pd.isna(row.roofprint_count)
    assert row.confidence == "HIGH"


def test_missing_floor_area_falls_back_to_roofprint_times_stories_and_drops_to_low():
    """Spec step 2: fall back to roofprint area x estimated stories; drop to LOW."""
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", BLD_AREA=None, STORIES="2"),
            record(LOC_ID="F_2_2", BLD_AREA=10_000),  # keeps 3160 in scope
        ),
        taxpar("F_1_1", "F_2_2"),
        town_id=WORCESTER_TOWN_ID,
        structures=roofs(square(1, 1, 8), square(21, 1, 8)),
    )
    rows = gdf.set_index("loc_id")

    fallback = rows.loc["F_1_1"]
    assert fallback.sqft == pytest.approx(64 * siting.SQFT_PER_SQM * 2, abs=0.5)
    assert fallback.sqft_source == "roofprint"
    assert fallback.confidence == "LOW"
    assert "has_floor_area" in fallback.confidence_reasons
    assert FALLBACK_REASON in fallback.confidence_reasons

    recorded = rows.loc["F_2_2"]
    assert recorded.sqft == 10_000
    assert recorded.sqft_source == "assessor"
    assert gdf.attrs["fallback_floor_area"] == 1


def test_the_fallback_assumes_one_story_when_none_is_recorded():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", BLD_AREA=None, STORIES=None),
            record(LOC_ID="F_2_2", BLD_AREA=10_000),
        ),
        taxpar("F_1_1", "F_2_2"),
        town_id=WORCESTER_TOWN_ID,
        structures=roofs(square(1, 1, 8), square(21, 1, 8)),
    )
    row = gdf.set_index("loc_id").loc["F_1_1"]
    assert row.sqft == pytest.approx(64 * siting.SQFT_PER_SQM * 1, abs=0.5)


def test_the_siting_result_reaches_the_output():
    """A 4 m roof in a 10 m parcel has 3 m either side: under ten feet, so no
    wall clears and the parcel is screened out, stated as a finding."""
    row = only(build_parcels(
        assess(record()), taxpar("F_100000_900000"),
        town_id=WORCESTER_TOWN_ID, structures=roofs(square(3, 3, 4)),
    ))
    assert row.siting == "screened_out"
    assert row.wall_run_ft == 0.0
    # None from the screen may surface as NaN after the map onto parcels
    assert row.wall_segment is None or pd.isna(row.wall_segment)


def test_worcester_grades_roofprints_and_screens_every_parcel(worcester_parcels):
    gdf = worcester_parcels
    assert gdf.attrs["roofprints_graded"] is True
    assert gdf.attrs["fallback_floor_area"] == 0  # every mapped parcel has an area
    assert gdf["siting"].notna().all()
    assert set(gdf["siting"]) <= set(siting.SITING_STATUSES)
    assert int((gdf["siting"] == "no_geometry").sum()) == 1
    assert int((gdf["roofprint_count"] == 1).sum()) == 1541
    assert dict(gdf["confidence"].value_counts()) == {"MED": 905, "HIGH": 605, "LOW": 589}
```

- [ ] **Step 2: Point the session fixture at the structures layer**

In `tests/conftest.py`, replace the body of `worcester_parcels`:

```python
@pytest.fixture(scope="session")
def worcester_parcels():
    if not HAS_WORCESTER:
        pytest.skip("Worcester L3 extract not present (data/raw is gitignored)")
    if not HAS_STRUCTURES:
        pytest.skip(
            "Worcester STRUCTURES_POLY not present (data/raw is gitignored); "
            "run scripts/fetch_structures.py --town-id 348"
        )
    from shave import crosswalk, ingest

    # test_crosswalk loads temporary tables through the same lru_cache. Its
    # autouse fixture clears either side, but a session fixture must not
    # depend on test order to get the committed crosswalk.
    crosswalk.load.cache_clear()
    return ingest.load_municipality(
        str(WORCESTER_DIR), town_id=WORCESTER_TOWN_ID, structures_path=STRUCTURES_PATH
    )
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_ingest.py`
Expected: FAIL — `ImportError: cannot import name 'FALLBACK_REASON' from 'shave.ingest'`

- [ ] **Step 4: Add `DEFAULT_STORIES` to `assumptions.py`**

Directly after `MIN_WALL_RUN_FT = 13.1`, add:

```python

# Stories assumed when the assessor records none, for the roofprint floor-area
# fallback only. One story understates a taller building, which is the safe
# direction: floor area is the whole scale factor.
DEFAULT_STORIES = 1.0
```

In `PUBLISHED`, directly after the `min_wall_run` entry, add:

```python
    Assumption(
        "default_stories", DEFAULT_STORIES, "stories", "ASSUMED",
        "roofprint floor-area fallback",
        "Used only when the assessor records neither a floor area nor a story "
        "count. One story understates a taller building, the safe direction "
        "for a scale factor.",
    ),
```

- [ ] **Step 5: Wire roofprints into `ingest.py`**

**Imports.** Replace the line `from .assumptions import LIKELY_SINGLE_METERED_MAX_SQFT` with:

```python
from . import siting
from .assumptions import DEFAULT_STORIES, LIKELY_SINGLE_METERED_MAX_SQFT
```

**Predicates.** Replace from `# The six HIGH-confidence predicates` through `COARSE_REASON = "coarse_use_code"` with:

```python
# The seven HIGH-confidence predicates, in report order. A parcel is HIGH only
# if all graded predicates hold. Names are returned verbatim in
# `confidence_reasons` so the UI can say which one failed rather than showing a
# bare chip. `single_roofprint` is graded only when a structures layer is
# supplied; `gdf.attrs["roofprints_graded"]` records whether it was.
PREDICATES: tuple[str, ...] = (
    "unique_archetype",          # the use code maps 1:1 to one archetype
    "has_floor_area",            # BLD_AREA present and non-zero, as the assessor recorded it
    "single_record",             # exactly one Assess record at this LOC_ID
    "single_owner",              # one owner of record
    "within_single_meter_cap",   # floor area <= LIKELY_SINGLE_METERED_MAX_SQFT
    "single_meter_archetype",    # the use code is not definitionally multi-tenant
    "single_roofprint",          # exactly one roofprint on the parcel
)

# Not a predicate: a hard floor. The crosswalk marks 4000 and 4010 as COLLAPSE
# POINTs — every manufacturer in the state carries 4000, and cold storage hides
# inside 4010 — so those parcels are capped at LOW however well they score on
# the other predicates.
COARSE_REASON = "coarse_use_code"

# Also a hard floor, from the spec's step 2: a floor area estimated from the
# roofprint rather than recorded by the assessor drops the parcel to LOW.
FALLBACK_REASON = "floor_area_from_roofprint"
```

**Output columns.** Replace `OUTPUT_COLUMNS` with:

```python
OUTPUT_COLUMNS: tuple[str, ...] = (
    "loc_id", "prop_id", "use_code", "use_desc", "archetype", "source",
    "icp_sector", "sqft", "sqft_source", "stories", "year_built", "owner",
    "site_addr", "city", "zip", "zoning", "assess_fy", "record_count",
    "owner_count", "confidence", "confidence_reasons", "multi_use", "multi_meter",
    "roofprint_count", "roofprint_sqft", "wall_run_ft", "wall_bearing_deg",
    "siting", "wall_segment", "geometry",
)
```

**Signature.** Replace the `build_parcels` signature with:

```python
def build_parcels(
    assess: pd.DataFrame,
    taxpar: gpd.GeoDataFrame | None = None,
    *,
    town_id: int | str | None = None,
    assess_fy_hint: int | None = None,
    structures: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
```

**Remove the early grading.** Delete these lines, which sit directly before `# --- assessor vintage`:

```python
    # Office band needs the *collapsed* area, which is why it is resolved here
    # and not in `_crosswalk_frame`.
    parcels["archetype"] = _resolve_office_bands(
        parcels["archetype"].astype("string"), parcels["sqft"]
    )

    parcels = _apply_confidence(parcels)

```

**Grade after the geometry join.** Replace:

```python
    else:
        parcels["geometry"] = None
```

with:

```python
    else:
        parcels["geometry"] = None

    # --- roofprints, the floor-area fallback, office band, grading ---------
    # All of these follow the geometry join because roofprints are assigned
    # by polygon. The office band needs the FINAL floor area and the fallback
    # can supply one, so the band is resolved after it; grading comes last
    # because it reads both.
    parcels["assessor_sqft"] = pd.to_numeric(parcels["sqft"], errors="coerce")
    roofprints_graded = structures is not None and crs is not None
    n_fallback = 0
    if roofprints_graded:
        # A parcel with no polygon arrives from the merge as NaN, not None;
        # normalise it so the GeoSeries sees a missing geometry, not a float.
        polygons = [g if getattr(g, "geom_type", None) else None for g in parcels["geometry"]]
        mapped = gpd.GeoDataFrame(
            {"loc_id": parcels["LOC_ID"].astype(str).to_numpy()},
            geometry=gpd.GeoSeries(polygons, crs=crs),
            crs=crs,
        )
        sited = siting.screen(mapped, structures).set_index("loc_id")
        for column in siting.SCREEN_COLUMNS[1:]:
            parcels[column] = parcels["LOC_ID"].astype(str).map(sited[column]).to_numpy()
        stories = (
            pd.to_numeric(parcels["STORIES"], errors="coerce")
            if "STORIES" in parcels else pd.Series(np.nan, index=parcels.index)
        )
        stories = stories.where(stories > 0, DEFAULT_STORIES)
        area = parcels["assessor_sqft"]
        roof_area = pd.to_numeric(parcels["roofprint_sqft"], errors="coerce").fillna(0.0)
        use_roof = (area.isna() | area.le(0)) & roof_area.gt(0)
        parcels["sqft"] = area.where(~use_roof, roof_area * stories)
        parcels["sqft_source"] = np.where(use_roof, "roofprint", "assessor")
        n_fallback = int(use_roof.sum())
    else:
        for column in siting.SCREEN_COLUMNS[1:]:
            parcels[column] = None
        parcels["sqft_source"] = "assessor"

    parcels["archetype"] = _resolve_office_bands(
        parcels["archetype"].astype("string"), parcels["sqft"]
    )
    parcels = _apply_confidence(parcels, roofprints_graded=roofprints_graded)
```

**Final schema.** In the `out = pd.DataFrame({...})` dictionary, add after the `"sqft": …` entry:

```python
            "sqft_source": parcels["sqft_source"].astype("string"),
```

and add directly before `"geometry": parcels["geometry"],`:

```python
            "roofprint_count": pd.to_numeric(parcels["roofprint_count"], errors="coerce").astype("Int64"),
            "roofprint_sqft": pd.to_numeric(parcels["roofprint_sqft"], errors="coerce").astype("Float64"),
            "wall_run_ft": pd.to_numeric(parcels["wall_run_ft"], errors="coerce").astype("Float64"),
            "wall_bearing_deg": pd.to_numeric(parcels["wall_bearing_deg"], errors="coerce").astype("Int64"),
            "siting": parcels["siting"].astype("string"),
            "wall_segment": parcels["wall_segment"],
```

In the `gdf.attrs.update({...})` call inside `build_parcels`, add:

```python
            "roofprints_graded": roofprints_graded,
            "fallback_floor_area": n_fallback,
```

**Grading.** Replace the whole of `_apply_confidence` with:

```python
def _apply_confidence(parcels: pd.DataFrame, roofprints_graded: bool = False) -> pd.DataFrame:
    """HIGH/MED/LOW plus the names of the predicates that failed.

    HIGH is every graded predicate. MED is exactly one failure. LOW is two or
    more, a coarse 400-series code, or a floor area estimated from the
    roofprint -- regardless of the rest. The failing names are carried out so
    the ranked view can say *why* a row is not HIGH.

    `has_floor_area` reads the assessor's own figure, so a parcel rescued by
    the roofprint fallback still says the assessor recorded nothing.
    """
    sqft = pd.to_numeric(parcels["sqft"], errors="coerce")
    assessor = pd.to_numeric(
        parcels["assessor_sqft"] if "assessor_sqft" in parcels else parcels["sqft"],
        errors="coerce",
    )
    # Read defensively: existing tests build parcel frames without these
    # columns, and a missing column is a KeyError where a missing value is not.
    multi_meter = (
        parcels["multi_meter"] if "multi_meter" in parcels
        else pd.Series(False, index=parcels.index)
    ).fillna(False).astype(bool)
    roof_count = pd.to_numeric(
        parcels["roofprint_count"] if "roofprint_count" in parcels
        else pd.Series(np.nan, index=parcels.index),
        errors="coerce",
    )
    graded = [p for p in PREDICATES if roofprints_graded or p != "single_roofprint"]
    holds = pd.DataFrame(
        {
            "unique_archetype": parcels["unique_archetype"].fillna(False).astype(bool),
            "has_floor_area": (assessor.notna() & assessor.gt(0)).to_numpy(),
            "single_record": parcels["record_count"].fillna(1).eq(1).to_numpy(),
            "single_owner": parcels["owner_count"].fillna(1).eq(1).to_numpy(),
            "within_single_meter_cap": sqft.fillna(0.0)
            .le(LIKELY_SINGLE_METERED_MAX_SQFT)
            .to_numpy(),
            "single_meter_archetype": ~multi_meter.to_numpy(),
            "single_roofprint": roof_count.eq(1).to_numpy(),
        },
        index=parcels.index,
    )[graded]

    coarse = parcels["collapse_point"].fillna(False).astype(bool).to_numpy()
    fallback = (
        parcels["sqft_source"].eq("roofprint").to_numpy()
        if "sqft_source" in parcels else np.zeros(len(parcels), dtype=bool)
    )
    failures = ~holds.to_numpy(dtype=bool)
    n_failed = failures.sum(axis=1)

    confidence = np.where(
        coarse | fallback | (n_failed >= 2), "LOW",
        np.where(n_failed == 1, "MED", "HIGH"),
    )

    # A comprehension over output parcels (~2.1k for Worcester), not over the
    # 47,675 input records. The 47k-row work above is all vectorised.
    all_names = graded + [COARSE_REASON, FALLBACK_REASON]
    flagged = np.column_stack([failures, coarse[:, None], fallback[:, None]])
    reasons = [
        tuple(name for name, bad in zip(all_names, row) if bad) for row in flagged
    ]

    parcels = parcels.copy()
    parcels["confidence"] = confidence
    parcels["confidence_reasons"] = pd.Series(reasons, index=parcels.index, dtype=object)
    return parcels
```

**Entry point.** In `load_municipality`, change the signature to:

```python
def load_municipality(
    dir_path: str | Path, town_id: int | str, structures_path: str | Path | None = None
) -> gpd.GeoDataFrame:
```

Add to its docstring, after the sentence ending "grades confidence.":

```
    With `structures_path`, it also joins the MassGIS STRUCTURES_POLY layer:
    roofprint counts feed the `single_roofprint` predicate, roofprint area
    fills a missing floor area, and every parcel gets a siting screen result.
```

Replace:

```python
    gdf = build_parcels(
        assess,
        taxpar,
        town_id=tid,
        assess_fy_hint=_fy_from_filename(assess_path, taxpar_path),
    )
```

with:

```python
    structures = (
        siting.load_structures(structures_path) if structures_path is not None else None
    )
    gdf = build_parcels(
        assess,
        taxpar,
        town_id=tid,
        assess_fy_hint=_fy_from_filename(assess_path, taxpar_path),
        structures=structures,
    )
```

and add to its `gdf.attrs.update({...})`:

```python
            "structures_path": None if structures_path is None else str(structures_path),
```

- [ ] **Step 6: Run the ingest tests**

Run: `uv run pytest tests/test_ingest.py tests/test_siting.py`
Expected: PASS. That is 8 new ingest tests, and every existing ingest test unchanged, because synthetic frames without structures grade six predicates exactly as before.

- [ ] **Step 7: Run everything**

Run: `uv run pytest`
Expected: **1010 passed, 4 deselected** (1002 + 8). The session fixture now screens Worcester, so expect the one setup to take about 5 s longer. If `test_shared_fixtures.py` fails, the new `wall_segment` column is the likely cause, and the fix is in the consumer, not the guard.

- [ ] **Step 8: Commit**

```bash
git add src/shave/ingest.py src/shave/assumptions.py tests/test_ingest.py tests/conftest.py
git commit -m "feat: roofprints feed confidence and floor area

The spec's HIGH tier requires exactly one roofprint on the parcel; that is now
the seventh predicate. A parcel with none usually has its building mapped
mostly on a neighbouring lot, and a parcel with several is often several
meters -- the parcel-is-not-the-account problem the tier exists to flag.

Measured on Worcester, exported rows move HIGH 121 -> 87, MED 221 -> 177,
LOW 221 -> 299. Confidence does not feed the score, so no rank, dollar figure
or R-squared changes.

A missing floor area now falls back to roofprint area times recorded stories
(one when none is recorded) and drops the parcel to LOW, per the spec's step 2.
No Worcester parcel with a polygon needs it today; the test pins that at zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 3: Carry the result and draw the wall at build time

**Files:**
- Modify: `src/shave/mapgeo.py` (`_grown` lines 109–125; append functions)
- Modify: `src/shave/export.py` (`SCHEMA_VERSION`, `PARCEL_FIELDS`)
- Modify: `src/shave/site_data.py`
- Modify: `scripts/build_site.py`
- Modify: `docs/ranked-json-schema.md`
- Test: `tests/test_mapgeo.py`, `tests/test_site_data.py`

**Interfaces:**
- Consumes: `worcester_parcels`, now carrying the siting columns (Task 2).
- Produces:
  - `mapgeo.wall_path_for(parcel_4326, segment_4326, frame, min_span=MIN_SPAN_UNITS) -> str`, an open `M…L…` path, or `""`
  - `mapgeo.walls_for(gdf, frame) -> dict[str, str]`, keyed by `loc_id`
  - `site_data.compass(bearing_deg) -> str`, an 8-point label such as "SW", or `""` for None
  - `site_data.enrich(export_payload, scored, paths=None, view_box=None, walls=None)`
  - every enriched row gains `wall` (path string, empty when none) and `wall_facing`
  - payload gains `siting_rule: {"clearance_ft": float, "min_wall_run_ft": float}`
  - exported rows gain `sqft_source`, `roofprint_count`, `wall_run_ft`, `wall_bearing_deg`, `siting`
  - `export.SCHEMA_VERSION == "1.5.0"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mapgeo.py`:

```python
# --- the wall run, drawn with its parcel -----------------------------------

import geopandas as gpd
from shapely.geometry import LineString
from shapely.geometry import box as _box


def _wall_frame():
    return mapgeo.MapFrame(
        min_lon=-71.9, min_lat=42.2, max_lon=-71.7, max_lat=42.4,
        width=620.0, height=818.0,
    )


def test_a_wall_on_a_large_parcel_is_drawn_where_it_is():
    frame = _wall_frame()
    parcel = _box(-71.85, 42.25, -71.75, 42.35)  # far above the minimum span
    wall = LineString([(-71.84, 42.26), (-71.80, 42.26)])

    d = mapgeo.wall_path_for(parcel, wall, frame)

    x1, y1 = mapgeo.project(-71.84, 42.26, frame)
    x2, y2 = mapgeo.project(-71.80, 42.26, frame)
    assert d == f"M{round(x1, 1)},{round(y1, 1)}L{round(x2, 1)},{round(y2, 1)}"
    assert "Z" not in d, "a wall is an open segment, not a closed shape"


def test_a_wall_on_a_grown_parcel_grows_with_it():
    """Small parcels are drawn larger about their own centre. A wall drawn at
    its true position would float off the enlarged building."""
    frame = _wall_frame()
    # a few metres wide and far shorter than it is wide, so the wall along its
    # base spans the parcel's largest dimension and grows to the full minimum
    parcel = _box(-71.80001, 42.300000, -71.79999, 42.300001)
    wall = LineString([(-71.80001, 42.300000), (-71.79999, 42.300000)])

    d = mapgeo.wall_path_for(parcel, wall, frame)
    coords = [tuple(map(float, p.split(","))) for p in d[1:].split("L")]
    drawn_span = abs(coords[1][0] - coords[0][0])

    assert drawn_span == pytest.approx(mapgeo.MIN_SPAN_UNITS, rel=0.05)


def test_walls_for_skips_parcels_with_no_run():
    gdf = gpd.GeoDataFrame(
        {
            "loc_id": ["A", "B"],
            "wall_segment": [LineString([(10, 20), (40, 20)]), None],
        },
        geometry=[_box(0, 0, 50, 50), _box(100, 0, 150, 50)],
        crs="EPSG:26986",
    )
    frame = mapgeo.frame_for(gdf)

    walls = mapgeo.walls_for(gdf, frame)

    assert set(walls) == {"A"}
    assert walls["A"].startswith("M")
```

Append to `tests/test_site_data.py`:

```python
def test_compass_labels_a_bearing_with_eight_points():
    assert site_data.compass(0) == "N"
    assert site_data.compass(228) == "SW"
    assert site_data.compass(100) == "E"
    assert site_data.compass(338) == "N"
    assert site_data.compass(None) == ""


def test_the_payload_carries_the_siting_rule_and_each_row_its_wall():
    from shave.assumptions import MIN_WALL_CLEARANCE_FT, MIN_WALL_RUN_FT

    payload = {"schema_version": "1.5.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12, "wall_bearing_deg": 228}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub(), walls={"L1": "M1,2L3,4"})

    row = out["lists"]["comstock"][0]
    assert row["wall"] == "M1,2L3,4"
    assert row["wall_facing"] == "SW"
    assert out["siting_rule"] == {
        "clearance_ft": MIN_WALL_CLEARANCE_FT, "min_wall_run_ft": MIN_WALL_RUN_FT,
    }


def test_every_exported_row_carries_its_siting_result(worcester_parcels, worcester_scored):
    from shave import export, mapgeo, siting

    frame = mapgeo.frame_for(worcester_parcels)
    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored, walls=mapgeo.walls_for(worcester_parcels, frame))

    rows = {r["loc_id"]: r for l in enriched["lists"].values() for r in l}
    for row in rows.values():
        assert row["siting"] in siting.SITING_STATUSES, row["loc_id"]
        if row["wall_run_ft"]:
            assert row["wall"].startswith("M"), row["loc_id"]
    walmart = rows["F_577265_2910122"]
    assert walmart["siting"] == "clear"
    assert walmart["wall_bearing_deg"] == 228
    assert walmart["wall_facing"] == "SW"
    screened = [r for r in rows.values() if r["siting"] == "screened_out"]
    assert 1 <= len(screened) <= 20
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_mapgeo.py tests/test_site_data.py`
Expected: FAIL — `AttributeError: module 'shave.mapgeo' has no attribute 'wall_path_for'`, and the same for `compass`.

- [ ] **Step 3: Share the growth transform in `mapgeo.py`**

Replace the whole of `_grown` with:

```python
def _growth(points: list[tuple[float, float]], min_span: float) -> tuple[float, float, float]:
    """The centre and scale that grow a projected ring up to `min_span`.

    Scale is 1.0 when the ring is already large enough. Split out from
    `_grown` so a wall on the parcel can use exactly the same transform.
    """
    if min_span <= 0 or not points:
        return 0.0, 0.0, 1.0
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span >= min_span or span <= 0:
        return 0.0, 0.0, 1.0
    return (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0, min_span / span


def _grown(points: list[tuple[float, float]], min_span: float) -> list[tuple[float, float]]:
    """Scale a projected ring about its own centre up to `min_span`.

    Position is preserved exactly -- a parcel moved to make it visible would
    be a lie about where it is. Only its drawn size changes.
    """
    cx, cy, scale = _growth(points, min_span)
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points]
```

Append to the end of `mapgeo.py`:

```python
def wall_path_for(parcel, segment, frame: MapFrame, min_span: float = MIN_SPAN_UNITS) -> str:
    """The clear wall run as an open SVG path, in the parcel's drawn space.

    Both arguments are EPSG:4326. The parcel is simplified exactly as
    `path_for` simplifies it, and the wall takes the growth of whichever part
    of the parcel it lies on, so a small parcel's wall stays on its building.
    """
    if parcel is None or segment is None or parcel.is_empty or segment.is_empty:
        return ""
    simple = parcel.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
    if simple.is_empty:
        simple = parcel
    parts = [simple] if simple.geom_type == "Polygon" else list(getattr(simple, "geoms", []))
    if not parts:
        return ""
    middle = segment.interpolate(0.5, normalized=True)
    part = min(parts, key=lambda p: p.distance(middle))
    ring = [project(lon, lat, frame) for lon, lat in part.exterior.coords]
    cx, cy, scale = _growth(ring, min_span)
    points = []
    for lon, lat in segment.coords:
        x, y = project(lon, lat, frame)
        gx, gy = cx + (x - cx) * scale, cy + (y - cy) * scale
        points.append(f"{round(gx, COORD_DECIMALS)},{round(gy, COORD_DECIMALS)}")
    return "M" + points[0] + "".join("L" + p for p in points[1:])


def walls_for(gdf, frame: MapFrame) -> dict[str, str]:
    """`loc_id` to wall path, for every parcel whose siting screen found a run."""
    if "wall_segment" not in gdf.columns:
        return {}
    has = gdf[gdf["wall_segment"].notna() & gdf.geometry.notna()]
    if has.empty:
        return {}
    import geopandas as gpd  # local: mapgeo otherwise needs only shapely objects

    parcels = has.geometry.to_crs(4326)
    segments = gpd.GeoSeries(list(has["wall_segment"]), crs=has.crs).to_crs(4326)
    out: dict[str, str] = {}
    for loc_id, parcel, segment in zip(has["loc_id"], parcels, segments):
        d = wall_path_for(parcel, segment, frame)
        if d:
            out[str(loc_id)] = d
    return out
```

- [ ] **Step 4: Carry the fields through the export and site data**

In `src/shave/export.py`, set `SCHEMA_VERSION = "1.5.0"` and replace `PARCEL_FIELDS` with:

```python
PARCEL_FIELDS = (
    "prop_id", "site_addr", "city", "zip", "owner", "use_code", "use_desc",
    "icp_sector", "assess_fy", "confidence", "confidence_reasons",
    "sqft_source", "roofprint_count", "wall_run_ft", "wall_bearing_deg", "siting",
    "lon", "lat",
)
```

In `src/shave/site_data.py`:

Add to the imports:

```python
from shave.assumptions import MIN_WALL_CLEARANCE_FT, MIN_WALL_RUN_FT
```

In `ADDED_ROW_FIELDS`, add `"wall", "wall_facing",` after `"day_offpeak",`.

In `REQUIRED_ROW_FIELDS`, add `"siting", "wall_run_ft", "wall_bearing_deg", "roofprint_count", "sqft_source",` after `"peak_day_held_kw",`.

Add below `day_profile`:

```python
_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def compass(bearing_deg) -> str:
    """An eight-point label for a bearing, so the page names a direction
    without doing arithmetic on it. "" when there is no bearing."""
    if bearing_deg is None:
        return ""
    return _COMPASS[int(round(float(bearing_deg) / 45.0)) % 8]
```

Change the `enrich` signature to:

```python
def enrich(
    export_payload: dict,
    scored: pd.DataFrame,
    paths: dict[str, str] | None = None,
    view_box: str | None = None,
    walls: dict[str, str] | None = None,
) -> dict:
```

Directly after `row.update(day_profile(row))`, add:

```python
            # Empty string, as with `path`: most rows have a wall run, and the
            # page checks truthiness once.
            row["wall"] = (walls or {}).get(row["loc_id"], "")
            row["wall_facing"] = compass(row.get("wall_bearing_deg"))
```

Directly after the `payload["day_axis"] = {…}` block, add:

```python
    # The screen's own thresholds, so the page never restates ten feet.
    payload["siting_rule"] = {
        "clearance_ft": MIN_WALL_CLEARANCE_FT,
        "min_wall_run_ft": MIN_WALL_RUN_FT,
    }
```

- [ ] **Step 5: Build with the structures layer**

In `scripts/build_site.py`:

Change the import to:

```python
from shave import addresses, export, ingest, mapgeo, pipeline, regression, siting, site_data
```

Replace `    parcels = ingest.load_municipality(args.dir, town_id=args.town_id)` with:

```python
    parcels = ingest.load_municipality(
        args.dir, town_id=args.town_id,
        structures_path=siting.structures_path(args.town_id),
    )
```

Replace:

```python
    enriched = site_data.enrich(
        raw, scored, paths=mapgeo.paths_for(parcels, frame), view_box=frame.view_box
    )
```

with:

```python
    enriched = site_data.enrich(
        raw, scored,
        paths=mapgeo.paths_for(parcels, frame),
        view_box=frame.view_box,
        walls=mapgeo.walls_for(parcels, frame),
    )
```

In `docs/ranked-json-schema.md`, change `**Current version: \`1.4.0\`**` to `1.5.0` and add after the `**1.4.0**` paragraph:

```markdown
**1.5.0** — rows gain the siting screen: `siting` (string, one of `clear`,
`screened_out`, `no_roofprint`, `no_geometry`), `wall_run_ft` (float or null,
the longest wall with the published clearance to the parcel line),
`wall_bearing_deg` (int or null, the direction that wall faces, clockwise from
grid north), `roofprint_count` (int) and `sqft_source` (`assessor` or
`roofprint`). The site payload adds `wall` (an open SVG path in `map.view_box`
space, empty when there is no run) and `wall_facing` (an eight-point compass
label) on each row, and a top-level `siting_rule` object
`{clearance_ft, min_wall_run_ft}`. `clear` means only "not screened out".
MINOR: nothing was removed or retyped.
```

- [ ] **Step 6: Run everything and rebuild**

```bash
uv run pytest
uv run python scripts/build_site.py
uv run python -c "
import json, gzip, collections
b = open('public/data/ranked.json','rb').read(); d = json.loads(b)
rows = [r for l in d['lists'].values() for r in l]
print('schema', d['schema_version'], '| rule', d['siting_rule'])
print(dict(collections.Counter(r['siting'] for r in rows)))
print('rows with a wall path', sum(1 for r in rows if r['wall']))
print('confidence', dict(collections.Counter(r['confidence'] for r in rows)))
print('raw KB', len(b)//1024, '| gzip KB', len(gzip.compress(b))//1024)
"
```

**Pass conditions, declared in advance:**
- **1016 passed, 4 deselected** (1010 + 3 mapgeo + 3 site_data);
- schema `1.5.0`;
- exported confidence `{'HIGH': 87, 'MED': 177, 'LOW': 299}`;
- every row whose `wall_run_ft` is greater than 0 has a wall path;
- `ranked.json` under **1,600 KB raw** and **300 KB gzipped**.

Report the status counts.

- [ ] **Step 7: Commit**

```bash
git add src/shave/mapgeo.py src/shave/export.py src/shave/site_data.py scripts/build_site.py \
        docs/ranked-json-schema.md tests/test_mapgeo.py tests/test_site_data.py
git commit -m "feat: carry the siting result and draw the wall at build time

Rows gain the screen's continuous result -- wall run, bearing, status,
roofprint count, where the floor area came from -- and the site payload adds
the wall as an SVG segment plus an eight-point facing label, so the page
names a direction without computing one. The clearance and required run
travel as siting_rule.

A wall on a small parcel takes that parcel's growth about its centre, so it
stays on the enlarged building instead of floating beside it.

Schema 1.5.0, MINOR.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 4: The drawer states it; the map marks it

**Files:**
- Modify: `public/app.js`
- Modify: `public/index.html` (map legend)
- Modify: `public/app.css`
- Test: `web/render.test.js`

**Interfaces:**
- Consumes: row fields `siting`, `wall_run_ft`, `wall_bearing_deg`, `wall_facing`, `wall`; payload `siting_rule` (Task 3).
- Produces:
  - `export function sitingText(row, rule) -> string`
  - `export function wallHTML(row) -> string`
  - `drawerHTML(row, flagMeanings, dayAxis, sitingRule)`, gaining a fourth parameter
  - `mapSVG` draws a `<g id="walls">` layer; `select(id)` shows only the selected parcel's wall

- [ ] **Step 1: Write the failing tests**

Append to `web/render.test.js`:

```js
import { sitingText, wallHTML } from "../public/app.js";

const RULE = { clearance_ft: 10, min_wall_run_ft: 13.1 };

describe("sitingText", () => {
  it("states a clear run with its direction and says it is not a green light", () => {
    const text = sitingText(
      { siting: "clear", wall_run_ft: 288.7, wall_bearing_deg: 228, wall_facing: "SW" }, RULE,
    );
    expect(text).toContain("289 ft");
    expect(text).toContain("SW");
    expect(text).toContain("228°");
    expect(text).toContain("10 ft");
    expect(text).toMatch(/not a green light/i);
  });

  it("states a screen-out as a finding, with the threshold it failed", () => {
    const text = sitingText({ siting: "screened_out", wall_run_ft: 0 }, RULE);
    expect(text).toMatch(/^Screened out/);
    expect(text).toContain("0 ft");
    expect(text).toContain("13.1 ft");
  });

  it("says a parcel with no roofprint was not assessed, and why", () => {
    const text = sitingText({ siting: "no_roofprint", wall_run_ft: null }, RULE);
    expect(text).toMatch(/^Not assessed/);
    expect(text).toMatch(/neighbouring/);
  });

  it("never prints undefined or NaN for a row without a result", () => {
    const text = sitingText({}, undefined);
    expect(text).toMatch(/^Not assessed/);
    expect(text).not.toMatch(/undefined|NaN/);
  });
});

describe("wallHTML", () => {
  it("draws a hidden, unclickable mark only when the row has a wall", () => {
    const html = wallHTML({ loc_id: "A", wall: "M1,2L3,4" });
    expect(html).toContain('class="wall"');
    expect(html).toContain('data-id="A"');
    expect(html).toContain('pointer-events="none"');
    expect(html).not.toContain("var(--signal)");
    expect(wallHTML({ loc_id: "B", wall: "" })).toBe("");
  });

  it("escapes the path it was handed", () => {
    expect(wallHTML({ loc_id: "A", wall: '"><script>' })).not.toContain("<script>");
  });
});

describe("drawerHTML siting", () => {
  it("carries the siting sentence", () => {
    const html = drawerHTML(
      { ...ROW, siting: "screened_out", wall_run_ft: 0 }, {}, undefined, RULE,
    );
    expect(html).toContain("<dt>Siting</dt>");
    expect(html).toContain("Screened out");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `sitingText is not a function`.

- [ ] **Step 3: Add the renderers to `public/app.js`**

Insert directly before `export function drawerHTML(`:

```js
// The siting screen is a screen-out, never a green light. Every number here was
// computed by the build; the page only chooses which sentence to show.
export function sitingText(row, rule) {
  const r = rule || {};
  const run = Math.round(Number(row && row.wall_run_ft) || 0);
  const clearance = r.clearance_ft != null ? `${r.clearance_ft} ft` : "the required";
  if (row && row.siting === "clear") {
    return (
      `Longest wall with ${clearance} of parcel-side clearance: ${run} ft, facing ` +
      `${row.wall_facing} (${row.wall_bearing_deg}°). Not a green light: the screen ` +
      `cannot see loading docks, fire lanes, egress or where the service entrance is.`
    );
  }
  if (row && row.siting === "screened_out") {
    return (
      `Screened out: the longest wall with ${clearance} of clearance to the parcel ` +
      `line runs ${run} ft, under the ${r.min_wall_run_ft} ft two cabinets need. ` +
      `Stated as a finding.`
    );
  }
  if (row && row.siting === "no_roofprint") {
    return (
      `Not assessed: no roofprint sits on this parcel. The building's roof is mapped ` +
      `mostly on a neighbouring lot, so its walls cannot be attributed here.`
    );
  }
  return `Not assessed: there is no parcel polygon to measure against.`;
}

// Hatched in ink, never the accent. Hidden until its parcel is selected: at town
// scale a median wall is two or three units long, and 172 of them at once are noise.
export function wallHTML(row) {
  if (!row || !row.wall) return "";
  return (
    `<path class="wall" data-id="${esc(row.loc_id)}" d="${esc(row.wall)}" fill="none" ` +
    `stroke="var(--ink)" stroke-width="2.4" stroke-dasharray="1.2 0.8" ` +
    `stroke-linecap="butt" pointer-events="none"/>`
  );
}
```

In `drawerHTML`, change the signature to `export function drawerHTML(row, flagMeanings, dayAxis, sitingRule) {`. Directly after the Confidence entry:

```js
    `<div><dt>Confidence</dt><dd><span class="chip ${chipClass(row.confidence)}">` +
    `${esc(row.confidence)}</span>${failed ? " failed: " + esc(failed) : ""}</dd></div>` +
```

add:

```js
    `<div><dt>Siting</dt><dd>${esc(sitingText(row, sitingRule))}</dd></div>` +
```

In `mapSVG`, replace the final return's parcels group:

```js
    `<g id="parcels">${drawn.map((r) => parcelHTML(r, maxSaving)).join("")}</g>` +
```

with:

```js
    `<g id="parcels">${drawn.map((r) => parcelHTML(r, maxSaving)).join("")}</g>` +
    `<g id="walls">${drawn.map(wallHTML).join("")}</g>` +
```

In the `state` object literal, add `sitingRule: null,` after `dayAxis: null,`.

In `boot()`, after `state.dayAxis = ranked.day_axis || null;`, add:

```js
  state.sitingRule = ranked.siting_rule || null;
```

In `select(id)`, change the drawer line to:

```js
  $("#drawer").innerHTML = drawerHTML(
    row, (state.method || {}).flag_meanings, state.dayAxis, state.sitingRule,
  );
```

and directly after the `$$("#map .parcel").forEach(…)` block, add:

```js
  $$("#map .wall").forEach((w) => w.classList.toggle("on", w.dataset.id === id));
```

- [ ] **Step 4: Legend and styles**

In `public/index.html`, directly after the line `<span><i class="sw-g3"></i>Rate G&#8209;3 &middot; $10.48/kW</span>`, add:

```html
          <span><i class="sw-wall"></i>Clear wall run, selected site</span>
```

Append to `public/app.css`:

```css
/* ---------- wall run ---------- */
/* Shown for the selected parcel only. Ink, not the accent: --signal is spent. */
.wall{visibility:hidden}
.wall.on{visibility:visible}
.legend .sw-wall{height:3px; vertical-align:3px; border-radius:0;
  background:repeating-linear-gradient(90deg, var(--ink) 0 2px, transparent 2px 4px)}
```

- [ ] **Step 5: Run both suites**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
uv run pytest
```
Expected: render **57 passed** (50 + 4 sitingText + 2 wallHTML + 1 drawer); Python **1016 passed, 4 deselected**.

- [ ] **Step 6: Check against the real payload, then look at it**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/node" --input-type=module -e '
import { readFileSync } from "node:fs";
const { sitingText, drawerHTML, mapSVG } = await import("/Users/pjay/powertown/public/app.js");
const d = JSON.parse(readFileSync("/Users/pjay/powertown/public/data/ranked.json", "utf8"));
const rows = Object.values(d.lists).flat();
let bad = 0;
for (const r of rows) if (/undefined|NaN/.test(sitingText(r, d.siting_rule))) bad++;
console.log("rows with undefined/NaN siting text:", bad);
console.log(sitingText(d.lists.comstock[0], d.siting_rule));
const svg = mapSVG(d.lists.comstock, d.map.view_box, 1);
console.log("wall paths in comstock map:", (svg.match(/class="wall"/g) || []).length);
'
"$NB/npx" wrangler dev --port 8787
```

**Pass conditions:**
- 0 rows with bad text;
- the ComStock rank 1 sentence reads *"…288 ft, facing SW (228°)…"* or *"…289 ft…"*;
- the wall path count equals the ComStock rows whose `wall` is non-empty.

At `http://127.0.0.1:8787/`, confirm by eye:
- rank 1's drawer shows the Siting line;
- a short hatched mark appears on its parcel and moves when another row is selected;
- no mark shows for unselected parcels;
- a screened-out row, found by filtering `ranked.json` for `"siting":"screened_out"`, reads as a finding;
- the legend has a wall entry.

If a browser is unavailable, say so in the report rather than skipping silently.

- [ ] **Step 7: Commit**

```bash
git add public/app.js public/index.html public/app.css web/render.test.js
git commit -m "feat: the drawer states the siting result; the map marks the wall

The drawer's Siting line gives the longest clear wall and the direction it
faces, and says plainly it is not a green light. A screen-out is stated as a
finding with the threshold it missed; a parcel whose building is mapped on a
neighbouring lot says it was not assessed and why.

The hatched wall is drawn for the selected parcel only, in ink. At town scale
a median wall is two or three SVG units, and 172 at once would be noise.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 5: Say what it cannot see, update the review, ship

**Files:**
- Modify: `src/shave/method.py` (`LIMITATIONS`, `KNOWN_GAPS`)
- Modify: `tests/test_method.py` (replace `test_the_method_page_says_what_the_map_cannot_show`)
- Modify: `docs/spec-coverage.md`
- Merge `feat/siting-screen` → `main`, deploy

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `LIMITATIONS` entry `siting_screens_out_only`
  - `KNOWN_GAPS` no longer contains `map_shows_no_siting`

- [ ] **Step 1: Replace the map-gap test**

In `tests/test_method.py`, replace the whole of `test_the_method_page_says_what_the_map_cannot_show` with:

```python
def test_the_method_page_says_what_the_siting_screen_cannot_see():
    """The spec: 'State on the method page what this cannot see.' The gap that
    said no screen had been run is retired now that one has."""
    gaps = {g.key for g in method.KNOWN_GAPS}
    assert "map_shows_no_siting" not in gaps
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "siting_screens_out_only" in stated, sorted(stated)
    text = stated["siting_screens_out_only"].lower()
    for blind_spot in ("loading dock", "fire lane", "egress", "setback", "service entrance"):
        assert blind_spot in text, blind_spot
    assert "not a green light" in text or "does not confirm" in text
```

Run: `uv run pytest tests/test_method.py -k siting_screen`
Expected: FAIL — `assert 'map_shows_no_siting' not in {...}`

- [ ] **Step 2: Retire the gap, state the limit**

In `src/shave/method.py`, delete the whole `Limitation("map_shows_no_siting", …)` entry from `KNOWN_GAPS`. Then add, as the last entry of `LIMITATIONS`:

```python
    Limitation(
        "siting_screens_out_only",
        "The siting screen screens out the impossible and does not confirm the "
        "possible. It measures the longest wall with ten feet of clearance to "
        "the parcel line on MassGIS roof outlines, which include overhangs. It "
        "cannot see loading docks, fire lanes, parking aisles, means of egress, "
        "wall openings, local zoning setbacks or where the service entrance is. "
        "A clear result is not a green light.",
    ),
```

Run: `uv run pytest tests/test_method.py`
Expected: PASS.

- [ ] **Step 3: Final full run**

```bash
uv run pytest
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: **1016 passed, 4 deselected** (the replaced test nets zero); **57 passed**.

- [ ] **Step 4: Update `docs/spec-coverage.md`**

Make these edits:
1. **Header table**
   - `Tests` → `**1016 Python** (4 network-marked, deselected) + **57 render**`.
   - `Coverage of spec stages` → `**8 of 12 numbered steps complete**, 1 partial, 1 blocked`. The previous header said 9 of 12, which overcounted; the complete steps are 1, 2, 3, 4, 5, 8, 9 and 10.
2. **Stage 1 heading** → `## Stage 1 — 7 of 9 complete, 1 partial, 1 blocked`.
3. **Stage 1 row 2** → state `✅`, notes `Missing floor area falls back to roofprint area × recorded stories (one when none is recorded) and drops to LOW with reason floor_area_from_roofprint. No Worcester parcel with a polygon needs it today; the test pins that at zero.`
4. **Stage 1 row 3** → state `✅`, notes `MassGIS STRUCTURES_POLY joined by representative point: 1,541 of 2,098 mapped parcels hold one roofprint, 370 several, 187 none. Feeds the single_roofprint predicate (exported HIGH 121 → 87) and the siting screen.`
5. **Stage 1 row 9 notes** → replace `The siting slot waits on step 3.` with `Siting line: longest clear wall and bearing, or a stated screen-out.`
6. **D2 row** → `✅ merged and live, with the hatched wall run on the selected parcel`.
7. **Test plan `siting` row** → `✅ zero-lot-line, footprint ≈ parcel, collinear merge, obstruction, straddling roof, real top-ranked sites (test_siting.py)`.
8. **Test plan heading** → `## The spec's test plan — 8 of 9 areas covered`.
9. **Pending table:** delete the `STRUCTURES_POLY + siting screen` row and renumber the rest 1–3.
10. **Deliberate divergences:** add at the end:

```markdown
**8. The wall run is drawn for the selected parcel only.** D2 lists a hatched wall segment
as a map channel. At 620 SVG units across Worcester one unit is about 17 m, so the median
exported clear run of 138 ft draws about 2.4 units long; hatching every parcel's wall at
once is noise, not a channel. The mark appears on the selected parcel, grown with it when
the parcel is drawn at its minimum size, and the legend says so.

**9. `clear` is named for what it is.** The spec asks for the continuous fact rather than a
boolean. The status field has four values — `clear`, `screened_out`, `no_roofprint`,
`no_geometry` — and `clear` is defined everywhere it appears as "not screened out", never
as suitable.
```

- [ ] **Step 5: Commit, merge, push, deploy**

```bash
git add src/shave/method.py tests/test_method.py docs/spec-coverage.md
git commit -m "docs: what the siting screen cannot see

Retires the gap that said no screen had been run and states the spec's own
list of blind spots: loading docks, fire lanes, parking aisles, egress, wall
openings, zoning setbacks and the service entrance. Coverage review: steps 2
and 3 complete, the siting test-plan row covered.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git checkout main
git pull --ff-only origin main
git merge --no-ff feat/siting-screen -m "merge: the siting screen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

If `git pull --ff-only` refuses, stop and report rather than merging over unseen commits.

- [ ] **Step 6: Verify live**

```bash
URL="https://shave.pjayav.workers.dev"
curl -s -o /dev/null -w 'index  %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/ranked.json"
curl -s "$URL/data/ranked.json" | uv run python -c "
import json, sys, collections
d = json.load(sys.stdin); rows = [r for l in d['lists'].values() for r in l]
print(d['schema_version'], d['siting_rule'], dict(collections.Counter(r['siting'] for r in rows)))"
curl -s "$URL/data/method.json" | grep -c siting_screens_out_only
curl -s "$URL/app.js" | grep -c "export function sitingText"
```

**Pass conditions, declared in advance:** both `200`; index plus `ranked.json` under **3 s** combined; schema `1.5.0` with `siting_rule`; the method grep prints `1`; `sitingText` present in the deployed script.

---

## What the next plans pick up

| Next | Carries | Est. |
|---|---|---|
| **New Bedford and Chicopee** | L3 download, crosswalk pass, `county_gisjoin` for Bristol and Hampden, and now `scripts/fetch_structures.py --town-id` for each. The roofprint fallback likely gets its first real cases there. `build_site.py` still takes one town per run. | 2.5h |
| **MECOLS class-shape check** | Criterion 4. Re-fetch the workbook first. | 1h + fetch |
| Occupant resolution, 46 remaining | Hand work; the ratchet rises as rows land. | 3h |

---

## Self-Review

**Spec coverage.**
- Step 3's join (roofprint count, footprint area, siting geometry) → Task 1 (`assign_roofprints`, `screen`) and Task 2 (columns on every parcel).
- The confidence tier's *"exactly one roofprint"* → Task 2 (`single_roofprint`).
- Step 2's fallback, *"roofprint area × estimated stories; drop to LOW"* → Task 2 (`FALLBACK_REASON`, `DEFAULT_STORIES`).
- The siting screen, requirement by requirement:
  - continuous output → `WallRun.run_ft` and `bearing_deg`;
  - simplify and merge collinear → `SIMPLIFY_M`;
  - offset outward and test containment → the cells;
  - longest passing run and bearing → `_longest_true_run`;
  - 10 ft sourced → the existing `MIN_WALL_CLEARANCE_FT`;
  - screens out and does not confirm → the `clear` naming, `sitingText`, and the Task 5 limitation, which carries the spec's full blind-spot list.
- The spec's `siting` test-plan row: zero-lot-line, footprint ≈ parcel and collinear merge are the first three tests in `test_siting.py`.
- D2's hatched wall segment → Tasks 3–4, drawn for the selected parcel with the divergence recorded.
- Interaction States, Site detail, Error → `sitingText`'s screen-out sentence.
- Map Partial, *"unsited parcels drawn without a wall run"* → `wallHTML` returns `""`.
- FEMA flood zones remain cut, as the spec says.

**Placeholder scan.** No TBD or "handle edge cases". Every code step carries its code, and every test step its test. Task 5 Step 4 gives exact replacement text for each coverage-doc cell.

**Type consistency.**
- `siting.SCREEN_COLUMNS` (Task 1) is iterated by `ingest.build_parcels` (Task 2) as `SCREEN_COLUMNS[1:]`. That produces `roofprint_count`, `roofprint_sqft`, `wall_run_ft`, `wall_bearing_deg`, `wall_segment` and `siting`, which are exactly the new `OUTPUT_COLUMNS` less `sqft_source`, which Task 2 adds itself.
- `wall_segment` (Task 2) is read by `mapgeo.walls_for` (Task 3).
- `export.PARCEL_FIELDS` (Task 3) lifts `sqft_source`, `roofprint_count`, `wall_run_ft`, `wall_bearing_deg` and `siting`. These are the fields `site_data.REQUIRED_ROW_FIELDS` adds, and the fields `sitingText` reads (Task 4) together with `wall_facing` and `wall`, which `enrich` adds.
- `siting_rule` keys `clearance_ft` and `min_wall_run_ft` match between `enrich` (Task 3) and `sitingText` (Task 4).
- `drawerHTML` gains `sitingRule` as its fourth parameter in Task 4 and is called with `state.sitingRule`.
- `worcester_structures` (Task 1) and the structures-loaded `worcester_parcels` (Task 2) match their consumers in Tasks 1–3.

**Count arithmetic.**
- Python: 992 → T1 +10 = 1002 → T2 +8 = 1010 → T3 +3 mapgeo +3 site_data = 1016 → T5 replaces one test = **1016**.
- Render: 50 → T4 +7 = **57**.

**Risks worth naming.**
- **Confidence tiers shift visibly** (exported HIGH 121 → 87). The spec requires it and scoring is untouched, but someone who has seen the live chips will notice. The commit message and the coverage review both say why.
- **Shared-fixture guard.** `test_shared_fixtures.py` compares `worcester_parcels` before and after its consumers. `shapely.prepare` marks parcel geometries as prepared in place. That does not change their coordinates or equality, but if the guard ever flags `geometry`, prepared state is the first suspect.
- **`load_structures` drops fields.** It reads only `STRUCT_ID`, so `SOURCETYPE` (roof versus footprint) is not carried. All but 60 Worcester features are roofprints, so the conservative reading is uniform. If another town's layer is mostly `FOOTPRINT`, the clearance stops being an underestimate, and the method statement should say so.
