# Fall River and Lowell Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Fall River and Lowell load, classify and score through the same pipeline as Worcester, without moving a single Worcester figure.

**Architecture:**
- **A town registry** (`towns.py`) records each covered municipality's id, ComStock county and MassGIS extract. A committed snapshot of MassGIS's electricity-provider table proves each one is National Grid territory.
- **Use codes.** Ingest pads three-digit assessor codes to the crosswalk's four-character form. The crosswalk gains an optional `town_id` column, so a town's local sub-codes override the statewide meaning for that town only.
- **ComStock by county.** Archetypes resolve through each parcel's own county, pooling all Massachusetts counties when a county has no building of a type. That applies to hospitals, which neither Bristol nor Middlesex County has.
- **Scope.** The site stays Worcester-only in this plan; Plan `2026-09-15-three-town-site.md` ships the three towns.

**Tech Stack:** Python 3.11, pandas, geopandas, pyogrio, DuckDB httpfs, pytest.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`
- Stage 0: *"Pull actual `USE_CODE` value counts from the three towns. Build `crosswalk.csv`."*
- Stage 1 step 1: *"MassGIS L3 for the three towns."*
- Line 35: *"Geography: Massachusetts, National Grid territory."*
- Line 612–614: *"Municipal light plants … have different rate structures … None of the three towns is an MLP — confirm."*
- Line 924: *"Municipal light plants (excluded/flagged, National Grid rates never applied to them)."*
- Line 868–870: *"record `assess_year` per town at ingest."*

**The spec correction this plan makes.** The spec names *Worcester, New Bedford, Chicopee*. Its own confirmation step fails for two of them. MassGIS's electricity-provider layer, sourced from the Department of Public Utilities (October 2025), lists:
- New Bedford as *Eversource Energy (NSTAR Electric)*;
- Chicopee as *Chicopee Municipal Lighting Plant, Eversource Energy (NSTAR Electric)*.

The G-2/G-3 tariff every dollar figure rests on does not apply to either. The user chose **Fall River** (id 95), a mill city on a working harbour, and **Lowell** (id 160), the classic mill city. Both are *National Grid (Massachusetts Electric)*.

## Global Constraints

- **Worcester does not move.** Every Worcester parcel's archetype, confidence and score must be byte-identical before and after this plan. Task 2 and Task 3 each check it.
- **The crosswalk is domain judgment and is committed.** Every new row carries a note wherever its choice is not obvious, and follows the file's existing conventions:
  - condos are `multi_meter` 1;
  - residential and vacant uses are excluded HIGH;
  - intermittent occupancy is excluded MED/LOW;
  - collapse points start their note with `COLLAPSE POINT`.
- **No new dependency.** Downloads go through `curl`, for the certificate reason documented in `scripts/fetch_structures.py`.
- **Tooling:**
  - `data/raw/` and `data/interim/` are gitignored.
  - Run `uv run pytest` **without `-q`**.
  - `node`/`npx` via `NB="$HOME/.nvm/versions/node/v22.18.0/bin"`.
- **Baseline.** Record it in Task 1 Step 1. If Plan `2026-09-15-mecols-check.md` has landed, expect **1034 passed, 4 deselected**; if not, **1016**. The expected counts below are that baseline **B** plus the stated additions.
- Branch: `git checkout -b feat/fall-river-and-lowell`.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts, measured 2026-09-15

**Utilities.** Query of `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/ElectricityProviders/FeatureServer/0`: 351 features, with fields `TOWN`, `TOWN_ID`, `ELEC`, `ELEC_LABEL`.
- **Worcester** 348, **Fall River** 95, **Lowell** 160: `National Grid (Massachusetts Electric)`.
- New Bedford 201: `Eversource Energy (NSTAR Electric)`.
- Chicopee 61: `Chicopee Municipal Lighting Plant, Eversource Energy (NSTAR Electric)`.
- Statewide, 159 towns are National Grid-only.

**Extracts.** Both URLs answer HTTP 200:
- `https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/l3parcels/L3_SHP_M095_FALLRIVER.zip` (5.3 MB)
- `…/L3_SHP_M160_LOWELL.zip` (6.2 MB)

Each unzips to a folder (`L3_SHP_M095_FallRiver`, `L3_SHP_M160_Lowell`) holding `M095Assess_CY25_FY26.dbf` / `M095TaxPar_CY25_FY26.shp` (Fall River) and `M160Assess_CY25_FY26.dbf` / `M160TaxPar_CY25_FY26.shp` (Lowell).

| | Fall River | Lowell |
|---|---|---|
| Assess records | 22,060 | 28,134 |
| FY | 2026 | 2026 |
| TaxPar CRS | EPSG:26986 (20,224 polygons) | EPSG:26986 (22,183 polygons) |
| Roofprints | 26,521, EPSG:26986 | 24,739, EPSG:26986 |

Roofprints were fetched with `scripts/fetch_structures.py --town-id 95` and `--town-id 160` into `data/raw/M95_STRUCTURES/` and `data/raw/M160_STRUCTURES/`.

**Use codes.** Built, commercial and industrial classes only.
- **Fall River writes three-digit codes**: `316` for what Worcester writes as `3160`, with identical descriptions. After padding a trailing `0`:
  - 66 of 93 match an existing row;
  - one of those collides: Fall River `976` is *Library*, but the existing `9760` row is *Worcester Redevelopment Authority*;
  - 27 are uncovered.
- **Lowell writes four characters, and its fourth is a local sub-code.** `3401` is *Office Condo* and `9311` is *City of Lowell C*. There are 41 matches and 57 uncovered codes:
  - 10 are statewide standard codes;
  - 47 are Lowell-local, including its own meaning for `9512`, *Char Other C*, which the statewide row excludes as a charitable condo.
- **Lowell also writes `995`**, 573 records of *Other, Open Space*, as Worcester does. Padding every three-digit code therefore needs the crosswalk's `995` row renamed to `9950`.

**ComStock hospitals by county.** Distinct buildings per county: Essex 5, Suffolk 3, Worcester 2, Norfolk 1, and **Bristol and Middlesex 0**. Pooling every county gives a hospital cohort of **11**, below `MIN_COHORT = 30`, so it is flagged `widened` and the row carries `thin_cohort`. Bristol has 2,018 buildings over 13 types and Middlesex 2,936, so every other type exists in both counties.

**Counts pinned by existing tests.** `tests/test_crosswalk.py` pins:
- `EXPECTED_ROWS = 95`;
- `EXPECTED_COVERAGE = {total 95, comstock 50, modeled 16, excluded 29, collapse_points 2}`;
- a uniqueness check over `use_code`;
- the collapse set `{"4000","4010"}`;
- the literal `"995"` in two places.

Nothing else references `995` or `9760` except a docstring in `ingest._use_code`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/towns.py` *(new)* | The covered municipalities: id, name, slug, ComStock county, extract. |
| `data/town_utilities.csv` *(new, committed)* | MassGIS electricity provider per municipality, fetched date recorded. |
| `scripts/fetch_town_utilities.py`, `scripts/fetch_l3.py` *(new)* | Reproduce the two downloads. |
| `src/shave/crosswalk.py`, `src/shave/crosswalk.csv` *(modify)* | Optional `town_id`; 83 new rows; `995`→`9950`; `9760` scoped to Worcester. |
| `src/shave/ingest.py` *(modify)* | Pad three-digit codes; classify per town; carry `town_id`. |
| `src/shave/comstock.py`, `src/shave/pipeline.py`, `scripts/warm_comstock_cache.py` *(modify)* | County per parcel; statewide pool when a county lacks a type. |
| `tests/test_towns.py` *(new)*, `tests/test_crosswalk.py`, `tests/test_ingest.py`, `tests/test_comstock.py`, `tests/test_pipeline.py` | |

---

## Task 1: The town registry, proven National Grid

**Files:**
- Create: `src/shave/towns.py`
- Create: `scripts/fetch_town_utilities.py`, `scripts/fetch_l3.py`
- Create: `data/town_utilities.csv` (generated, committed)
- Create: `tests/test_towns.py`

**Interfaces:**
- Produces:
  - `towns.Town(town_id: int, name: str, slug: str, county_gisjoin: str, l3_zip: str, l3_dir: str)`, with property `l3_url`
  - `towns.TOWNS: tuple[Town, ...]`, in order Worcester, Fall River, Lowell
  - `towns.DEFAULT_TOWN_ID = 348`
  - `towns.by_id(town_id) -> Town`, which raises `KeyError`
  - `towns.county_for(town_id) -> str`, returning Worcester's county for `None`/NA
  - `towns.NATIONAL_GRID = "National Grid (Massachusetts Electric)"`
  - `towns.utilities(path=UTILITIES_PATH) -> dict[int, str]`

- [ ] **Step 1: Branch and record the baseline**

```bash
git checkout -b feat/fall-river-and-lowell
uv run pytest 2>&1 | tail -1
```

Record **B**, the passed count.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_towns.py`:

```python
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
```

Run: `uv run pytest tests/test_towns.py`
Expected: FAIL — `ImportError: cannot import name 'towns'`.

- [ ] **Step 3: Write `src/shave/towns.py`**

```python
"""The municipalities this tool covers, and why each qualifies.

A town qualifies only if National Grid (Massachusetts Electric) serves it: the
G-2/G-3 tariff, the rate-class test and every dollar figure are National
Grid's. The design doc named Worcester, New Bedford and Chicopee, and its own
"confirm none is a municipal light plant" step fails for two of them:
MassGIS's electricity-provider layer (Department of Public Utilities, October
2025) lists New Bedford as Eversource and Chicopee as a municipal light plant.
Fall River and Lowell replace them -- a harbour mill city and a mill city,
both National Grid -- and `data/town_utilities.csv` is the checkable record.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

L3_BASE_URL = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
    "shapefiles/l3parcels"
)
NATIONAL_GRID = "National Grid (Massachusetts Electric)"
UTILITIES_PATH = Path(__file__).resolve().parents[2] / "data" / "town_utilities.csv"


@dataclass(frozen=True)
class Town:
    town_id: int
    name: str
    slug: str
    #: NHGIS GISJOIN of the county, the partition ComStock metadata uses.
    county_gisjoin: str
    #: MassGIS's file name for the L3 extract.
    l3_zip: str
    #: Where that extract unzips.
    l3_dir: str

    @property
    def l3_url(self) -> str:
        return f"{L3_BASE_URL}/{self.l3_zip}"


TOWNS: tuple[Town, ...] = (
    Town(348, "Worcester", "worcester", "G2500270",
         "L3_SHP_M348_WORCESTER.zip", "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"),
    Town(95, "Fall River", "fall-river", "G2500050",
         "L3_SHP_M095_FALLRIVER.zip", "data/raw/M095_FALLRIVER/L3_SHP_M095_FallRiver"),
    Town(160, "Lowell", "lowell", "G2500170",
         "L3_SHP_M160_LOWELL.zip", "data/raw/M160_LOWELL/L3_SHP_M160_Lowell"),
)

DEFAULT_TOWN_ID = 348


def by_id(town_id) -> Town:
    tid = int(town_id)
    for town in TOWNS:
        if town.town_id == tid:
            return town
    raise KeyError(f"town {tid} is not covered; covered: {[t.town_id for t in TOWNS]}")


def county_for(town_id) -> str:
    """ComStock county for a parcel's town. A parcel built without a town --
    the synthetic test frames -- takes Worcester's, which is what every
    parcel used before towns existed."""
    if town_id is None or pd.isna(town_id):
        return by_id(DEFAULT_TOWN_ID).county_gisjoin
    return by_id(town_id).county_gisjoin


def utilities(path: Path | str = UTILITIES_PATH) -> dict[int, str]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return {int(row["town_id"]): row["elec"] for row in csv.DictReader(fh)}
```

- [ ] **Step 4: Generate the utility snapshot and the fetch scripts**

Create `scripts/fetch_town_utilities.py`:

```python
"""Snapshot MassGIS's electricity provider for every municipality.

    uv run python scripts/fetch_town_utilities.py

Writes data/town_utilities.csv, which IS committed: it is the evidence that
each covered town is National Grid territory.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys

from shave import towns

QUERY = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "ElectricityProviders/FeatureServer/0/query"
    "?where=1%3D1&outFields=TOWN,TOWN_ID,ELEC&returnGeometry=false&f=json"
)


def main() -> int:
    raw = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "60", QUERY],
        check=True, capture_output=True,
    ).stdout
    features = json.loads(raw)["features"]
    rows = sorted(
        ({"town_id": f["attributes"]["TOWN_ID"], "town": f["attributes"]["TOWN"],
          "elec": f["attributes"]["ELEC"]} for f in features),
        key=lambda r: r["town_id"],
    )
    fetched = dt.date.today().isoformat()
    with towns.UTILITIES_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["town_id", "town", "elec", "fetched_on"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "fetched_on": fetched})
    print(f"{len(rows)} municipalities -> {towns.UTILITIES_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `scripts/fetch_l3.py`:

```python
"""Download and unzip one covered town's MassGIS L3 parcel extract.

    uv run python scripts/fetch_l3.py --town-id 95
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from shave import towns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--town-id", type=int, required=True)
    args = parser.parse_args()
    town = towns.by_id(args.town_id)
    target = Path(town.l3_dir).parent
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / town.l3_zip
        subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location", "--retry", "3",
             "--max-time", "600", "--output", str(archive), town.l3_url],
            check=True,
        )
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    print(f"{town.l3_url} -> {town.l3_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
uv run python scripts/fetch_town_utilities.py
uv run python scripts/fetch_l3.py --town-id 95
uv run python scripts/fetch_l3.py --town-id 160
uv run python scripts/fetch_structures.py --town-id 95
uv run python scripts/fetch_structures.py --town-id 160
ls data/raw/M095_FALLRIVER/L3_SHP_M095_FallRiver/M095TaxPar_*.shp data/raw/M160_LOWELL/L3_SHP_M160_Lowell/M160TaxPar_*.shp
```

Expected: `351 municipalities`, and both TaxPar files listed. The Fall River extract failed once during planning with a dropped connection, then succeeded on retry; `--retry 3` is for that.

- [ ] **Step 5: Run and commit**

```bash
uv run pytest tests/test_towns.py
uv run pytest
git add src/shave/towns.py scripts/fetch_town_utilities.py scripts/fetch_l3.py data/town_utilities.csv tests/test_towns.py
git commit -m "feat: the town registry, proven National Grid territory

The design doc named New Bedford and Chicopee alongside Worcester, and its own
municipal-light-plant check fails for both: MassGIS's electricity provider
layer lists New Bedford as Eversource and Chicopee as a municipal light plant,
so the G-2/G-3 tariff never applies there. Fall River and Lowell -- a harbour
mill city and a mill city, both National Grid -- replace them, and the
committed provider snapshot is the checkable record.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **B + 4 passed**.

---

## Task 2: Use codes, padded and town-scoped

**Files:**
- Modify: `src/shave/crosswalk.csv` (header; the `995` row; the `9760` row; append 83 rows)
- Modify: `src/shave/crosswalk.py` (`CrosswalkRow`, `load`, `archetype_for`, `assert_covers`, `coverage_summary`; add `rows_for_town`)
- Modify: `src/shave/ingest.py` (`_use_code`, `_crosswalk_frame`, `build_parcels`, `OUTPUT_COLUMNS`, final schema)
- Test: `tests/test_crosswalk.py`, `tests/test_ingest.py`

**Interfaces:**
- Consumes: `towns.TOWNS`, `towns.by_id` (Task 1).
- Produces:
  - `CrosswalkRow.town_id: str`, blank for the statewide meaning
  - `crosswalk.load(path=None) -> dict[str, CrosswalkRow]`, **statewide rows only** (unchanged meaning for existing callers)
  - `crosswalk.rows_for_town(town_id=None, path=None) -> dict[str, CrosswalkRow]`: statewide merged with that town's rows, where the town's rows win
  - `crosswalk.archetype_for(use_code, sqft=None, town_id=None)`, `crosswalk.assert_covers(use_codes, town_id=None)`
  - `crosswalk.coverage_summary()`, which gains `town_overrides`
  - ingest output gains `town_id` (Int64)

- [ ] **Step 1: Write the failing tests**

In `tests/test_crosswalk.py`, make these edits:

- `HEADER` gains `"town_id"` as its last item.
- Replace `EXPECTED_ROWS = 95` and `EXPECTED_COVERAGE = {…}` with:

  ```python
  #: Statewide rows (town_id blank): what `crosswalk.load()` returns.
  EXPECTED_ROWS = 121
  #: Every physical row in the file, town rows included.
  EXPECTED_FILE_ROWS = 178
  EXPECTED_COVERAGE = {
      "total": 178,
      "comstock": 81,
      "modeled": 26,
      "excluded": 71,
      "collapse_points": 3,
      "town_overrides": 57,
  }
  ```

- Replace `test_no_duplicate_use_codes_in_the_committed_file` with:

  ```python
  def test_no_duplicate_use_codes_within_a_town_in_the_committed_file():
      with crosswalk.CROSSWALK_PATH.open(newline="", encoding="utf-8") as fh:
          keys = [((row.get("town_id") or "").strip(), row["use_code"].strip())
                  for row in csv.DictReader(fh)]
      assert len(keys) == len(set(keys)) == EXPECTED_FILE_ROWS
  ```

- In `test_use_codes_are_strings_not_integers`, replace `assert "995" in codes` with `assert "9950" in codes`, and change the comment's `995` references to `9950`.
- In `test_assert_covers_passes_on_a_subset`, change `"995"` to `"9950"`.

Append to `tests/test_crosswalk.py`:

```python
# ---------------------------------------------------------------------------
# town rows
# ---------------------------------------------------------------------------


def test_a_town_row_overrides_the_statewide_meaning_for_that_town_only():
    assert crosswalk.rows_for_town(160)["9512"].archetype == "small_office"
    assert crosswalk.rows_for_town(348)["9512"].excluded
    assert crosswalk.rows_for_town(None)["9512"].excluded


def test_a_town_only_code_is_invisible_to_other_towns():
    assert "3401" in crosswalk.rows_for_town(160)
    assert "3401" not in crosswalk.rows_for_town(95)
    assert "3401" not in crosswalk.load()


def test_worcester_keeps_its_local_9760_and_fall_river_gets_its_library():
    assert crosswalk.rows_for_town(348)["9760"].excluded
    assert crosswalk.rows_for_town(95)["9760"].archetype == "medium_office"
    assert "9760" not in crosswalk.load()


def test_the_same_code_may_carry_one_row_per_town(tmp_path):
    path = write_crosswalk(tmp_path, [
        good_row(),
        good_row(town_id="95", archetype="retail_standalone", confidence="LOW"),
    ])
    crosswalk.load(path)
    assert crosswalk.rows_for_town(95, path)["3160"].archetype == "retail_standalone"
    assert crosswalk.rows_for_town(348, path)["3160"].archetype == "warehouse"


def test_a_duplicate_code_within_one_town_is_rejected(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(town_id="95"), good_row(town_id="95")])
    with pytest.raises(CrosswalkError, match="duplicate"):
        crosswalk.load(path)


def test_a_non_numeric_town_id_is_rejected(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(town_id="Lowell")])
    with pytest.raises(CrosswalkError, match="town_id"):
        crosswalk.load(path)


def test_assert_covers_honours_town_rows():
    crosswalk.assert_covers({"3401", "9311"}, town_id=160)
    with pytest.raises(CrosswalkError, match="3401"):
        crosswalk.assert_covers({"3401"}, town_id=348)


def test_lowells_4022_is_a_collapse_point_like_4000():
    assert crosswalk.rows_for_town(160)["4022"].is_collapse_point
    statewide = {code for code, row in crosswalk.load().items() if row.is_collapse_point}
    assert statewide == {"4000", "4010"}
```

Append to `tests/test_ingest.py`:

```python
# ---------------------------------------------------------------------------
# use codes across towns
# ---------------------------------------------------------------------------

from shave.ingest import _use_code


def test_three_digit_codes_are_padded_and_local_codes_left_alone():
    """Fall River writes 316 for what Worcester writes 3160. A fourth character
    is a local sub-code (942C, Lowell's 3401) and must never be touched."""
    out = list(_use_code(pd.Series(["316", "3160", "942C", "3401", "995", "", None])))
    assert out == ["3160", "3160", "942C", "3401", "9950", "", ""]


def test_a_padded_code_classifies_and_the_town_is_carried():
    row = only(build_parcels(assess(record(USE_CODE="316")), town_id=WORCESTER_TOWN_ID))
    assert (row.use_code, row.archetype, row.town_id) == ("3160", "warehouse", 348)


def test_a_town_row_reaches_the_parcel():
    row = only(build_parcels(assess(record(USE_CODE="9512", TOWN_ID=160)), town_id=160))
    assert row.archetype == "small_office"
    assert crosswalk.archetype_for("9512", town_id=348) is None


@pytest.mark.parametrize("town_id", [95, 160])
def test_fall_river_and_lowell_load_with_every_use_code_classified(town_id):
    from shave import towns

    town = towns.by_id(town_id)
    if not Path(town.l3_dir).is_dir():
        pytest.skip(f"{town.name} L3 extract not present; run scripts/fetch_l3.py --town-id {town_id}")
    gdf = load_municipality(town.l3_dir, town_id)
    assert len(gdf) > 0
    assert set(gdf["town_id"].dropna().astype(int)) == {town_id}
```

Run: `uv run pytest tests/test_crosswalk.py tests/test_ingest.py`
Expected: FAIL, for example:
- the town tests with `AttributeError: module 'shave.crosswalk' has no attribute 'rows_for_town'`;
- the padding test with an assertion error, because `_use_code` already exists but does not yet pad;
- the count tests, because the file still has 95 rows.

- [ ] **Step 2: Edit `src/shave/crosswalk.csv`**

**Header.** Replace line 1 with:

```
use_code,use_desc,archetype,source,icp_sector,confidence,note,multi_meter,town_id
```

**The `995` row.** Replace:

```
995,"Other, Open Space",exclude,,,HIGH,344 parcels totalling 13 sq ft of building area.,0
```

with:

```
9950,"Other, Open Space",exclude,,,HIGH,"Written 995 by the assessor and padded to 9950 at ingest. 344 Worcester parcels totalling 13 sq ft of building area.",0,
```

**The `9760` row.** Replace:

```
9760,Worcester Redevelopment Authority,exclude,,,MED,,0
```

with:

```
9760,Worcester Redevelopment Authority,exclude,,,MED,Worcester's local use of 976.,0,348
```

**New rows.** Append these 83 rows at the end of the file, exactly:

```
3110,Bottled Gas and Propane Gas Tanks,exclude,,,MED,Storage tanks. No building load.,0,
3130,Lumber Yards,warehouse,comstock,,LOW,Open storage with a yard office; ambient warehouse is the nearest shape.,0,
3180,Commercial Greenhouses,exclude,,,LOW,Heating and grow-lighting load that no archetype carries. Single small parcel.,0,
3500,Property Used for Postal Services,warehouse,comstock,,LOW,Sorting and dock operations.,0,
3540,Bus Transportation Facilities,warehouse,comstock,,LOW,Bus garages and maintenance depots. See 9720.,0,
3620,Motion Picture Theaters,exclude,,,LOW,ComStock explicitly excludes theaters. See 3640.,0,
3690,Other Cultural and Entertainment Properties,exclude,,,LOW,Intermittent occupancy.,0,
3700,Bowling Alleys,exclude,,,LOW,Indoor recreation. See 3770.,0,
3840,Marinas,exclude,,,MED,Outdoor facility. No meaningful building load.,0,
3880,Other Outdoor Facilities,exclude,,,HIGH,Driving ranges and similar. No building load.,0,
3900,Developable Commercial Land,exclude,,,HIGH,Vacant.,0,
4310,Telephone Relay Towers and Cell Towers,exclude,,,HIGH,Utility asset. Not a customer building.,0,
4500,Electric Generation Plants,exclude,,,HIGH,A generator. Not a demand-charge customer in the sense this tool models.,0,
4520,"Electric Generation Plants, Agreement Value",exclude,,,HIGH,See 4500.,0,
9040,"Colleges and Schools, Private (retired code)",university,modeled,,LOW,Retired 2009. See 9420.,0,
9170,"DOE: UMass, State and Community Colleges (reimbursable)",university,modeled,,LOW,The reimbursable twin of 9270.,0,
9190,Commonwealth of Massachusetts (other),medium_office,comstock,,LOW,The reimbursable twin of 9290.,0,
9260,Judiciary,medium_office,comstock,,MED,Courthouses: office-like weekday occupancy.,0,
9370,"Improved, Tax Title / Treasurer (Municipal)",exclude,,,MED,Held by the municipality for tax title; occupancy unknown.,0,
9390,"Improved, District (County)",medium_office,comstock,,LOW,,0,
9440,Auxiliary Athletic (Educational Private),exclude,,,MED,Intermittent occupancy.,0,
9450,Affiliated Housing (Educational Private),exclude,,,HIGH,Residential.,0,
9520,"Auxiliary Use: Storage, Barns (Charitable Org)",exclude,,,MED,,0,
9610,Rectory or Parsonage,exclude,,,HIGH,Residential.,0,
9800,"Vacant, Selectmen or City Council, Other City or Town",exclude,,,HIGH,Vacant.,0,
9810,"Improved, Selectmen or City Council, Other City or Town",medium_office,comstock,,LOW,,0,
9960,"Other, Non-Taxable Condominium Common Land",exclude,,,HIGH,Common land. No building load.,0,
3030,Commercial Condo,strip_mall,comstock,,LOW,Condo. Metering almost certainly split. See 3221.,1,95
3940,Hall,exclude,,,MED,Function hall. Intermittent occupancy.,0,95
3950,Salon,retail_standalone,comstock,,MED,Small personal-service retail.,0,95
3990,Other Commercial,exclude,,,LOW,No usable description. See 3222.,0,95
4050,Industrial Condo,industrial_manufacturing,modeled,,LOW,Condo. Metering almost certainly split. See 4021.,1,95
9760,Library,medium_office,comstock,,LOW,Fall River's local use of 976; Worcester uses it for its redevelopment authority. See 9560.,0,95
9770,DPW,warehouse,comstock,,LOW,Municipal public works garages and yards.,0,95
9970,Other,exclude,,,LOW,No usable description.,0,95
9980,City Park and Recreation,exclude,,,HIGH,Parkland structures.,0,95
322I,Other: Dry Cleaner / Laundry,industrial_manufacturing,modeled,,LOW,"Commercial laundry, a named ICP load; modelled as manufacturing, as the 4000 collapse point does.",0,160
3401,Office Condo,small_office,comstock,,LOW,Condo. Metering almost certainly split.,1,160
340I,Other: Office Building,office,comstock,,LOW,Size band resolved from floor area.,0,160
342O,Other: Condo Office,small_office,comstock,,LOW,Condo. Metering almost certainly split.,1,160
3841,Yacht Club,exclude,,,MED,Seasonal clubhouse.,0,160
4022,Industrial Building,industrial_manufacturing,modeled,"1,3,4,5",LOW,"COLLAPSE POINT. Lowell's sub-code of 4000, and just as coarse: every kind of manufacturer can carry it. Within this code the ranking is driven by floor area and rate class, not by load shape.",0,160
404C,Manufacturing and Processing: Research and Development,laboratory,modeled,6,LOW,ComStock explicitly excludes laboratories. See 4040.,0,160
900C,US Government (commercial building),medium_office,comstock,,MED,See 9000.,0,160
901R,Public Service Properties (residential-style building),exclude,,,LOW,Residential-style building with no usable type.,0,160
905C,Private Hospital (Charitable),hospital,comstock,,LOW,See 9050.,0,160
910R,Environmental Management (residential-style building),exclude,,,LOW,,0,160
9172,"DOE: UMass, State and Community Colleges (imputed)",university,modeled,,LOW,See 9170.,0,160
917C,"DOE: UMass, State and Community Colleges (commercial building)",university,modeled,,LOW,UMass Lowell and Middlesex Community College buildings.,0,160
917I,"DOE: UMass, State and Community Colleges (industrial building)",university,modeled,,LOW,,0,160
920C,Dept of Conservation and Recreation (commercial building),exclude,,,MED,See 9200.,0,160
927C,"DOE: UMass Lowell, Middlesex Community College (non-reimbursable)",university,modeled,,LOW,See 9270.,0,160
928C,DCAM State Office Buildings (non-reimbursable),office,comstock,,LOW,Size band resolved from floor area. See 9280.,0,160
929C,Commonwealth of Massachusetts Other (non-reimbursable),medium_office,comstock,,LOW,See 9290.,0,160
9311,City of Lowell (commercial building),medium_office,comstock,,MED,See 9310.,0,160
9341,Lowell Public Schools (commercial building),secondary_school,comstock,,MED,See 9340.,0,160
9351,Public Safety (commercial building),small_office,comstock,,MED,Fire and police stations. See 9350.,0,160
9371,Tax Title (commercial building),exclude,,,MED,See 9370.,0,160
9372,Other: Condo Office (municipal),small_office,comstock,,LOW,Condo. Metering almost certainly split.,1,160
9401,Private Elementary School (commercial building),primary_school,comstock,,MED,See 9400.,0,160
9411,Private Secondary School (commercial building),secondary_school,comstock,,MED,See 9410.,0,160
9431,Private Other Educational (commercial building),secondary_school,comstock,,LOW,See 9430.,0,160
9511,Charitable Other (residential-style building),exclude,,,MED,Residential-style building.,0,160
9512,Charitable Other (commercial building),small_office,comstock,,LOW,"Lowell's 9512 is a commercial charitable building, not the exempt charitable condo the statewide row excludes. See 9510.",0,160
9513,Charitable Other Condo,exclude,,,LOW,Condo with no usable type. See the statewide 9512.,0,160
9532,Cemeteries (commercial building),exclude,,,HIGH,,0,160
9541,Function Hall or Fraternal Organization (commercial building),retail_standalone,comstock,,LOW,Intermittent occupancy. See 9540.,0,160
9552,Hospital (Charitable; commercial building),hospital,comstock,7,HIGH,See 9550.,0,160
9561,Library or Museum (commercial building),medium_office,comstock,,LOW,See 9560.,0,160
9571,Charitable Services (commercial building),medium_office,comstock,,LOW,See 9570.,0,160
9582,Charitable Recreation (commercial building),exclude,,,MED,See 9580.,0,160
9591,Charitable Housing (residential-style building),exclude,,,HIGH,Residential.,0,160
9592,Charitable Housing (commercial building),exclude,,,HIGH,Residential.,0,160
9601,Church or Temple (residential-style building),exclude,,,HIGH,,0,160
9602,Church or Temple (commercial building),exclude,,,HIGH,Intermittent occupancy. No shaveable weekday peak.,0,160
9611,Rectory or Parsonage (residential-style building),exclude,,,HIGH,Residential.,0,160
9612,Rectory or Parsonage (commercial building),exclude,,,HIGH,Residential.,0,160
9622,Other Religious (commercial building),exclude,,,HIGH,,0,160
9701,Housing Authority (commercial building),exclude,,,HIGH,Residential.,0,160
9702,Housing Authority Condo,exclude,,,HIGH,Residential.,0,160
9711,Utility Authority (commercial building),exclude,,,HIGH,Utility asset.,0,160
9721,Transportation Authority (commercial building),warehouse,comstock,,LOW,Bus and maintenance depots. See 9720.,0,160
9971,Other: Apartments,exclude,,,HIGH,Residential.,0,160
```

The rows break down as follows:

| group | rows | comstock | modeled | excluded |
|---|---|---|---|---|
| statewide | 27 | 7 | 2 | 18 |
| Fall River (95) | 9 | 4 | 1 | 4 |
| Lowell (160) | 47 | 20 | 7 | 20 |

The file totals 178 rows (121 statewide, 57 town): 81 comstock, 26 modeled, 71 excluded.

- [ ] **Step 3: Teach `src/shave/crosswalk.py` about towns**

In `CrosswalkRow`, add after `multi_meter`:

```python
    #: Blank for the statewide Department of Revenue meaning of the code. A
    #: town id when that municipality uses the code for something of its own:
    #: Lowell's fourth character is a local sub-code, and the 970-999 range is
    #: assigned locally (Worcester's 9760 is its redevelopment authority, Fall
    #: River's is a library). A town's row wins for that town and no other.
    town_id: str = ""
```

Replace the whole of `load` with:

```python
#: Town rows per crosswalk file, filled by `load` as it parses. Kept beside the
#: cached statewide dict so existing callers of `load()` see exactly what they
#: always have.
_TOWN_ROWS: dict[Path, dict[tuple[str, str], CrosswalkRow]] = {}


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict[str, CrosswalkRow]:
    """Read and validate the crosswalk; return its STATEWIDE rows.

    Town rows are validated too and made available through `rows_for_town`.
    Cached; call `load.cache_clear()` in tests.
    """
    src = Path(path) if path is not None else CROSSWALK_PATH
    if not src.exists():
        raise CrosswalkError(f"crosswalk not found at {src}")

    statewide: dict[str, CrosswalkRow] = {}
    town_rows: dict[tuple[str, str], CrosswalkRow] = {}
    with src.open(newline="", encoding="utf-8") as fh:
        for lineno, raw in enumerate(csv.DictReader(fh), start=2):
            code = (raw.get("use_code") or "").strip()
            if not code:
                raise CrosswalkError(f"{src}:{lineno} blank use_code")
            town = (raw.get("town_id") or "").strip()
            if town and not town.isdigit():
                raise CrosswalkError(f"{src}:{lineno} town_id must be a number, got {town!r}")
            if (town and (town, code) in town_rows) or (not town and code in statewide):
                raise CrosswalkError(
                    f"{src}:{lineno} duplicate use_code {code!r}"
                    + (f" for town {town}" if town else "")
                )

            row = CrosswalkRow(
                use_code=code,
                use_desc=(raw.get("use_desc") or "").strip(),
                archetype=(raw.get("archetype") or "").strip(),
                source=(raw.get("source") or "").strip(),  # type: ignore[arg-type]
                icp_sector=(raw.get("icp_sector") or "").strip(),
                confidence=((raw.get("confidence") or "LOW").strip().upper()),  # type: ignore[arg-type]
                note=(raw.get("note") or "").strip(),
                multi_meter=_parse_flag(
                    raw.get("multi_meter"), "multi_meter", f"{src.name}:{lineno} ({code})"
                ),
                town_id=town,
            )
            _validate_row(row, src, lineno)
            if town:
                town_rows[(town, code)] = row
            else:
                statewide[code] = row

    if not statewide and not town_rows:
        raise CrosswalkError(f"{src} has no rows")
    _TOWN_ROWS[src] = town_rows
    return statewide


def rows_for_town(
    town_id: int | str | None = None, path: Path | None = None
) -> dict[str, CrosswalkRow]:
    """Statewide rows with one town's own rows laid over them."""
    statewide = load(path)
    if town_id is None:
        return statewide
    tid = str(int(town_id))
    src = Path(path) if path is not None else CROSSWALK_PATH
    local = {code: row for (town, code), row in _TOWN_ROWS.get(src, {}).items() if town == tid}
    return {**statewide, **local}
```

In `archetype_for`, change the signature to `def archetype_for(use_code: str, sqft: float | None = None, town_id: int | str | None = None) -> CrosswalkRow | None:` and replace `rows = load()` with `rows = rows_for_town(town_id)`.

In `assert_covers`, change the signature to `def assert_covers(use_codes: set[str], town_id: int | str | None = None) -> None:` and replace `rows = load()` with `rows = rows_for_town(town_id)`.

Replace the whole of `coverage_summary` with:

```python
def coverage_summary() -> dict[str, int]:
    """Counts over every row in the file, town rows included."""
    statewide = load()
    town_rows = list(_TOWN_ROWS.get(CROSSWALK_PATH, {}).values())
    rows = list(statewide.values()) + town_rows
    return {
        "total": len(rows),
        "comstock": sum(1 for r in rows if r.source == "comstock"),
        "modeled": sum(1 for r in rows if r.source == "modeled"),
        "excluded": sum(1 for r in rows if r.excluded),
        "collapse_points": sum(1 for r in rows if r.is_collapse_point),
        "town_overrides": len(town_rows),
    }
```

- [ ] **Step 4: Pad codes and classify per town in `src/shave/ingest.py`**

Replace `_use_code` with:

```python
def _use_code(series: pd.Series) -> pd.Series:
    """Use codes as strings, in the crosswalk's four-character form.

    Worcester writes `3160`; Fall River writes the same Department of Revenue
    code as `316`. A bare three-digit code is the DOR base code with no local
    sub-code, so it gains a trailing zero. A fourth character is a local
    sub-code -- `942C`, Lowell's `3401` -- and is left exactly as written.
    """
    out = series.astype("string").str.strip().fillna("")
    three_digit = out.str.fullmatch(r"\d{3}").fillna(False)
    return out.where(~three_digit, out + "0")
```

Change `_crosswalk_frame` to take the town. Its signature becomes `def _crosswalk_frame(codes: Iterable[str], town_id: int | str | None = None) -> pd.DataFrame:`. Inside it:
- replace `rows = crosswalk.load()` with `rows = crosswalk.rows_for_town(town_id)`;
- replace `crosswalk.archetype_for(code)` with `crosswalk.archetype_for(code, town_id=town_id)`.

In `build_parcels`:
- replace `crosswalk.assert_covers(observed_codes)` with `crosswalk.assert_covers(observed_codes, town_id=town_id)`;
- replace `cw = _crosswalk_frame(observed_codes)` with `cw = _crosswalk_frame(observed_codes, town_id=town_id)`.

In `OUTPUT_COLUMNS`, insert `"town_id",` directly after `"loc_id",`. In the final `out = pd.DataFrame({...})`, add directly after the `"loc_id"` entry:

```python
            "town_id": pd.array(
                [None if town_id is None else int(town_id)] * len(parcels), dtype="Int64"
            ),
```

- [ ] **Step 5: Run, and prove Worcester did not move**

```bash
uv run pytest tests/test_crosswalk.py tests/test_ingest.py
uv run pytest
uv run python scripts/build_site.py && uv run python -c "
import json; d = json.load(open('public/data/ranked.json'))
rows = sorted((r['loc_id'], r['archetype'], r['confidence'], r['annual_savings_usd'], r['rank']) for l in d['lists'].values() for r in l)
json.dump(rows, open('/tmp/worcester-after-t2.json', 'w'))
print(len(rows), 'rows')"
git stash && uv run python scripts/build_site.py && uv run python -c "
import json; d = json.load(open('public/data/ranked.json'))
rows = sorted((r['loc_id'], r['archetype'], r['confidence'], r['annual_savings_usd'], r['rank']) for l in d['lists'].values() for r in l)
print('worcester unchanged:', rows == [tuple(x) for x in json.load(open('/tmp/worcester-after-t2.json'))])"
git stash pop
```

**Pass conditions, declared in advance:**
- **B + 17 passed**: 8 crosswalk, 3 ingest synthetic, 2 real-data, 4 from Task 1.
- `worcester unchanged: True`. Worcester's `995` records are excluded both before and after, and its `9760` row is the same row, now scoped to 348.

- [ ] **Step 6: Commit**

```bash
git add src/shave/crosswalk.csv src/shave/crosswalk.py src/shave/ingest.py tests/test_crosswalk.py tests/test_ingest.py
git commit -m "feat: use codes padded and scoped per town

Fall River writes the Department of Revenue base codes with three digits (316
for Worcester's 3160), so ingest pads a bare three-digit code with a trailing
zero; a fourth character is a local sub-code and is never touched. The
crosswalk gains an optional town_id so a municipality's own meaning of a code
wins for that town only: Lowell's 3401 is an office condo, Lowell's 9512 is a
commercial charitable building, and 976 is Worcester's redevelopment
authority but Fall River's library.

83 new rows: 27 statewide, 9 for Fall River, 47 for Lowell. Lowell's 4022
'Industrial Bldg' is a collapse point exactly like 4000. The 995 row becomes
9950 to match the padding. Every Worcester archetype, confidence and score is
unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 3: ComStock per county, pooled where a county has none

**Files:**
- Modify: `src/shave/comstock.py` (after `WORCESTER_COUNTY_GISJOIN`; the cache-miss branch of `build_archetype`)
- Modify: `src/shave/pipeline.py` (`default_archetype_factory`)
- Modify: `scripts/warm_comstock_cache.py` (rewrite)
- Test: `tests/test_comstock.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `towns.county_for`, `towns.TOWNS` (Task 1); ingest `town_id` (Task 2).
- Produces: `comstock.MA_COUNTY_GISJOINS: tuple[str, ...]` (14 counties). `build_archetype` pools them when the requested county has no building of the type.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comstock.py`:

```python
# ---------------------------------------------------------------------------
# a county without the type
# ---------------------------------------------------------------------------

from dataclasses import replace as _replace


class _Conn:
    def close(self):
        pass


def _offline(monkeypatch, index_rows):
    calls = []

    def fake_index(county, conn=None):
        calls.append(county)
        return pd.DataFrame(index_rows(county), columns=["bldg_id", "building_type", "sqft"])

    base = comstock.ReducedProfile.from_frame(
        pd.read_parquet("tests/fixtures/comstock_smalloffice_g2500270.parquet"))

    def fake_reduce(bldg_id, conn=None, sqft=None):
        return _replace(base, bldg_id=int(bldg_id), sqft=sqft)

    monkeypatch.setattr(comstock, "load_county_index", fake_index)
    monkeypatch.setattr(comstock, "reduce_timeseries", fake_reduce)
    monkeypatch.setattr(comstock, "connect", lambda: _Conn())
    return calls


def test_a_county_without_the_type_pools_every_massachusetts_county(tmp_path, monkeypatch):
    """Neither Bristol nor Middlesex County has a ComStock hospital."""
    def rows(county):
        out = [{"bldg_id": 1, "building_type": "Warehouse", "sqft": 10_000.0}]
        if county == "G2500090":  # Essex
            out += [{"bldg_id": 100 + i, "building_type": "Hospital", "sqft": 200_000.0 + i}
                    for i in range(5)]
        return out

    calls = _offline(monkeypatch, rows)

    a = comstock.build_archetype("hospital", 50_000.0, county_gisjoin="G2500050", cache_dir=tmp_path)

    assert calls[0] == "G2500050"
    assert set(calls[1:]) == set(comstock.MA_COUNTY_GISJOINS)
    assert a.profile.bldg_id in {100, 101, 102, 103, 104}
    assert a.widened is True and a.cohort_size == 5


def test_a_county_with_the_type_is_not_pooled(tmp_path, monkeypatch):
    calls = _offline(monkeypatch, lambda county: [
        {"bldg_id": 7, "building_type": "Warehouse", "sqft": 10_000.0}])

    comstock.build_archetype("warehouse", 50_000.0, county_gisjoin="G2500170", cache_dir=tmp_path)

    assert calls == ["G2500170"]


def test_every_massachusetts_county_is_in_the_pool():
    assert len(comstock.MA_COUNTY_GISJOINS) == 14
    assert comstock.MA_COUNTY_GISJOINS[0] == "G2500010"
    assert comstock.WORCESTER_COUNTY_GISJOIN in comstock.MA_COUNTY_GISJOINS
```

Append to `tests/test_pipeline.py`:

```python
def test_the_default_factory_asks_comstock_for_the_parcels_own_county(monkeypatch):
    from shave import comstock

    seen = {}

    def fake_build(name, sqft, county_gisjoin=None, **kwargs):
        seen["county"] = county_gisjoin
        raise comstock.ComStockError("stop here")

    monkeypatch.setattr(comstock, "build_archetype", fake_build)
    base = {"archetype": "warehouse", "sqft": 1000.0, "source": "comstock", "loc_id": "L"}

    with pytest.raises(comstock.ComStockError):
        pipeline.default_archetype_factory({**base, "town_id": 160})
    assert seen["county"] == "G2500170"

    with pytest.raises(comstock.ComStockError):
        pipeline.default_archetype_factory(base)
    assert seen["county"] == "G2500270", "no town means Worcester, as before towns existed"
```

Run: `uv run pytest tests/test_comstock.py tests/test_pipeline.py`
Expected: FAIL — `AttributeError: module 'shave.comstock' has no attribute 'MA_COUNTY_GISJOINS'`.

- [ ] **Step 2: Implement**

In `src/shave/comstock.py`, directly after `WORCESTER_COUNTY_GISJOIN = "G2500270"`, add:

```python
#: Every Massachusetts county, FIPS 25001-25027 (odd codes), in GISJOIN form.
#: `build_archetype` pools them when a county has no building of a type.
MA_COUNTY_GISJOINS: tuple[str, ...] = tuple(f"G250{fips:03d}0" for fips in range(1, 28, 2))
```

In `build_archetype`, replace:

```python
            index = load_county_index(county_gisjoin, conn=conn)
            rep = select_representative(
                index, ARCHETYPE_TO_COMSTOCK[archetype_name], conn=conn
            )
```

with:

```python
            index = load_county_index(county_gisjoin, conn=conn)
            comstock_type = ARCHETYPE_TO_COMSTOCK[archetype_name]
            if not (index["building_type"] == comstock_type).any():
                # Bristol and Middlesex County have no ComStock hospital at all.
                # Pool every Massachusetts county rather than borrowing one
                # neighbour's; select_representative then marks the thin
                # statewide cohort (11 hospitals) as widened, and the row says so.
                index = pd.concat(
                    [load_county_index(g, conn=conn) for g in MA_COUNTY_GISJOINS],
                    ignore_index=True,
                ).drop_duplicates("bldg_id")
            rep = select_representative(index, comstock_type, conn=conn)
```

In `src/shave/pipeline.py`:
- change `from shave import comstock, crosswalk, modeled, scorer` to `from shave import comstock, crosswalk, modeled, scorer, towns`;
- in `default_archetype_factory`, replace `return comstock.build_archetype(name, sqft)` with:

```python
        return comstock.build_archetype(
            name, sqft, county_gisjoin=towns.county_for(parcel.get("town_id"))
        )
```

Replace `scripts/warm_comstock_cache.py` entirely with:

```python
"""Fetch and cache one measured profile per ComStock archetype, per covered town.

Run once per new town. Later stages read only the local cache, so the pipeline
is reproducible offline and a re-run costs nothing.

    uv run python scripts/warm_comstock_cache.py
"""

from __future__ import annotations

import sys
import time

from shave import comstock, siting, towns
from shave.ingest import load_municipality


def main() -> int:
    failures = []
    for town in towns.TOWNS:
        parcels = load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        wanted = sorted(
            parcels.loc[parcels["source"] == "comstock", "archetype"].dropna().unique()
        )
        print(f"\n{town.name} ({town.county_gisjoin}): {len(wanted)} ComStock archetypes")
        for name in wanted:
            started = time.perf_counter()
            try:
                a = comstock.build_archetype(
                    name, sqft=10_000.0, county_gisjoin=town.county_gisjoin
                )
                flag = "  ** WIDENED **" if a.widened else ""
                print(f"  {name:26s} bldg {a.profile.bldg_id:>7}  "
                      f"cohort {a.cohort_size:>4}{flag}  {time.perf_counter() - started:5.1f}s")
            except Exception as exc:  # noqa: BLE001 - report every failure, fail at the end
                failures.append((town.name, name, exc))
                print(f"  {name:26s} FAILED: {exc}")
    if failures:
        print(f"\n{len(failures)} archetype(s) failed", file=sys.stderr)
        return 1
    print(f"\ncache warm in {comstock.CACHE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Warm the new counties and run**

```bash
uv run pytest tests/test_comstock.py tests/test_pipeline.py
uv run python scripts/warm_comstock_cache.py
```

Expected: tests PASS. The warm run lists Worcester from cache instantly, then Fall River (G2500050) and Lowell (G2500170), roughly four minutes each on S3. Every `hospital` line in the two new towns is `** WIDENED **` with cohort 11. No `FAILED` line.

If Plan `2026-09-15-mecols-check.md` has landed, also run `uv run python scripts/refresh_comstock_energy.py` so the new counties' profiles carry monthly energy. New profiles written after that plan already carry it, and the refresh is then a no-op check.

- [ ] **Step 4: Full run, Worcester unchanged, commit**

```bash
uv run pytest
uv run python scripts/build_site.py && uv run python -c "
import json; d = json.load(open('public/data/ranked.json'))
rows = sorted((r['loc_id'], r['archetype'], r['confidence'], r['annual_savings_usd'], r['rank']) for l in d['lists'].values() for r in l)
print('worcester unchanged:', rows == [tuple(x) for x in json.load(open('/tmp/worcester-after-t2.json'))])"
git add src/shave/comstock.py src/shave/pipeline.py scripts/warm_comstock_cache.py tests/test_comstock.py tests/test_pipeline.py
git commit -m "feat: ComStock per county, pooled statewide where a county has none

Each parcel's archetype now comes from its own town's county. Bristol and
Middlesex County have no ComStock hospital, so a county without a building
type pools all fourteen Massachusetts counties; the 11-hospital statewide
cohort is marked widened and the row carries thin_cohort. Worcester's scores
are unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **B + 21 passed** (17 + 3 comstock + 1 pipeline); `worcester unchanged: True`.

---

## Task 4: All three towns score

**Files:**
- Modify: `tests/test_towns.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_towns.py`:

```python
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
```

Run: `uv run pytest tests/test_towns.py`
Expected: PASS. These tests prove Tasks 1–3 together, so they pass on first run. About a minute, two full town scorings.

- [ ] **Step 2: Measure and record**

```bash
uv run python -c "
import collections
from shave import ingest, pipeline, siting, towns
for t in towns.TOWNS:
    p = ingest.load_municipality(t.l3_dir, t.town_id, structures_path=siting.structures_path(t.town_id))
    s = pipeline.score_parcels(p); k = s[s['keep'].astype(bool)]
    print(f\"{t.name:10s} parcels {len(p):5d}  kept {len(k):4d}  sweet {int(k['sweet_spot'].sum()):4d}  \"
          f\"comstock {int((k['source']=='comstock').sum()):4d}  modeled {int((k['source']=='modeled').sum()):4d}  \"
          f\"unscored {dict(collections.Counter(s['unscored_reason'].dropna()))}  \"
          f\"fallback_floor_area {p.attrs['fallback_floor_area']}  FY {p.attrs['assess_fy']}\")
" 2>&1 | grep -v -i warning
```

Record the three lines verbatim in the commit message below. Worcester's must read **2,099 parcels, 737 kept, 172 sweet**.

- [ ] **Step 3: Commit and merge (no deploy: the site is still Worcester-only)**

```bash
uv run pytest
git add tests/test_towns.py
git commit -m "test: Fall River and Lowell score end to end

<the three measured lines from Step 2>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git checkout main && git pull --ff-only origin main
git merge --no-ff feat/fall-river-and-lowell -m "merge: Fall River and Lowell through the pipeline

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
```

Expected: **B + 23 passed**. If `git pull --ff-only` refuses, stop and report.

---

## Self-Review

**Spec coverage.**
- *"MassGIS L3 for the three towns"* → Task 1 fetches and Task 2 loads them, with the town set corrected and the correction evidenced (`data/town_utilities.csv`, `test_the_design_docs_new_bedford_and_chicopee_are_not`).
- *"Pull actual USE_CODE value counts … build crosswalk.csv"* → Task 2's 83 rows, derived from the measured per-town code audit.
- *"None of the three towns is an MLP — confirm"* → `test_every_covered_town_is_national_grid_territory`.
- *"record assess_year per town"* → already in `gdf.attrs["assess_fy"]` per town, measured in Task 4. Surfacing it on the page is the site plan.
- The municipality control and payload → `2026-09-15-three-town-site.md`.

**Placeholder scan.** The commit message slot in Task 4 Step 3 is filled from Step 2's printed output. Every code step carries its code, and every CSV row is written out.

**Type consistency.**
- `towns.county_for` (Task 1) is called by `pipeline.default_archetype_factory` (Task 3) with `parcel.get("town_id")`, produced by ingest (Task 2).
- `crosswalk.rows_for_town(town_id)` is used by `_crosswalk_frame`, `archetype_for` and `assert_covers`.
- `CrosswalkRow.town_id` is a string; `rows_for_town` compares `str(int(town_id))`.
- `MA_COUNTY_GISJOINS` is used by `build_archetype` and its tests.

**Count arithmetic.** B → T1 +4 → T2 +13 → T3 +4 → T4 +2 = **B + 23**.

**Risks.**
- **Pooled hospital cohort.** The statewide pool reads 14 county indexes, about 14 s once per new town, since the result is cached per county. The cohort of 11 is thin, and the `thin_cohort` flag says so on every affected row.
- **Crosswalk judgment.** Any row in Step 2's block is open to a domain reviewer's disagreement, which is what committing the file is for. Changing a row later only moves the parcels carrying that code, and the pinned counts in `test_crosswalk.py` will say which.
