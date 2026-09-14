# Finish and Ship Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four pending items in `docs/spec-coverage.md` that need no new data: ship the map, cut the suite from minutes to about one, draw the 24-hour day profile the spec asks the drawer for, and give a reader an address box to check a building they already know.

**Architecture:** Everything stays build-time Python plus a static page. The day profile is carried out of `pipeline.score_parcel`, where it is already computed, normalised in `site_data`, and drawn as one inline SVG. The address box reads a second static file, `public/data/addresses.json`, loaded only on first search so it costs the ranked list's first paint nothing. There is still no Worker script and no database.

**Tech Stack:** Python 3.11 (pandas, geopandas, pytest), vanilla ES2020 + inline SVG, vitest, Cloudflare Workers static assets.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`. Specifically: Stage 1 step 9 (*"24h load sparkline with the 08:00–21:00 window shaded, source label, confidence tier"*); design review D5 (*"The address box moves to Stage 1… a static prebuilt index… no database, so it cannot break when the free tier sleeps"*); the Interaction States table row for Address lookup; success criterion 7. The coverage review this plan executes against is `docs/spec-coverage.md`, "Pending, in recommended order", items 1, 2, 5 and 8.

**Design system:** `DESIGN.md`. In particular: *"Sparklines get an area fill at 16% opacity, a 1.1px stroke, an emphasized peak dot in `--signal`, and a 5%-opacity band marking the billed 08:00–21:00 window."*

**Prior plans:** six. The encoding map (`2026-09-11-encoding-map.md`) has Tasks 1–3 committed on `feat/encoding-map` and **Task 4 never landed**. This plan's Task 1 finishes it.

## Scope, and what is split into later plans

The user chose one plan per subsystem. This is the first: the items that need no download and no hand work.

| Pending item (spec-coverage.md) | Where it goes |
|---|---|
| 1. 24h sparkline with the billed window shaded | **This plan**, Tasks 3–4 |
| 2. Merge and deploy the map | **This plan**, Task 1 |
| 3. Occupant resolution, 46 remaining | No plan. Hand lookups; the ratchet in `tests/test_occupants.py` rises as rows land |
| 4. `STRUCTURES_POLY` + siting screen | Its own plan, next |
| 5. Address box over a static index | **This plan**, Tasks 5–6 |
| 6. New Bedford and Chicopee | Its own plan |
| 7. MECOLS check | Its own plan, after the workbook is re-fetched |
| 8. Suite runtime | **This plan**, Task 2 |

**Order.** Task 1 ships the finished map first so it goes live on its own and is not held behind new work. Task 2 comes next because every later task runs the suite: saving three minutes per run, over roughly twenty runs, pays for itself before Task 3 is done.

## Global Constraints

- Python `>=3.11`. **Do not add any Python or JavaScript dependency.**
- **The page computes no figure it displays.** Every number on screen comes from `scripts/build_site.py`. `app.js` may scale normalised values to pixels, index into arrays the build supplied, and match an address query against the index. Matching a query is search, not a figure.
- **Never restate a constant.** Tariff hours, interval width and battery ratings come from `src/shave/assumptions.py` (or `archetype.STEP_HOURS`). JavaScript gets them through the payload, never as literals.
- **`--signal` is spent on exactly three things** (DESIGN.md): the shaved peak on a sparkline, parcel fill weight on the map, and the selected-row rail. It is never a button. Rate class uses `--g2`/`--g3`.
- **Radius is 3px everywhere (`var(--r)`) and there are no shadows.** Touch targets ≥ 44px.
- **The two ranked lists are never merged** — not in the index, not in a search result.
- Empty states state a finding, not an absence. Errors say what is still working (spec, Interaction States).
- Every text value that came from an assessor record goes through `esc()` before it reaches `innerHTML`.
- **`node`, `npm` and `npx` are nvm shell functions; `export PATH` does not reach them.** Always:
  ```bash
  NB="$HOME/.nvm/versions/node/v22.18.0/bin"
  "$NB/npx" vitest run
  ```
  `/usr/local/bin/wrangler` is a stub that prints "You have not installed wrangler"; never invoke it. Use `"$NB/npx" wrangler`.
- Baselines, measured 2026-09-13 on `feat/encoding-map` at `a2d1225`: **Python 954 passed, 4 deselected**; **render 31 passed**.
- Every commit ends with this trailer:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts, measured 2026-09-13

Do not re-derive these. Do verify the checks each task names.

**Where the suite's time goes.** `uv run pytest --durations=25`:

| test | seconds |
|---|---|
| `test_site_data::test_the_payload_is_json_serialisable_and_small_enough_to_serve` | 30.3 |
| `test_site_data::test_each_list_is_ranked_by_dollars_within_itself` | 29.6 |
| `test_site_data::test_every_field_the_page_reads_is_present_on_every_row` | 26.5 |
| `test_site_data::test_every_exported_row_carries_a_map_path` | 25.7 |
| `test_occupants::test_occupant_coverage_of_the_top_fifty_only_ever_goes_up` | 24.7 |
| `test_site_data::test_the_top_row_of_each_list_carries_a_named_occupant_and_its_reason` | 23.1 |
| `test_occupants::test_the_top_ranked_row_names_a_real_business` | 22.5 |
| *next slowest* (`test_scorer` property test) | 2.0 |

That is **182 s in seven tests**, and every one of them is `pipeline.score_parcels` over Worcester. `ingest.load_municipality` alone takes about 1 s. So the cost is scoring, not loading, and one session-scoped scored frame removes almost all of it. `test_ingest.py`'s own module-scoped `worcester` fixture costs 1.15 s and is **left alone**.

**The day profile is already computed, but only inside the billed window.** `Archetype.peak_day_window(month)` returns `INTERVALS_PER_BILLED_DAY` = **52** points, 08:00–20:45 at 15-minute steps. `pipeline.score_parcel` computes `worst = argmax(shaveable)` (the month the battery works hardest) and then calls `peak_day_window(worst + 1)`, but it never stores the result. The measured half's cache (`comstock.ReducedProfile`) keeps **only** the 52 billed intervals per month plus `offpeak_max_kw`, the month's single overnight maximum. **No 24-hour shape exists for ComStock buildings without re-reading 13 timeseries from S3.**

**The design decision this forces.** The chart spans 24 hours, and draws only what the pipeline actually has:
- the 52 billed intervals, as the line;
- the billed 08:00–21:00 window, as the 5% band DESIGN.md specifies;
- the overnight hours, as a dashed line at `offpeak_max_kw` and labelled as unbilled.

Drawing an invented overnight curve would put a shape on screen that no data supports. Re-reading S3 for a line the tariff never bills is not worth the network dependency. The method page says so (Task 3).

**For every exported row, the day's peak equals that month's billed demand.** ComStock's monthly peak is the maximum over billed intervals, which is the worst day's maximum. Modelled `monthly_peaks()` is literally `peak_day_window(m).max()`. Task 3's real-data test asserts this, and it is what catches an off-by-one on `worst`.

**Payload today.** `public/data/ranked.json` is **961 KB raw, 168 KB gzipped**, 563 rows. `export.MAX_BYTES` is 5 MB. `export.SCHEMA_VERSION` is `1.3.0`; `site_data.SITE_SCHEMA_VERSION` is `1.0.0`, and the page checks only its major version.

**Addresses.** `ingest.load_municipality` returns 2,099 parcels with **zero null `site_addr`** and **6 duplicated addresses**. The assessor writes addresses upper-case and mostly abbreviated (`385 PLANTATION ST`, `183 SOUTHWEST CUTOFF`), but not always (`100 C STREET`). So both sides of a match need the same normalisation.

**Scoring status per parcel** (from `pipeline.ScoredRow` and `export.build_export`):
- in `lists` → ranked;
- `unscored_reason` set (`no_floor_area`, `no_intensity_anchor`, `no_archetype_profile`) → carried, not scored;
- `keep` false → below the 50 kW floor (the only `band_reason` `scorer.band_filter` emits);
- `keep` true and not exported → scored, but outside `TOP_N` ∪ sweet-spot rows.

`method.FLAG_MEANINGS` already holds a plain sentence for each of the three unscored reasons.

**Branches.** `feat/encoding-map` exists only locally. `origin/main` is at `048697a`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/method.py` *(modify)* | The map gap (T1), the day-chart limitation (T3), the address-box limitation (T5). |
| `tests/conftest.py` *(new)* | Session-scoped Worcester parcels and scored frame. One concern: run the expensive pipeline once. |
| `tests/test_shared_fixtures.py` *(new)* | Proves the consumers of those shared frames do not mutate them. |
| `src/shave/pipeline.py` *(modify)* | `ScoredRow` carries the worst billed day it already computes. |
| `src/shave/site_data.py` *(modify)* | `day_profile()` normalises it; payload gains `day_axis`. |
| `src/shave/export.py`, `docs/ranked-json-schema.md` *(modify)* | Schema `1.4.0`. |
| `src/shave/addresses.py` *(new)* | Address normalisation, query parsing and the static index. One file, because the index keys and the query parser must never disagree. |
| `tests/fixtures/address_cases.json` *(new)* | The normalisation cases **both** languages are held to. |
| `scripts/build_site.py` *(modify)* | Writes `addresses.json`. |
| `public/app.js` *(modify)* | `daySVG`, drawer confidence, `parseQuery`/`similarity`/`lookup`/`lookupHTML`, wiring. |
| `public/index.html`, `public/app.css` *(modify)* | The lookup form; day-chart and lookup styles. |
| `web/render.test.js` *(modify)* | Render tests for all of the above. |
| `docs/spec-coverage.md` *(modify)* | Updated when it ships (T7). |

---

## Task 1: Ship the map, and say what it cannot show

Map plan Task 4, which never landed. The map draws the assessor's parcel outline and nothing else. A reader will reasonably take a shape on a map to mean the site was assessed for fit, so the method page has to say otherwise before the map goes live.

**Files:**
- Modify: `src/shave/method.py` (the `no_siting_screen` entry in `KNOWN_GAPS`, lines 157–162)
- Test: `tests/test_method.py`
- Merge `feat/encoding-map` → `main`, deploy

**Interfaces:**
- Consumes: `method.KNOWN_GAPS`.
- Produces: `KNOWN_GAPS` entry keyed `map_shows_no_siting`, replacing `no_siting_screen`. After this task, `main` carries the map and later tasks branch from it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_method.py`:

```python
def test_the_method_page_says_what_the_map_cannot_show():
    """The map draws parcel outlines. A reader will reasonably assume a shape
    on a map means a site was assessed for fit; nothing here checks that."""
    stated = {g.key: g.statement for g in method.KNOWN_GAPS}
    assert "map_shows_no_siting" in stated, sorted(stated)
    assert "no_siting_screen" not in stated, "the two would say overlapping things"
    text = stated["map_shows_no_siting"].lower()
    assert "wall" in text
    assert "outline" in text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_method.py -k map_cannot -v`
Expected: FAIL — `AssertionError: ... 'map_shows_no_siting' in [...]`

- [ ] **Step 3: Replace the gap**

In `src/shave/method.py`, replace the whole `no_siting_screen` `Limitation(...)` entry (the first item of `KNOWN_GAPS`) with:

```python
    Limitation(
        "map_shows_no_siting",
        "The map draws the assessor's parcel outline and nothing else. A shape "
        "on it means a parcel was scored, not that a cabinet will fit: no "
        "siting screen has been run, so the longest unobstructed wall run is "
        "not computed and nothing here rules out a zero-lot-line or fully "
        "built parcel. It also cannot see loading docks, fire lanes, egress or "
        "where the service entrance is.",
    ),
```

- [ ] **Step 4: Run both suites**

```bash
uv run pytest -q
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: **955 passed, 4 deselected**; **31 passed**. `test_limitation_keys_are_unique` covers the new key.

- [ ] **Step 5: Commit on the map branch**

```bash
git add src/shave/method.py tests/test_method.py
git commit -m "docs: say what the map cannot show

The map draws the assessor's parcel outline and nothing else. A reader will
reasonably take a shape on a map to mean the site was assessed for fit. No
siting screen has been run, so nothing computes the longest clear wall run or
rules out a zero-lot-line parcel, and the map cannot see loading docks, fire
lanes or egress. Replaces no_siting_screen, which said a narrower version of
the same thing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

- [ ] **Step 6: Merge to main and push**

```bash
git checkout main
git pull --ff-only origin main
git merge --no-ff feat/encoding-map -m "merge: the encoding map

Fill opacity for annual saving, outline colour for rate class, cross-linked
with the table both ways, and a method-page gap naming what the map cannot
show.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
```

If `git pull --ff-only` refuses, stop and report: `origin/main` has moved since `048697a`, and a merge on top of unseen commits needs a person to look.

- [ ] **Step 7: Build and deploy**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

- [ ] **Step 8: Verify live**

```bash
URL="https://shave.pjayav.workers.dev"
curl -s -o /dev/null -w 'index  %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/ranked.json"
curl -s "$URL/data/method.json" | grep -c map_shows_no_siting
```

**Pass conditions, declared in advance:** both `200`; index plus `ranked.json` under **3 s** combined; the grep prints `1`. Then open the URL and confirm by eye that the map draws, clicking a parcel selects its row, and **Sweet spot** turns the picture from a few large slate parcels into many small teal ones.

- [ ] **Step 9: Branch for the rest of this plan**

```bash
git checkout -b feat/finish-and-ship
```

---

## Task 2: Score Worcester once per session

Seven integration tests each re-score 2,099 parcels, 182 s of a roughly five-minute run. They all need the same read-only frame.

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_shared_fixtures.py`
- Modify: `tests/test_site_data.py` (the five `@needs_worcester` tests, lines 105–197, and the module header lines 1–15)
- Modify: `tests/test_occupants.py` (the two `@needs_worcester` tests, lines 135–171, and lines 13–18)

**Interfaces:**
- Produces, for every later task's tests:
  - fixture `worcester_parcels` → `geopandas.GeoDataFrame` from `ingest.load_municipality`, session-scoped, **skips** when the extract is absent
  - fixture `worcester_scored` → `pandas.DataFrame` from `pipeline.score_parcels(worcester_parcels)`, session-scoped
  - Both are **read-only by convention**; `test_shared_fixtures.py` enforces it for the consumers that exist.

- [ ] **Step 1: Record the baseline**

```bash
/usr/bin/time -p uv run pytest -q 2>&1 | tail -5
```

Write down the `real` seconds. Expected: about 954 passed, 4 deselected, and somewhere near 240–300 s.

- [ ] **Step 2: Write the fixtures**

Create `tests/conftest.py`:

```python
"""Shared fixtures.

Scoring Worcester's 2,099 parcels takes about 25 seconds, and seven
integration tests each used to do it themselves -- 182 of the suite's roughly
300 seconds. These fixtures do it once per session.

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
```

- [ ] **Step 3: Write the guard test**

Create `tests/test_shared_fixtures.py`:

```python
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
```

Run: `uv run pytest tests/test_shared_fixtures.py -v`
Expected: PASS (one test, about 25 s — this is where the session's single scoring now happens).

- [ ] **Step 4: Convert `tests/test_site_data.py`**

Replace lines 1–15 (docstring through the `needs_worcester` definition) with:

```python
"""What the page reads, adapted from the one export contract."""

import json

import pandas as pd
import pytest

from shave import site_data
```

Then replace each of the five integration tests (lines 105–197). Remove the `@needs_worcester` decorator, the in-function `ingest.load_municipality` and `pipeline.score_parcels` calls, and take the fixtures as arguments. The five replacements, in file order:

```python
def test_every_field_the_page_reads_is_present_on_every_row(
    worcester_parcels, worcester_scored
):
    """The consumer contract. A rename in the pipeline or the export must
    break the build, not the browser."""
    from shave import export

    raw = export.build_export(worcester_scored, worcester_parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, worcester_scored)

    for name, rows in enriched["lists"].items():
        assert rows, f"the {name} list is empty"
        for row in rows:
            missing = set(site_data.REQUIRED_ROW_FIELDS) - set(row)
            assert not missing, f"{name} row {row['loc_id']} missing {sorted(missing)}"


def test_the_payload_is_json_serialisable_and_small_enough_to_serve(
    worcester_parcels, worcester_scored
):
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    blob = json.dumps(enriched, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < export.MAX_BYTES


def test_the_top_row_of_each_list_carries_a_named_occupant_and_its_reason(
    worcester_parcels, worcester_scored
):
    """Success criterion 2, at the point the page reads it, on BOTH lists --
    because the lists are never merged, each one's head is a first row that
    someone will read first."""
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for name, rows in enriched["lists"].items():
        top = rows[0]
        assert top["rank"] == 1
        assert top["reason"].endswith("."), name
        assert top["occupant"], f"the top {name} row must name a real business"
        assert top["occupant_source"].startswith("http"), name


def test_each_list_is_ranked_by_dollars_within_itself(
    worcester_parcels, worcester_scored
):
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for rows in enriched["lists"].values():
        usd = [r["annual_savings_usd"] for r in rows]
        assert usd == sorted(usd, reverse=True)
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))


def test_every_exported_row_carries_a_map_path(worcester_parcels, worcester_scored):
    """One Worcester parcel has no geometry and must still be exported, with
    an empty path rather than a missing key."""
    from shave import export, mapgeo

    frame = mapgeo.frame_for(worcester_parcels)
    raw = export.build_export(worcester_scored, worcester_parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, worcester_scored,
                                paths=mapgeo.paths_for(worcester_parcels, frame),
                                view_box=frame.view_box)

    assert enriched["map"]["view_box"].startswith("0 0 620 ")
    drawn = 0
    for rows in enriched["lists"].values():
        for row in rows:
            assert "path" in row, f"{row['loc_id']} has no path key"
            if row["path"]:
                assert row["path"].startswith("M") and row["path"].endswith("Z")
                drawn += 1
    assert drawn > 0, "nothing would be drawn"
```

Confirm with `grep -c needs_worcester tests/test_site_data.py`, which must print `0`.

- [ ] **Step 5: Convert `tests/test_occupants.py`**

Delete lines 13–18 (`WORCESTER_DIR = ...` through the `needs_worcester = pytest.mark.skipif(...)` block). Keep the `Path` import; `write_occupants` uses it. Replace the two integration tests with:

```python
def test_the_top_ranked_row_names_a_real_business(worcester_scored):
    """Success criterion 2, as a test.

    The spec: 'The top-ranked site is a real, named Massachusetts operating
    business at a verifiable address, with a one-sentence checkable reason.'
    If the head of the ranking is a holding company, the deliverable does not
    meet its own bar and this must fail.
    """
    scored = occupants.attach(worcester_scored)
    top = scored[scored["keep"]].nlargest(1, "annual_savings_usd").iloc[0]

    assert top["occupant"], f"top-ranked parcel {top['loc_id']} has no resolved occupant"
    assert top["occupant_source"], "and no source for it"


def test_occupant_coverage_of_the_top_fifty_only_ever_goes_up(worcester_scored):
    """A ratchet, not a target.

    Resolving the top 50 is hand work and is not finished: the spec asks for
    40 of 50 and the table holds RESOLVED_TOP_50_TODAY. This test exists so
    that number cannot quietly fall -- a row deleted or a ranking change that
    drops a resolved parcel out of the top 50 fails here. Raise the constant
    as rows land; when it reaches SPEC_TARGET_TOP_50 the spec's bar is met.
    """
    stats = occupants.coverage(worcester_scored, top_n=50)

    assert stats["top_n_resolved"] >= RESOLVED_TOP_50_TODAY, (
        f"coverage fell to {stats['top_n_resolved']} from {RESOLVED_TOP_50_TODAY}"
    )
    assert RESOLVED_TOP_50_TODAY <= SPEC_TARGET_TOP_50
```

Confirm `grep -n "needs_worcester\|WORCESTER_DIR" tests/test_occupants.py` prints nothing.

- [ ] **Step 6: Measure**

```bash
/usr/bin/time -p uv run pytest -q --durations=5 2>&1 | tail -12
```

**Pass conditions, declared in advance:**
- **956 passed, 4 deselected** (955 + the guard test);
- no single test *call* over 5 s, and exactly one *setup* near 25 s (the session fixture);
- `real` at least **140 s below** the Step 1 baseline.

Report both `real` figures.

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_shared_fixtures.py tests/test_site_data.py tests/test_occupants.py
git commit -m "test: score Worcester once per session

Seven integration tests each re-scored all 2,099 parcels, 182 seconds of the
suite. Scoring, not loading, was the cost: load_municipality takes about one
second, score_parcels about twenty-five. Both are now session fixtures.

A shared fixture turns one test's in-place edit into every later test's wrong
input, so a guard test runs every consumer the suite uses against the shared
frames and asserts nothing moved.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 3: Carry the worst billed day out of the scorer

`score_parcel` already picks the month the battery works hardest and reads that month's peak-day window. It throws the window away. Keep it, normalise it with the held level and the overnight maximum on one scale, and publish the tariff axis so the page never restates 08:00 or 21:00.

**Files:**
- Modify: `src/shave/pipeline.py` (`ScoredRow` lines 45–67, `score_parcel` lines 128–149, `_unscored` lines 152–175)
- Modify: `src/shave/site_data.py`
- Modify: `src/shave/export.py` (`SCHEMA_VERSION`)
- Modify: `src/shave/method.py` (`LIMITATIONS`)
- Modify: `docs/ranked-json-schema.md`
- Test: `tests/test_pipeline.py`, `tests/test_site_data.py`, `tests/test_method.py`

**Interfaces:**
- Consumes: `worcester_parcels`, `worcester_scored` (Task 2).
- Produces:
  - `ScoredRow.peak_day_month: int` — 1–12; `0` on an unscored row
  - `ScoredRow.peak_day_kw: tuple[float, ...]` — `INTERVALS_PER_BILLED_DAY` values, kW, 1 dp; `()` on an unscored row
  - `ScoredRow.peak_day_held_kw: float` — that month's billed peak less what the battery removes, kW, 1 dp
  - `site_data.day_profile(row: Mapping) -> dict` with keys `day_kw: list[float]`, `day_held: float`, `day_offpeak: float`, all on one 0–1 scale
  - every enriched row gains `day_kw`, `day_held`, `day_offpeak`
  - enriched payload gains `day_axis: {"window_start_hour": int, "window_end_hour": int, "step_hours": float}`
  - `export.SCHEMA_VERSION == "1.4.0"`

- [ ] **Step 1: Write the failing pipeline tests**

Append to `tests/test_pipeline.py`:

```python
def _july_spike_archetype() -> FixtureArchetype:
    """Flat at 100 kW every month, except a one-hour 400 kW spike in July."""
    windows = np.full((12, INTERVALS_PER_BILLED_DAY), 100.0)
    windows[6, 20:24] = 400.0
    return FixtureArchetype(
        monthly_peak_kw=windows.max(axis=1),
        windows=windows,
        offpeak_max_kw=np.full(12, 60.0),
        source="comstock",
    )


def test_the_peak_day_is_the_month_the_battery_works_hardest():
    """July's spike is where the most kW come off, so July is the day the
    drawer draws -- the same month the recharge test already reads."""
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _july_spike_archetype())

    assert row.peak_day_month == 7
    assert len(row.peak_day_kw) == INTERVALS_PER_BILLED_DAY
    assert max(row.peak_day_kw) == pytest.approx(row.monthly_billed_demand_kw[6])


def test_the_held_level_is_the_billed_peak_less_what_the_battery_removes():
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _july_spike_archetype())

    m = row.peak_day_month - 1
    expected = row.monthly_billed_demand_kw[m] - row.monthly_shaveable_kw[m]
    assert row.peak_day_held_kw == pytest.approx(expected, abs=0.1)
    # 400 kW spike, 250 kW power cap: the battery holds it at 150.
    assert row.peak_day_held_kw == pytest.approx(150.0, abs=0.1)


def test_an_unscored_row_carries_no_day_rather_than_a_fake_one():
    gdf = pd.DataFrame([{"loc_id": "L9", "sqft": None, "archetype": "warehouse",
                         "source": "comstock"}])

    out = pipeline.score_parcels(gdf, archetype_factory=lambda p: _flat_archetype(100.0))

    assert out["peak_day_month"].iloc[0] == 0
    assert tuple(out["peak_day_kw"].iloc[0]) == ()
    assert out["peak_day_held_kw"].iloc[0] == 0.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -k "peak_day or held_level or no_day" -v`
Expected: FAIL — `AttributeError: 'ScoredRow' object has no attribute 'peak_day_month'`

- [ ] **Step 3: Carry the day through `pipeline.py`**

In `ScoredRow`, insert three fields between `months_at_power_cap: int` and `flags: tuple[str, ...] = ()`. They have no defaults, so they must come before `flags`:

```python
    months_at_power_cap: int
    #: The month the battery works hardest, 1-12, and that month's worst billed
    #: day inside the peak window. This is the day the drawer draws. 0 and ()
    #: on an unscored row: there is no day to draw, and inventing one is worse.
    peak_day_month: int
    peak_day_kw: tuple[float, ...]
    #: The level the battery holds that day's billed peak to.
    peak_day_held_kw: float
    flags: tuple[str, ...] = ()
```

In `score_parcel`, add these three keyword arguments to the `return ScoredRow(...)` call, directly after `months_at_power_cap=months_at_cap,`:

```python
        peak_day_month=worst + 1,
        peak_day_kw=tuple(
            round(float(v), 1) for v in archetype.peak_day_window(worst + 1)
        ),
        peak_day_held_kw=round(float(peaks[worst] - shaveable[worst]), 1),
```

In `_unscored`, add after `months_at_power_cap=0,`:

```python
        peak_day_month=0,
        peak_day_kw=(),
        peak_day_held_kw=0.0,
```

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS, including the three new tests.

- [ ] **Step 4: Write the failing `site_data` tests**

Add to the imports at the top of `tests/test_site_data.py`:

```python
from shave.archetype import INTERVALS_PER_BILLED_DAY, STEP_HOURS
from shave.assumptions import PEAK_HOUR_END, PEAK_HOUR_START
```

Append:

```python
def test_day_profile_puts_load_held_level_and_overnight_on_one_scale():
    """The page draws all three on one axis and does no arithmetic, so they
    must arrive already sharing a scale."""
    row = {"peak_day_kw": [100.0, 400.0, 200.0], "peak_day_held_kw": 150.0,
           "offpeak_max_kw": 80.0}

    out = site_data.day_profile(row)

    assert out["day_kw"] == [0.25, 1.0, 0.5]
    assert out["day_held"] == pytest.approx(0.375)
    assert out["day_offpeak"] == pytest.approx(0.2)


def test_an_overnight_load_above_the_billed_peak_sets_the_scale():
    """A 3 a.m. process is free under this tariff, so overnight load can exceed
    the billed peak. It must not be drawn off the top of the chart."""
    out = site_data.day_profile(
        {"peak_day_kw": [50.0, 100.0], "peak_day_held_kw": 60.0, "offpeak_max_kw": 200.0}
    )

    assert out["day_offpeak"] == 1.0
    assert max(out["day_kw"]) == 0.5


def test_a_row_with_no_day_yields_an_empty_series_not_a_crash():
    assert site_data.day_profile({"offpeak_max_kw": 0.0}) == {
        "day_kw": [], "day_held": 0.0, "day_offpeak": 0.0,
    }


def test_the_payload_carries_the_tariff_axis_so_the_page_restates_nothing():
    payload = {"schema_version": "1.4.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}

    out = site_data.enrich(payload, _scored_stub())

    assert out["day_axis"] == {
        "window_start_hour": PEAK_HOUR_START,
        "window_end_hour": PEAK_HOUR_END,
        "step_hours": STEP_HOURS,
    }


def test_every_exported_row_carries_its_worst_billed_day(
    worcester_parcels, worcester_scored
):
    """The day's own peak IS that month's billed demand. If `worst` were off by
    one month, this is the assertion that would say so."""
    from shave import export

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)

    for name, rows in enriched["lists"].items():
        for row in rows:
            m = row["peak_day_month"]
            assert 1 <= m <= 12, f"{name} {row['loc_id']} month {m}"
            assert len(row["day_kw"]) == INTERVALS_PER_BILLED_DAY
            assert max(row["peak_day_kw"]) == pytest.approx(
                row["monthly_billed_demand_kw"][m - 1], abs=0.1
            ), f"{name} {row['loc_id']}"
            assert 0.0 <= row["day_held"] <= max(row["day_kw"]) + 1e-3
            assert max(row["day_kw"] + [row["day_offpeak"]]) == pytest.approx(1.0)
```

- [ ] **Step 5: Run them to verify they fail**

Run: `uv run pytest tests/test_site_data.py -k "day" -v`
Expected: FAIL — `AttributeError: module 'shave.site_data' has no attribute 'day_profile'`

- [ ] **Step 6: Implement `day_profile` and the axis**

In `src/shave/site_data.py`, add imports below `from shave import method, occupants`:

```python
from shave.archetype import STEP_HOURS
from shave.assumptions import PEAK_HOUR_END, PEAK_HOUR_START
```

Replace `ADDED_ROW_FIELDS` and `REQUIRED_ROW_FIELDS` with:

```python
#: What this module adds on top of an exported row.
ADDED_ROW_FIELDS: tuple[str, ...] = (
    "occupant", "occupant_source", "window_kw", "shaveable_kw", "path",
    "day_kw", "day_held", "day_offpeak",
)

#: What the page reads off every row. Everything but ADDED_ROW_FIELDS comes
#: from `export.build_export`; the test asserts all of it is present, so a
#: rename in the pipeline or the export breaks the build, not the browser.
REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "loc_id", "rank", "reason", "archetype", "source", "sqft", "avg_12mo_kw",
    "peak_kw", "peak_to_avg", "rate_class", "demand_charge_per_kw",
    "annual_savings_usd", "shaved_fraction", "confidence", "confidence_reasons",
    "flags", "sweet_spot", "site_addr", "city", "owner", "use_desc",
    "monthly_billed_demand_kw", "peak_day_month", "peak_day_held_kw",
) + ADDED_ROW_FIELDS
```

Add below `window_series`:

```python
def day_profile(row: Mapping) -> dict:
    """The worst billed day, normalised for a 24-hour chart.

    Three things share one scale: the billed-window load, the level the
    battery holds it to, and the overnight maximum. Normalising them together
    is what lets the page draw all three on one axis without arithmetic of its
    own.

    The scale is the larger of the day's peak and the overnight maximum. A
    3 a.m. process is free under this tariff, so overnight load can exceed the
    billed peak, and a chart scaled to the window alone would draw it off the
    top.

    Only the maximum is known overnight, not the shape: the measured half's
    cache keeps the 52 billed intervals and nothing between 21:00 and 08:00.
    The page draws that maximum as a dashed line and says it is unbilled.
    """
    window = [float(v) for v in (row.get("peak_day_kw") or [])]
    offpeak = float(row.get("offpeak_max_kw") or 0.0)
    held = float(row.get("peak_day_held_kw") or 0.0)
    top = max(window + [offpeak])
    if not window or top <= 0.0:
        return {"day_kw": [], "day_held": 0.0, "day_offpeak": 0.0}
    return {
        "day_kw": [round(v / top, 3) for v in window],
        "day_held": round(held / top, 3),
        "day_offpeak": round(offpeak / top, 3),
    }
```

In `enrich`, inside the row loop directly after the `row["path"] = ...` line, add:

```python
            row.update(day_profile(row))
```

And directly after `payload["site_schema_version"] = SITE_SCHEMA_VERSION`, add:

```python
    # The tariff's own hours, so the page never restates 08:00 or 21:00.
    payload["day_axis"] = {
        "window_start_hour": PEAK_HOUR_START,
        "window_end_hour": PEAK_HOUR_END,
        "step_hours": STEP_HOURS,
    }
```

In `src/shave/export.py`:

```python
SCHEMA_VERSION = "1.4.0"
```

Run: `uv run pytest tests/test_site_data.py tests/test_export.py -v`
Expected: PASS.

- [ ] **Step 7: State the chart's limit on the method page**

Append to `tests/test_method.py`:

```python
def test_the_method_page_says_the_day_chart_is_one_day_and_blind_overnight():
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "day_chart_is_one_day" in stated, sorted(stated)
    text = stated["day_chart_is_one_day"].lower()
    assert "overnight" in text
    assert "not billed" in text
```

Run: `uv run pytest tests/test_method.py -k day_chart -v` — expected FAIL (`AssertionError`).

Add as the **last** entry of `LIMITATIONS` in `src/shave/method.py`:

```python
    Limitation(
        "day_chart_is_one_day",
        "The day chart in the detail panel is one day: the worst billed day of "
        "the month the battery works hardest. Inside 08:00-21:00 it is the "
        "archetype's own fifteen-minute load. Overnight only the maximum is "
        "known, not the shape, so it is drawn as a flat dashed line -- and "
        "overnight load is not billed under this tariff at any magnitude.",
    ),
```

Run: `uv run pytest tests/test_method.py -v` — expected PASS.

- [ ] **Step 8: Document schema 1.4.0**

In `docs/ranked-json-schema.md`, change `**Current version: \`1.3.0\`**` to `**Current version: \`1.4.0\`**`, and add directly below the `**1.3.0**` paragraph:

```markdown
**1.4.0** — rows gain `peak_day_month` (int, 1–12), `peak_day_kw` (float[52], kW)
and `peak_day_held_kw` (float, kW): the worst billed day of the month the battery
works hardest, 08:00–20:45 at fifteen-minute steps, and the level the battery holds
it to. The site payload additionally carries `day_kw`, `day_held` and `day_offpeak`
on each row — the same day, the held level and `offpeak_max_kw` normalised to one
shared 0–1 scale — and a top-level `day_axis` object
`{window_start_hour, window_end_hour, step_hours}` taken from `assumptions.py`.
MINOR: nothing was removed or retyped.
```

In the "Load and money" table, add after the `months_at_power_cap` row:

```markdown
| `peak_day_month` | int | — | The month with the most shaveable kW. `0` on an unscored row. |
| `peak_day_kw` | float[52] | kW | That month's worst billed day, 08:00–20:45. Its maximum equals `monthly_billed_demand_kw[peak_day_month-1]`. |
| `peak_day_held_kw` | float | kW | The level the battery holds that day's peak to. |
```

- [ ] **Step 9: Run everything and rebuild**

```bash
uv run pytest -q
uv run python scripts/build_site.py
uv run python -c "
import json, gzip
b = open('public/data/ranked.json','rb').read(); d = json.loads(b)
rows = [r for l in d['lists'].values() for r in l]
print('schema', d['schema_version'], '| axis', d['day_axis'])
print('rows', len(rows), '| with a day', sum(1 for r in rows if len(r['day_kw']) == 52))
print('raw KB', len(b)//1024, '| gzip KB', len(gzip.compress(b))//1024)
"
```

**Pass conditions, declared in advance:** **965 passed, 4 deselected** (956 + 3 pipeline + 5 site_data + 1 method); schema `1.4.0`; all 563 rows carry a 52-point day; `ranked.json` under **1,500 KB raw** and **320 KB gzipped**. Report the figures.

- [ ] **Step 10: Commit**

```bash
git add src/shave/pipeline.py src/shave/site_data.py src/shave/export.py src/shave/method.py \
        docs/ranked-json-schema.md tests/test_pipeline.py tests/test_site_data.py tests/test_method.py
git commit -m "feat: carry the worst billed day out of the scorer

score_parcel already chose the month the battery works hardest and read that
month's peak-day window for the recharge test, then discarded it. ScoredRow now
keeps it, with the level the battery holds it to.

site_data normalises the window, the held level and the overnight maximum onto
one scale, because the page draws all three on one axis and does no arithmetic.
The scale is the larger of the day's peak and the overnight maximum: a 3 a.m.
process is free under this tariff and can exceed the billed peak. The tariff's
hours travel in the payload so the page never restates them.

The measured cache keeps no overnight shape, only its maximum. The method page
says so rather than the chart inventing a curve.

Schema 1.4.0, MINOR.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 4: Draw the day in the drawer, with its confidence tier

The spec's step 9 asks the drawer for *"24h load sparkline with the 08:00–21:00 window shaded… confidence tier"*. The chart spends `--signal` on the shaved peak, the first of DESIGN.md's three permitted uses. It does that with an SVG `clipPath` above the held line, so the page draws a shape rather than computing `max(v, held)`.

**Files:**
- Modify: `public/app.js` (`drawerHTML`, `state`, `select`, `boot`)
- Modify: `public/app.css` (drawer section)
- Test: `web/render.test.js`

**Interfaces:**
- Consumes: row fields `day_kw`, `day_held`, `day_offpeak`, `peak_day_month`, `peak_day_held_kw`, `monthly_billed_demand_kw`, `confidence`, `confidence_reasons`; payload `day_axis` (Task 3).
- Produces:
  - `export function daySVG(row, axis, w, h) -> string`
  - `drawerHTML(row, flagMeanings, dayAxis)` — third parameter added; omitting it renders the "no day profile" message, never a crash

- [ ] **Step 1: Write the failing tests**

In `web/render.test.js`, add `daySVG` to the import list at the top of the file:

```js
import {
  chipClass,
  daySVG,
  drawerHTML,
  fmtMoney,
  methodHTML,
  rowHTML,
  sparkSVG,
} from "../public/app.js";
```

Append:

```js
const DAY_AXIS = { window_start_hour: 8, window_end_hour: 21, step_hours: 0.25 };
const DAY_ROW = {
  ...ROW,
  peak_day_month: 7,
  peak_day_held_kw: 150,
  monthly_billed_demand_kw: [100, 100, 100, 100, 100, 100, 400, 100, 100, 100, 100, 100],
  day_kw: Array.from({ length: 52 }, (_, i) => (i >= 20 && i < 24 ? 1 : 0.25)),
  day_held: 0.375,
  day_offpeak: 0.2,
};

describe("daySVG", () => {
  const svg = daySVG(DAY_ROW, DAY_AXIS, 302, 84);

  it("shades exactly the billed window on a 24-hour axis", () => {
    // x(h) = 1 + h/24 * 300, so 08:00 is 101.0 and 13 hours is 162.5 wide.
    expect(svg).toMatch(/<rect class="billed" x="101\.0" y="0" width="162\.5"/);
  });

  it("draws every billed interval and no invented overnight curve", () => {
    const pts = svg.match(/<polyline points="([^"]+)"/)[1].trim().split(" ");
    expect(pts).toHaveLength(52);
    expect(svg.match(/<polyline/g)).toHaveLength(1);
  });

  it("spends the accent once, on the peak above the held level", () => {
    expect(svg.match(/var\(--signal\)/g)).toHaveLength(1);
    expect(svg).toContain('clip-path="url(#dayshaved)"');
    // plot height 70, y(v) = 1 + (1 - v) * 68, so held 0.375 sits at 43.5
    expect(svg).toContain('<clipPath id="dayshaved"><rect x="0" y="0" width="302" height="43.5"/>');
  });

  it("marks the overnight maximum on both sides of the window and says it is not billed", () => {
    expect(svg.match(/stroke-dasharray="2 2"/g)).toHaveLength(2);
    expect(svg).toContain("not billed");
  });

  it("names the month, the billed peak and the held level for a screen reader", () => {
    expect(svg).toMatch(/aria-label="[^"]*July[^"]*400 kW[^"]*150 kW/);
  });

  it("says so plainly when there is no day, and never draws NaN", () => {
    const empty = daySVG({ ...ROW, day_kw: [] }, DAY_AXIS, 302, 84);
    expect(empty).toContain("No day profile");
    expect(empty).not.toContain("NaN");
    expect(daySVG(DAY_ROW, undefined, 302, 84)).toContain("No day profile");
  });
});

describe("drawerHTML confidence", () => {
  it("shows the confidence tier and names the predicates that failed", () => {
    const html = drawerHTML(
      { ...DAY_ROW, confidence: "LOW", confidence_reasons: ["within_single_meter_cap"] },
      {},
      DAY_AXIS,
    );
    expect(html).toContain('class="chip lo"');
    expect(html).toContain("within single meter cap");
    expect(html).toContain('class="billed"');
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `daySVG is not a function`.

- [ ] **Step 3: Add `daySVG` to `public/app.js`**

Insert directly after `sparkSVG`:

```js
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function hh(hour) {
  return String(hour).padStart(2, "0") + ":00";
}

// The worst billed day, on a 24-hour axis. Every value arrives normalised to
// one shared scale by site_data.day_profile, and the tariff's hours arrive in
// `axis`, so this only maps hours and 0-1 values to pixels. The shaved peak is
// the load drawn a second time in --signal and clipped to the region above the
// held line: a shape, not a subtraction.
export function daySVG(row, axis, w, h) {
  const a = ((row && row.day_kw) || []).map((v) => Number(v) || 0);
  if (!a.length || !axis) {
    return `<p class="dayempty">No day profile for this site.</p>`;
  }
  const pad = 1;
  const ph = h - 14; // plot height; the bottom 14px carry the hour labels
  const x = (hour) => (pad + (hour / 24) * (w - 2 * pad)).toFixed(1);
  const y = (v) => (pad + (1 - v) * (ph - 2)).toFixed(1);

  const start = axis.window_start_hour;
  const end = axis.window_end_hour;
  const step = axis.step_hours;
  const base = (ph - pad).toFixed(1);
  const pts = a.map((v, i) => `${x(start + i * step)},${y(v)}`);
  const lastX = x(start + (a.length - 1) * step);
  const area = `M${x(start)},${base} L${pts.join(" L")} L${lastX},${base} Z`;
  const held = y(Number(row.day_held) || 0);
  const night = y(Number(row.day_offpeak) || 0);

  const month = MONTHS[(row.peak_day_month || 0) - 1] || "";
  const peakKw = (row.monthly_billed_demand_kw || [])[(row.peak_day_month || 0) - 1];
  const label =
    `Worst billed day${month ? " in " + month : ""}: billed peak ` +
    `${Math.round(Number(peakKw) || 0)} kW, held to ` +
    `${Math.round(Number(row.peak_day_held_kw) || 0)} kW. The shaded band is the ` +
    `billed ${hh(start)} to ${hh(end)} window; the dashed line outside it is the ` +
    `overnight maximum, which is not billed.`;

  const tick = (hour, anchor) =>
    `<text x="${x(hour)}" y="${h - 2}" text-anchor="${anchor}" font-size="9" ` +
    `font-family="var(--mono)" fill="var(--ink-3)">${hh(hour)}</text>`;

  return (
    `<svg class="day" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" ` +
    `aria-label="${esc(label)}">` +
    `<defs><clipPath id="dayshaved"><rect x="0" y="0" width="${w}" height="${held}"/></clipPath></defs>` +
    `<rect class="billed" x="${x(start)}" y="0" ` +
    `width="${(((end - start) / 24) * (w - 2 * pad)).toFixed(1)}" height="${ph}" ` +
    `fill="var(--ink-2)" opacity=".05"/>` +
    `<line x1="${x(0)}" y1="${night}" x2="${x(start)}" y2="${night}" ` +
    `stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="2 2"/>` +
    `<line x1="${x(end)}" y1="${night}" x2="${x(24)}" y2="${night}" ` +
    `stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="2 2"/>` +
    `<path d="${area}" fill="var(--ink-2)" opacity=".16"/>` +
    `<path d="${area}" fill="var(--signal)" opacity=".55" clip-path="url(#dayshaved)"/>` +
    `<polyline points="${pts.join(" ")}" fill="none" stroke="var(--ink-2)" ` +
    `stroke-width="1.1" stroke-linejoin="round"/>` +
    `<line x1="${x(start)}" y1="${held}" x2="${lastX}" y2="${held}" ` +
    `stroke="var(--ink)" stroke-width="1" stroke-dasharray="3 2"/>` +
    tick(0, "start") + tick(start, "middle") + tick(end, "middle") + tick(24, "end") +
    `</svg>`
  );
}
```

- [ ] **Step 4: Put the day and the confidence tier in the drawer**

Replace the signature and the two lines that open the drawer body in `drawerHTML`:

```js
export function drawerHTML(row, flagMeanings, dayAxis) {
```

Inside, before `return (`, add:

```js
  const failed = (row.confidence_reasons || []).map((r) => r.replace(/_/g, " ")).join(" · ");
  const month = MONTHS[(row.peak_day_month || 0) - 1];
```

Replace these two existing lines:

```js
    `<div class="dayprofile">${sparkSVG(row.window_kw, 300, 60)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Billed demand by month &middot; peak marked</div>` +
```

with:

```js
    `<div class="dayprofile">${daySVG(row, dayAxis, 302, 84)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Worst billed day` +
    `${month ? " &middot; " + esc(month) : ""} &middot; shaded = billed window ` +
    `&middot; accent = what the battery removes</div>` +
    `<div class="dayprofile">${sparkSVG(row.window_kw, 302, 36)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Billed demand by month &middot; peak marked</div>` +
```

Inside the `<dl class="kv">`, directly after the `Load shape` entry, add:

```js
    `<div><dt>Confidence</dt><dd><span class="chip ${chipClass(row.confidence)}">` +
    `${esc(row.confidence)}</span>${failed ? " failed: " + esc(failed) : ""}</dd></div>` +
```

- [ ] **Step 5: Wire the axis through**

In the `state` object literal, add `dayAxis: null,`.

In `boot()`, directly after `state.viewBox = ...`, add:

```js
  state.dayAxis = ranked.day_axis || null;
```

In `select(id)`, change the drawer line to:

```js
  $("#drawer").innerHTML = drawerHTML(row, (state.method || {}).flag_meanings, state.dayAxis);
```

- [ ] **Step 6: Style it**

In `public/app.css`, replace `.dayprofile{margin-top:10px}` with:

```css
.dayprofile{margin-top:10px}
/* The drawer is 45fr of the split and one column on a phone; the chart scales
   down with it rather than forcing the panel wider. */
.day{display:block; max-width:100%; height:auto}
.dayempty{margin:0; font-size:12px; color:var(--ink-2)}
```

- [ ] **Step 7: Run both suites**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
uv run pytest -q
```
Expected: **38 passed** (31 + 6 `daySVG` + 1 drawer confidence); Python **965 passed, 4 deselected**.

- [ ] **Step 8: Look at it**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler dev --port 8787
```

Open `http://127.0.0.1:8787/`. Confirm by eye, in **both** light and dark system themes:
- rank 1's drawer shows a 24-hour chart with a faint band from 08:00 to 21:00;
- the accent fill sits only above the dashed held line, at the spike;
- the overnight dashed line appears left and right of the band and nowhere inside it;
- the modelled list's rank 1 (UMass Chan, a flat load) shows little or no accent — that is the thesis;
- the Confidence entry shows a chip and the failed predicates;
- at 400px wide the chart shrinks inside the drawer and the body does not scroll sideways.

- [ ] **Step 9: Commit**

```bash
git add public/app.js public/app.css web/render.test.js
git commit -m "feat: the drawer draws the worst billed day

The spec's step 9 asks for a 24-hour load profile with the 08:00-21:00 window
shaded. The billed intervals are the line; the band is the window; the accent
is the load clipped above the level the battery holds it to, so the page draws
a shape rather than computing one. Overnight is a dashed maximum labelled as
unbilled, because that is all the pipeline knows there.

The confidence tier, a chip on the row until now, is in the drawer with the
predicates that failed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 5: A static address index

D5: *"What a domain expert does thirty seconds in is check a building they already know."* The index is a JSON file built next to `ranked.json`, so no database sits on the request path. Normalisation exists twice, here to build keys and in `app.js` to read a query, because the page cannot import Python. Both are held to one cases file, and the abbreviation table travels inside the index so the page never keeps its own copy.

**Files:**
- Create: `src/shave/addresses.py`
- Create: `tests/fixtures/address_cases.json`
- Create: `tests/test_addresses.py`
- Modify: `scripts/build_site.py`
- Modify: `src/shave/method.py` (`LIMITATIONS`)
- Test: `tests/test_method.py`

**Interfaces:**
- Consumes: `worcester_parcels`, `worcester_scored` (Task 2); `enriched["lists"]` from `site_data.enrich`; `method.FLAG_MEANINGS`; `pipeline.UNSCORED_REASONS`; `assumptions.MIN_AVG_DEMAND_KW`, `assumptions.RATED_POWER_KW`.
- Produces:
  - `addresses.INDEX_SCHEMA_VERSION = "1.0.0"`
  - `addresses.ABBREVIATIONS: dict[str, str]`
  - `addresses.normalize(text) -> str`
  - `addresses.parse_query(query: str, towns: Sequence[str]) -> dict[str, str]` with keys `street`, `town`
  - `addresses.STATUS_SENTENCES: dict[str, str]` keyed `ranked`, `not_exported`, `below_floor`, plus every `pipeline.UNSCORED_REASONS`
  - `addresses.build_index(parcels, scored, lists, towns) -> dict` with keys `index_schema_version`, `towns: list[str]`, `abbreviations`, `statuses`, `entries: list[dict]`
  - each entry: `key, addr, loc_id, status, list, rank, source, archetype, sqft, avg_12mo_kw, rate_class, annual_savings_usd, confidence`
  - build writes `public/data/addresses.json`
  - `tests/fixtures/address_cases.json` shape: `{"towns": [...], "abbreviations": {...}, "cases": [{"query", "street", "town"}]}` — Task 6's vitest reads it

- [ ] **Step 1: Write the shared cases file**

Create `tests/fixtures/address_cases.json`:

```json
{
  "towns": ["WORCESTER"],
  "abbreviations": {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "DRIVE": "DR",
    "BOULEVARD": "BLVD", "PLACE": "PL", "LANE": "LN", "COURT": "CT",
    "PARKWAY": "PKWY", "HIGHWAY": "HWY", "SQUARE": "SQ", "TERRACE": "TER",
    "CIRCLE": "CIR", "TURNPIKE": "TPKE", "EXTENSION": "EXT",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"
  },
  "cases": [
    {"query": "385 Plantation Street, Worcester, MA 01605", "street": "385 PLANTATION ST", "town": "WORCESTER"},
    {"query": "385 plantation st", "street": "385 PLANTATION ST", "town": ""},
    {"query": "385 Plantation St Worcester MA 01605-1234", "street": "385 PLANTATION ST", "town": "WORCESTER"},
    {"query": "100 C Street", "street": "100 C ST", "town": ""},
    {"query": "12 Main St., Springfield, MA", "street": "12 MAIN ST", "town": "SPRINGFIELD"},
    {"query": "183 Southwest Cutoff", "street": "183 SOUTHWEST CUTOFF", "town": ""},
    {"query": "  1001  Millbury  Avenue ", "street": "1001 MILLBURY AVE", "town": ""},
    {"query": "100 Route 9", "street": "100 ROUTE 9", "town": ""},
    {"query": "", "street": "", "town": ""}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_addresses.py`:

```python
"""The address index: a reader checks a building they already know."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from shave import addresses, method, pipeline

CASES = json.loads(Path("tests/fixtures/address_cases.json").read_text())


def test_the_shared_cases_file_carries_the_same_abbreviations_as_the_code():
    """app.js is tested against this file's table and reads the index's copy
    at run time. If the two drifted, the page would parse differently from
    the keys it is matching against."""
    assert CASES["abbreviations"] == addresses.ABBREVIATIONS


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["query"] or "empty")
def test_a_pasted_address_parses_to_its_street_and_town(case):
    got = addresses.parse_query(case["query"], CASES["towns"])
    assert got == {"street": case["street"], "town": case["town"]}


def test_normalize_leaves_nothing_to_match_for_a_missing_address():
    assert addresses.normalize(None) == ""
    assert addresses.normalize(pd.NA) == ""
    assert addresses.normalize(float("nan")) == ""
    assert addresses.normalize("100 C STREET") == "100 C ST"


def _frames():
    parcels = pd.DataFrame([
        {"loc_id": "A", "site_addr": "385 PLANTATION ST", "confidence": "MED"},
        {"loc_id": "B", "site_addr": "70 JAMES STREET", "confidence": "HIGH"},
        {"loc_id": "C", "site_addr": "10 ELBRIDGE ST", "confidence": "LOW"},
        {"loc_id": "D", "site_addr": "440 LINCOLN ST", "confidence": "HIGH"},
        {"loc_id": "E", "site_addr": pd.NA, "confidence": "HIGH"},
    ])
    base = {"source": "comstock", "archetype": "warehouse", "rate_class": "G-2"}
    scored = pd.DataFrame([
        {**base, "loc_id": "A", "sqft": 50_000.0, "avg_12mo_kw": 300.0,
         "annual_savings_usd": 30_000.0, "keep": True, "unscored_reason": None},
        {**base, "loc_id": "B", "sqft": 2_000.0, "avg_12mo_kw": 12.0,
         "annual_savings_usd": 400.0, "keep": False, "unscored_reason": None},
        {**base, "loc_id": "C", "sqft": float("nan"), "avg_12mo_kw": 0.0,
         "annual_savings_usd": 0.0, "keep": False, "unscored_reason": "no_floor_area"},
        {**base, "loc_id": "D", "sqft": 20_000.0, "avg_12mo_kw": 90.0,
         "annual_savings_usd": 2_000.0, "keep": True, "unscored_reason": None},
        {**base, "loc_id": "E", "sqft": 20_000.0, "avg_12mo_kw": 90.0,
         "annual_savings_usd": 2_000.0, "keep": True, "unscored_reason": None},
    ])
    lists = {"comstock": [{"loc_id": "A", "rank": 1}], "modeled": []}
    return parcels, scored, lists


def test_every_screened_parcel_is_indexed_with_what_happened_to_it():
    """A match must say ranked, screened out, or unscored -- never just
    'not found' for a building the pipeline actually looked at."""
    parcels, scored, lists = _frames()

    index = addresses.build_index(parcels, scored, lists, towns=["WORCESTER"])
    by_id = {e["loc_id"]: e for e in index["entries"]}

    assert by_id["A"]["status"] == "ranked"
    assert (by_id["A"]["list"], by_id["A"]["rank"]) == ("comstock", 1)
    assert by_id["B"]["status"] == "below_floor"
    assert by_id["B"]["key"] == "70 JAMES ST"
    assert by_id["C"]["status"] == "no_floor_area"
    assert by_id["C"]["sqft"] is None, "NaN floor area must not become a number"
    assert by_id["D"]["status"] == "not_exported"
    assert (by_id["D"]["list"], by_id["D"]["rank"]) == ("", None)
    assert index["towns"] == ["WORCESTER"]
    assert index["abbreviations"] == addresses.ABBREVIATIONS
    assert index["index_schema_version"] == addresses.INDEX_SCHEMA_VERSION


def test_a_parcel_with_no_address_is_left_out_rather_than_indexed_under_nothing():
    parcels, scored, lists = _frames()
    index = addresses.build_index(parcels, scored, lists, towns=["WORCESTER"])
    assert "E" not in {e["loc_id"] for e in index["entries"]}
    assert all(e["key"] for e in index["entries"])


def test_every_status_a_parcel_can_carry_has_a_sentence():
    expected = {"ranked", "not_exported", "below_floor", *pipeline.UNSCORED_REASONS}
    assert set(addresses.STATUS_SENTENCES) == expected
    for reason in pipeline.UNSCORED_REASONS:
        assert addresses.STATUS_SENTENCES[reason] == method.FLAG_MEANINGS[reason]


def test_every_exported_worcester_row_is_found_by_its_own_address(
    worcester_parcels, worcester_scored
):
    """Criterion 7 at the build: paste the address of anything on the list
    and the index finds that parcel exactly."""
    from shave import export, site_data

    enriched = site_data.enrich(
        export.build_export(worcester_scored, worcester_parcels,
                            town={"name": "Worcester", "town_id": 348}),
        worcester_scored)
    index = addresses.build_index(worcester_parcels, worcester_scored,
                                  enriched["lists"], towns=["WORCESTER"])

    keys = {}
    for e in index["entries"]:
        keys.setdefault(e["key"], set()).add(e["loc_id"])
    for name, rows in enriched["lists"].items():
        for row in rows:
            q = addresses.parse_query(f"{row['site_addr']}, Worcester, MA", ["WORCESTER"])
            assert row["loc_id"] in keys.get(q["street"], set()), (name, row["site_addr"])

    assert len(index["entries"]) == len(worcester_parcels)  # zero null addresses today
    blob = json.dumps(index, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < 700 * 1024
    for e in index["entries"]:
        for field in ("sqft", "avg_12mo_kw", "annual_savings_usd"):
            v = e[field]
            assert v is None or not (isinstance(v, float) and math.isnan(v))
```

Run: `uv run pytest tests/test_addresses.py -v`
Expected: FAIL — `ImportError: cannot import name 'addresses' from 'shave'`

- [ ] **Step 3: Write `src/shave/addresses.py`**

```python
"""A static address index, so a reader can check a building they already know.

Design review D5 calls this the verification moment: what a domain expert does
thirty seconds in is look up a site they know. It ships as a JSON file built
beside ranked.json, not a database, so it cannot break when a free tier sleeps.

Normalisation exists twice -- here, to build the keys, and in app.js, to read a
query -- because the page cannot import Python. Both are held to one set of
cases in tests/fixtures/address_cases.json, and the abbreviation table travels
inside the index so the page never keeps a copy of its own.

Every parcel the pipeline screened is indexed with what happened to it. A
building that was looked at and screened out is a finding, and answering "not
found" for it would be a silence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

import pandas as pd

from shave import method, pipeline
from shave.assumptions import MIN_AVG_DEMAND_KW, RATED_POWER_KW

INDEX_SCHEMA_VERSION = "1.0.0"

#: USPS-style suffixes and directionals. The assessor mostly abbreviates and
#: occasionally does not ("100 C STREET"), and readers paste either form.
ABBREVIATIONS: dict[str, str] = {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "DRIVE": "DR",
    "BOULEVARD": "BLVD", "PLACE": "PL", "LANE": "LN", "COURT": "CT",
    "PARKWAY": "PKWY", "HIGHWAY": "HWY", "SQUARE": "SQ", "TERRACE": "TER",
    "CIRCLE": "CIR", "TURNPIKE": "TPKE", "EXTENSION": "EXT",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
}

_SPLIT = re.compile(r"[^A-Z0-9]+")
_STATE = frozenset({"MA", "MASS", "MASSACHUSETTS"})
#: A ZIP or the +4 of a ZIP+4. Four or five digits only, so "ROUTE 9" survives.
_ZIPPISH = re.compile(r"^\d{4,5}$")

STATUS_SENTENCES: dict[str, str] = {
    "ranked": "On the ranked list.",
    "not_exported": (
        "Scored and above the demand floor, but outside the rows this page "
        "publishes. The saving shown is the scorer's own figure for it."
    ),
    "below_floor": (
        f"Screened out: its estimated 12-month average demand is under "
        f"{MIN_AVG_DEMAND_KW:.0f} kW, so a {RATED_POWER_KW:.0f} kW battery has no "
        f"peak worth shaving here. That is a finding, not a missing row."
    ),
    **{reason: method.FLAG_MEANINGS[reason] for reason in pipeline.UNSCORED_REASONS},
}


def _tokens(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text.upper()) if t]


def normalize(text) -> str:
    """Upper-case, punctuation to spaces, suffixes abbreviated. "" if absent."""
    if not isinstance(text, str):
        return ""
    return " ".join(ABBREVIATIONS.get(t, t) for t in _tokens(text))


def parse_query(query: str, towns: Sequence[str]) -> dict[str, str]:
    """Split a pasted address into a normalised street and a town.

    With a comma: everything before the first comma is the street, and what
    follows, less any state or ZIP, is the town. Without one: trailing state
    and ZIP tokens are peeled off, then a covered town name at the end is
    taken as the town. At least one street token always survives the peel, so
    a bare number is not erased.

    app.js `parseQuery` is the same function. Change both, and the cases file.
    """
    text = query if isinstance(query, str) else ""
    head, comma, tail = text.partition(",")
    street = _tokens(head)
    town: list[str] = []
    if comma:
        town = [t for t in _tokens(tail) if t not in _STATE and not _ZIPPISH.match(t)]
    else:
        while len(street) > 1 and (street[-1] in _STATE or _ZIPPISH.match(street[-1])):
            street.pop()
        for name in towns:
            words = _tokens(name)
            if len(street) > len(words) and street[-len(words):] == words:
                street, town = street[: -len(words)], words
                break
    return {
        "street": " ".join(ABBREVIATIONS.get(t, t) for t in street),
        "town": " ".join(town),
    }


def _number(value, digits: int):
    """A JSON-safe rounded number, or None for missing and NaN."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return round(f, digits) if digits else int(round(f))


def build_index(
    parcels: pd.DataFrame,
    scored: pd.DataFrame,
    lists: Mapping[str, list[dict]],
    towns: Sequence[str],
) -> dict:
    """One entry per screened parcel that has an address.

    `lists` is the export's two ranked lists. Their ranks are copied, never
    recomputed, and the lists stay separate: an entry names which list it is
    on, and there is no cross-list rank.
    """
    exported = {
        row["loc_id"]: (name, row["rank"])
        for name, rows in lists.items()
        for row in rows
    }
    detail = pd.DataFrame(parcels)[["loc_id", "site_addr", "confidence"]]
    merged = scored.merge(detail, on="loc_id", how="left")

    entries = []
    for rec in merged.to_dict("records"):
        key = normalize(rec.get("site_addr"))
        if not key:
            continue
        loc_id = str(rec["loc_id"])
        unscored = rec.get("unscored_reason")
        list_name, rank = "", None
        if loc_id in exported:
            status = "ranked"
            list_name, rank = exported[loc_id]
        elif isinstance(unscored, str) and unscored:
            status = unscored
        elif not bool(rec.get("keep")):
            status = "below_floor"
        else:
            status = "not_exported"
        entries.append({
            "key": key,
            "addr": str(rec["site_addr"]),
            "loc_id": loc_id,
            "status": status,
            "list": list_name,
            "rank": rank,
            "source": str(rec.get("source") or ""),
            "archetype": str(rec.get("archetype") or ""),
            "sqft": _number(rec.get("sqft"), 0),
            "avg_12mo_kw": _number(rec.get("avg_12mo_kw"), 1),
            "rate_class": str(rec.get("rate_class") or ""),
            "annual_savings_usd": _number(rec.get("annual_savings_usd"), 0),
            "confidence": rec["confidence"] if isinstance(rec.get("confidence"), str) else "",
        })
    entries.sort(key=lambda e: (e["key"], e["loc_id"]))

    return {
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "towns": [t.upper() for t in towns],
        "abbreviations": dict(ABBREVIATIONS),
        "statuses": dict(STATUS_SENTENCES),
        "entries": entries,
    }
```

Note `_number(..., 0)` returns an `int`, so the unit test's `by_id["C"]["sqft"] is None` holds for NaN, and a real floor area comes out whole.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_addresses.py -v`
Expected: PASS — 9 cases from the parametrised test plus 6 others, **15 tests**.

- [ ] **Step 5: State the box's limit on the method page**

Append to `tests/test_method.py`:

```python
def test_the_method_page_says_what_the_address_box_searches():
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    assert "address_box_is_the_screen_only" in stated, sorted(stated)
    text = stated["address_box_is_the_screen_only"].lower()
    assert "residential" in text
    assert "not screened" in text
```

Run: `uv run pytest tests/test_method.py -k address_box -v` — expected FAIL.

Add as the **last** entry of `LIMITATIONS` in `src/shave/method.py`:

```python
    Limitation(
        "address_box_is_the_screen_only",
        "The address box searches the commercial and industrial parcels this "
        "screen looked at, by the assessor's own site address. A residential "
        "parcel, a building recorded under a different street number, or an "
        "address in a town not yet processed returns no match -- which means "
        "not screened, not screened out.",
    ),
```

Run: `uv run pytest tests/test_method.py -v` — expected PASS.

- [ ] **Step 6: Write the index at build time**

In `scripts/build_site.py`, change the import line to:

```python
from shave import addresses, export, ingest, mapgeo, pipeline, regression, site_data
```

Directly after the `(out / "method.json").write_text(...)` call, add:

```python
    # Loaded by the page only on first search, so the ranked list's first
    # paint never waits for it.
    index = addresses.build_index(
        parcels, scored, enriched["lists"], towns=[args.town_name]
    )
    (out / "addresses.json").write_text(
        json.dumps(index, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
```

Change the size-report loop to:

```python
    for name in ("ranked.json", "method.json", "addresses.json"):
```

Update the module docstring's last sentence to: `Writes public/data/ranked.json (the enriched export), public/data/method.json and public/data/addresses.json.`

- [ ] **Step 7: Run everything and rebuild**

```bash
uv run pytest -q
uv run python scripts/build_site.py
uv run python -c "
import json, gzip, collections
b = open('public/data/addresses.json','rb').read(); d = json.loads(b)
print('entries', len(d['entries']), '| raw KB', len(b)//1024, '| gzip KB', len(gzip.compress(b))//1024)
print(collections.Counter(e['status'] for e in d['entries']))
"
```

**Pass conditions, declared in advance:** **981 passed, 4 deselected** (965 + 15 addresses + 1 method); 2,099 entries; `addresses.json` under **700 KB raw**; statuses sum to 2,099, with `ranked` equal to the number of unique `loc_id`s across both lists and `no_intensity_anchor` 6 and `no_floor_area` 1 (the method page's own unscored counts). Report the figures.

- [ ] **Step 8: Commit**

```bash
git add src/shave/addresses.py tests/fixtures/address_cases.json tests/test_addresses.py \
        scripts/build_site.py src/shave/method.py tests/test_method.py
git commit -m "feat: a static address index

D5's verification moment: a reader checks a building they already know. The
index is a JSON file beside ranked.json, not a database, so nothing on the
request path can sleep.

Every screened parcel is indexed with what happened to it -- ranked, below the
floor, unscored with its reason, or scored but outside the published rows. A
building the pipeline looked at and screened out is a finding; answering 'not
found' for it would be a silence. Ranks are copied from the two lists, never
recomputed, and there is no cross-list rank.

Normalisation lives in Python and in app.js, held to one shared cases file, and
the abbreviation table ships inside the index.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 6: The address box

**Files:**
- Modify: `public/app.js` (pure functions before the wiring section; listeners in `boot()`)
- Modify: `public/index.html` (between `.toolbar` and `.split`)
- Modify: `public/app.css`
- Test: `web/render.test.js`

**Interfaces:**
- Consumes: `addresses.json` shape and `tests/fixtures/address_cases.json` (Task 5); `select(id)`, `#src-cs`, `#src-md`, `#view-all`.
- Produces:
  - `export function parseQuery(query, towns, abbrev) -> {street, town}`
  - `export function similarity(a, b) -> number` in [0, 1], trigram Jaccard
  - `export function lookup(index, query) -> {kind, matches, town}` where `kind` is one of `"empty" | "outside" | "exact" | "approximate" | "none"`
  - `export function lookupHTML(result, index) -> string`

- [ ] **Step 1: Write the failing tests**

At the very top of `web/render.test.js`, below the existing `vitest` import, add:

```js
import { readFileSync } from "node:fs";
```

Append:

```js
import { lookup, lookupHTML, parseQuery, similarity } from "../public/app.js";

const ADDRESS_CASES = JSON.parse(
  readFileSync(new URL("../tests/fixtures/address_cases.json", import.meta.url), "utf8"),
);

describe("parseQuery", () => {
  it("parses every shared case exactly as the Python index builder does", () => {
    for (const c of ADDRESS_CASES.cases) {
      expect(parseQuery(c.query, ADDRESS_CASES.towns, ADDRESS_CASES.abbreviations), c.query)
        .toEqual({ street: c.street, town: c.town });
    }
  });
});

describe("similarity", () => {
  it("is 1 for identical strings and 0 for strings sharing nothing", () => {
    expect(similarity("385 PLANTATION ST", "385 PLANTATION ST")).toBe(1);
    expect(similarity("ABC", "XYZ")).toBe(0);
  });
});

const INDEX = {
  index_schema_version: "1.0.0",
  towns: ["WORCESTER"],
  abbreviations: ADDRESS_CASES.abbreviations,
  statuses: {
    ranked: "On the ranked list.",
    below_floor: "Screened out: under the floor. That is a finding, not a missing row.",
    no_floor_area: "No floor area.",
  },
  entries: [
    { key: "385 PLANTATION ST", addr: "385 PLANTATION ST", loc_id: "F_1", status: "ranked",
      list: "modeled", rank: 1, source: "modeled", archetype: "university", sqft: 1628495,
      avg_12mo_kw: 3957.7, rate_class: "G-3", annual_savings_usd: 31440, confidence: "MED" },
    { key: "70 JAMES ST", addr: "70 JAMES ST", loc_id: "F_2", status: "below_floor",
      list: "", rank: null, source: "comstock", archetype: "warehouse", sqft: 2000,
      avg_12mo_kw: 12, rate_class: "G-2", annual_savings_usd: 400, confidence: "HIGH" },
    { key: "10 ELBRIDGE ST", addr: "10 ELBRIDGE ST", loc_id: "F_3", status: "no_floor_area",
      list: "", rank: null, source: "comstock", archetype: "warehouse", sqft: null,
      avg_12mo_kw: 0, rate_class: "G-2", annual_savings_usd: 0, confidence: "LOW" },
  ],
};

describe("lookup", () => {
  it("finds an exact match whatever form the address was pasted in", () => {
    const r = lookup(INDEX, "385 Plantation Street, Worcester, MA 01605");
    expect(r.kind).toBe("exact");
    expect(r.matches.map((m) => m.loc_id)).toEqual(["F_1"]);
  });

  it("offers the nearest address for a typo, and calls it approximate", () => {
    const r = lookup(INDEX, "385 Plantaton St");
    expect(r.kind).toBe("approximate");
    expect(r.matches[0].loc_id).toBe("F_1");
  });

  it("recognises an address in a town that is not covered", () => {
    const r = lookup(INDEX, "12 Main St, Springfield, MA");
    expect(r.kind).toBe("outside");
    expect(r.town).toBe("SPRINGFIELD");
  });

  it("returns none when nothing is close", () => {
    expect(lookup(INDEX, "9999 Nowhere Rd").kind).toBe("none");
  });

  it("does nothing for an empty query", () => {
    expect(lookup(INDEX, "   ").kind).toBe("empty");
  });
});

describe("lookupHTML", () => {
  it("says an uncovered town was not screened, which differs from screened out", () => {
    const html = lookupHTML(lookup(INDEX, "12 Main St, Springfield"), INDEX);
    expect(html).toContain("SPRINGFIELD");
    expect(html).toMatch(/not been screened/);
    expect(html).toContain("WORCESTER");
  });

  it("labels fuzzy matches as approximate", () => {
    expect(lookupHTML(lookup(INDEX, "385 Plantaton St"), INDEX)).toMatch(/approximate/i);
  });

  it("makes a ranked match a button that knows its list, and a screened-out one a statement", () => {
    const ranked = lookupHTML(lookup(INDEX, "385 Plantation St"), INDEX);
    expect(ranked).toMatch(/<button[^>]*class="hit"[^>]*data-id="F_1"[^>]*data-list="modeled"/);
    expect(ranked).toContain("Rank 1");

    const out = lookupHTML(lookup(INDEX, "70 James Street"), INDEX);
    expect(out).not.toContain("<button");
    expect(out).toContain("That is a finding, not a missing row.");
  });

  it("escapes the address, which came from an assessor record", () => {
    const evil = { ...INDEX, entries: [{ ...INDEX.entries[1], key: "1 X ST",
      addr: '<img src=x onerror="alert(1)">' }] };
    const html = lookupHTML(lookup(evil, "1 X St"), evil);
    expect(html).not.toContain("<img");
  });

  it("says what the index holds when nothing matches", () => {
    const html = lookupHTML(lookup(INDEX, "9999 Nowhere Rd"), INDEX);
    expect(html).toContain("3 addressed parcels");
    expect(html).toMatch(/residential/);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `lookup is not a function`.

- [ ] **Step 3: Add the pure functions to `public/app.js`**

Insert directly before the `// wiring.` separator block:

```js
// ---------------------------------------------------------------------------
// address lookup. parseQuery is src/shave/addresses.py parse_query in
// JavaScript; both are tested against tests/fixtures/address_cases.json, and
// the abbreviation table comes from the index rather than living here.
// ---------------------------------------------------------------------------

const SUPPORTED_INDEX_MAJOR = "1";
const STATE_TOKENS = new Set(["MA", "MASS", "MASSACHUSETTS"]);
const ZIPPISH = /^\d{4,5}$/;
//: A fuzzy candidate must share at least this share of trigrams to be offered.
const APPROX_MIN = 0.4;
const APPROX_MAX_RESULTS = 5;

function addrTokens(text) {
  return String(text || "").toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
}

export function parseQuery(query, towns, abbrev) {
  const text = typeof query === "string" ? query : "";
  const cut = text.indexOf(",");
  let street = addrTokens(cut < 0 ? text : text.slice(0, cut));
  let town = [];
  if (cut >= 0) {
    town = addrTokens(text.slice(cut + 1)).filter((t) => !STATE_TOKENS.has(t) && !ZIPPISH.test(t));
  } else {
    while (
      street.length > 1 &&
      (STATE_TOKENS.has(street[street.length - 1]) || ZIPPISH.test(street[street.length - 1]))
    ) {
      street.pop();
    }
    for (const name of towns || []) {
      const words = addrTokens(name);
      const tail = street.slice(street.length - words.length);
      if (street.length > words.length && words.every((w, i) => tail[i] === w)) {
        street = street.slice(0, street.length - words.length);
        town = words;
        break;
      }
    }
  }
  const map = abbrev || {};
  return {
    street: street.map((t) => (Object.hasOwn(map, t) ? map[t] : t)).join(" "),
    town: town.join(" "),
  };
}

function trigrams(s) {
  const padded = `  ${s} `;
  const out = new Set();
  for (let i = 0; i + 3 <= padded.length; i++) out.add(padded.slice(i, i + 3));
  return out;
}

export function similarity(a, b) {
  const A = trigrams(a);
  const B = trigrams(b);
  let shared = 0;
  for (const t of A) if (B.has(t)) shared++;
  const union = A.size + B.size - shared;
  return union ? shared / union : 0;
}

export function lookup(index, query) {
  const q = parseQuery(query, index.towns, index.abbreviations);
  if (!q.street) return { kind: "empty", matches: [], town: q.town };
  if (q.town && !index.towns.includes(q.town)) {
    return { kind: "outside", matches: [], town: q.town };
  }
  const exact = index.entries.filter((e) => e.key === q.street);
  if (exact.length) return { kind: "exact", matches: exact, town: q.town };
  const near = index.entries
    .map((e) => ({ e, s: similarity(q.street, e.key) }))
    .filter((c) => c.s >= APPROX_MIN)
    .sort((a, b) => b.s - a.s || (a.e.key < b.e.key ? -1 : a.e.key > b.e.key ? 1 : 0))
    .slice(0, APPROX_MAX_RESULTS)
    .map((c) => c.e);
  return { kind: near.length ? "approximate" : "none", matches: near, town: q.town };
}

function hitHTML(entry, index) {
  const sentence = (index.statuses || {})[entry.status] || "";
  const listName = entry.list === "modeled" ? "Modeled industrial" : "ComStock-backed";
  const facts = [
    entry.archetype ? `${esc(entry.archetype)} (${esc(entry.source)})` : "",
    entry.sqft != null ? `${Number(entry.sqft).toLocaleString("en-US")} sq ft` : "",
    entry.rate_class ? `rate ${esc(entry.rate_class)}` : "",
    entry.status !== "ranked" && entry.annual_savings_usd
      ? `estimated ${fmtMoney(entry.annual_savings_usd)}/yr`
      : "",
  ].filter(Boolean).join(" &middot; ");
  const body =
    `<div class="addr">${esc(entry.addr)}</div>` +
    `<div class="status">${entry.status === "ranked"
      ? `Rank ${esc(entry.rank)} &middot; ${esc(listName)} &middot; ` +
        `${fmtMoney(entry.annual_savings_usd)}/yr &middot; open it in the list`
      : esc(sentence)}</div>` +
    (facts ? `<div class="status">${facts}</div>` : "");
  // Only a ranked parcel has a row to jump to. Anything else is a statement.
  return entry.status === "ranked"
    ? `<li><button type="button" class="hit" data-id="${esc(entry.loc_id)}" ` +
        `data-list="${esc(entry.list)}">${body}</button></li>`
    : `<li><div class="hit">${body}</div></li>`;
}

export function lookupHTML(result, index) {
  const towns = (index.towns || []).map(esc).join(", ");
  if (result.kind === "empty") return "";
  if (result.kind === "outside") {
    return (
      `<p class="reason">That address is in ${esc(result.town)}, and this screen ` +
      `covers ${towns} only. It has not been screened &mdash; which is ` +
      `different from screened out.</p>`
    );
  }
  if (result.kind === "none") {
    return (
      `<p class="reason">No screened parcel matches that address. The index holds ` +
      `the assessor's own site addresses for ${index.entries.length.toLocaleString("en-US")} ` +
      `addressed parcels in ${towns}, commercial and industrial only; a residential ` +
      `parcel, or a building recorded under a different street number, will not ` +
      `appear.</p>`
    );
  }
  const head =
    result.kind === "exact"
      ? `<div class="eyebrow">Exact match</div>`
      : `<div class="eyebrow">No exact match &middot; nearest addresses, approximate &mdash; check the street number</div>`;
  return `${head}<ul class="hits">${result.matches.map((e) => hitHTML(e, index)).join("")}</ul>`;
}
```

- [ ] **Step 4: Add the form to `public/index.html`**

Directly after the closing `</div>` of `<div class="toolbar">` and before `<div class="split">`, insert:

```html
    <form class="lookup" id="lookup" role="search" aria-label="Check a building by address">
      <label for="addr" class="eyebrow">Check a building you know</label>
      <div class="lookup-row">
        <input id="addr" name="addr" type="search" autocomplete="off" spellcheck="false"
               placeholder="e.g. 385 Plantation St, Worcester">
        <button type="submit">Look up</button>
      </div>
      <div id="lookup-result" aria-live="polite"></div>
    </form>
```

- [ ] **Step 5: Wire it in `boot()`**

Directly before `function select(id) {`, add:

```js
let addressIndex = null;

async function loadAddressIndex() {
  if (addressIndex) return addressIndex;
  const idx = await (await fetch("/data/addresses.json")).json();
  if (String(idx.index_schema_version || "").split(".")[0] !== SUPPORTED_INDEX_MAJOR) {
    throw new Error(`address index ${idx.index_schema_version} not supported`);
  }
  addressIndex = idx;
  return idx;
}

// A ranked match opens in the list it belongs to. The lists are never merged,
// so the source toggle moves to that list rather than the row joining this one.
function jumpTo(list, id) {
  $(list === "modeled" ? "#src-md" : "#src-cs").click();
  $("#view-all").click();
  select(id);
  const tr = $(`#rows tr[data-id="${CSS.escape(id)}"]`);
  if (tr) {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    tr.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    tr.focus({ preventScroll: true });
  }
}
```

In `boot()`, directly before the `$$(".tab").forEach(...)` block, add:

```js
  $("#lookup").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#addr");
    const out = $("#lookup-result");
    input.setAttribute("aria-busy", "true");
    out.innerHTML = `<p class="whysplit">Loading the address index&hellip;</p>`;
    try {
      const idx = await loadAddressIndex();
      out.innerHTML = lookupHTML(lookup(idx, input.value), idx);
    } catch (err) {
      out.innerHTML =
        `<p class="reason">The address index could not be loaded. The ranked list ` +
        `and the map are unaffected &mdash; they are served as separate static data.</p>`;
    } finally {
      input.removeAttribute("aria-busy");
    }
  });
  $("#lookup-result").addEventListener("click", (e) => {
    const hit = e.target.closest("button.hit[data-id]");
    if (hit) jumpTo(hit.dataset.list, hit.dataset.id);
  });
```

- [ ] **Step 6: Style it**

Append to `public/app.css`, before the method section's `/* ---------- method ---------- */` comment:

```css
/* ---------- address lookup ---------- */
/* D5: the verification moment. Ink, never --signal: the accent is not a button. */
.lookup{margin-top:12px; padding:10px 12px; background:var(--surface);
  border:1px solid var(--rule); border-radius:var(--r)}
.lookup-row{display:flex; gap:8px; margin-top:6px; flex-wrap:wrap}
.lookup input{flex:1 1 220px; min-width:0; min-height:44px; padding:0 10px;
  font-family:var(--mono); font-size:13px; color:var(--ink); background:var(--ground);
  border:1px solid var(--rule-strong); border-radius:var(--r)}
.lookup input[aria-busy="true"]{border-color:var(--ink-3)}
.lookup button[type="submit"]{min-height:44px; padding:0 14px; font:inherit; font-size:13px;
  font-weight:600; color:var(--ground); background:var(--ink); border:0;
  border-radius:var(--r); cursor:pointer}
#lookup-result{margin-top:10px}
#lookup-result:empty{display:none}
#lookup-result .reason{margin:0; max-width:78ch}
.hits{list-style:none; margin:6px 0 0; padding:0; display:grid; gap:6px}
.hit{display:block; width:100%; text-align:left; font:inherit; color:inherit;
  background:var(--surface-2); border:1px solid var(--rule); border-radius:var(--r);
  padding:8px 10px}
button.hit{cursor:pointer; min-height:44px}
button.hit:hover{border-color:var(--rule-strong)}
.hit .addr{font-family:var(--mono); font-size:12.5px; font-weight:600}
.hit .status{font-size:12px; color:var(--ink-2); margin-top:2px}
```

- [ ] **Step 7: Run both suites**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
uv run pytest -q
```
Expected: render **50 passed** (38 + 1 parseQuery + 1 similarity + 5 lookup + 5 lookupHTML); Python **981 passed, 4 deselected**.

- [ ] **Step 8: Use it**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler dev --port 8787
```

At `http://127.0.0.1:8787/`, with the browser's network panel open, confirm:
- `addresses.json` is **not** requested on page load, only on the first **Look up**;
- `360 Plantation St, Worcester` shows an exact match on the modelled list; clicking it switches to **Modeled industrial**, selects that row and scrolls to it;
- `385 Plantaton St` offers approximate matches and says so;
- `12 Main St, Springfield, MA` says Springfield has not been screened;
- the address of a parcel known to be below the floor (pick any `below_floor` entry from `addresses.json`) shows the screened-out sentence and no button;
- blocking `addresses.json` in the network panel and searching shows the "could not be loaded… unaffected" message while the list and map keep working;
- at 400px wide, the input and button stack without horizontal scroll, and both are at least 44px tall.

- [ ] **Step 9: Commit**

```bash
git add public/app.js public/index.html public/app.css web/render.test.js
git commit -m "feat: the address box

Paste an address, get what the screen did with that building: its row, a
screened-out finding, or the reason it could not be scored. A ranked match
opens in the list it belongs to -- the source toggle moves, the lists do not
merge. A typo gets nearest matches labelled approximate; an uncovered town is
told it has not been screened, which is not the same as screened out.

The index loads only on first search, so the ranked list's first paint does
not wait for it, and if it fails the message says the list and map still work.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 7: Ship it and update the coverage review

**Files:**
- Modify: `docs/spec-coverage.md`
- Merge `feat/finish-and-ship` → `main`, deploy

**Interfaces:**
- Consumes: everything above.
- Produces: the live site with the day chart and the address box; a coverage document that matches it.

- [ ] **Step 1: Final full run**

```bash
uv run pytest -q
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: **981 passed, 4 deselected**; **50 passed**. If either differs, stop and reconcile before touching `main`.

- [ ] **Step 2: Update `docs/spec-coverage.md`**

Make exactly these edits:

1. Header table: `Tests` row → `**981 Python** (4 network-marked, deselected) + **50 render**`. `Coverage of spec stages` → `**9 of 12 numbered steps complete**, 2 partial`. `Success criteria` → `**6 of 7**`.
2. Replace the blockquote under the header table (the "five minutes" paragraph) with:
   `> The Python suite scores Worcester once per session (`tests/conftest.py`). It used to re-run the 2,099-parcel pipeline in seven separate tests.`
3. Stage 1 table, row 9: state `✅`, notes `Ranked table → drawer (24-hour worst billed day with the billed window shaded, source label, confidence tier and failed predicates, lineage) → method page. The siting slot waits on step 3.`
4. "Additionally shipped" table, D2 row: `✅ merged and live`.
5. Delete the section "### The gap in step 9" and its three paragraphs and bullet list.
6. Stage 2 table, row 10: `✅ static index over every screened parcel, no database. Loaded on first search.`
7. Success criteria table, row 7: `✅` with evidence `Worcester. Exact, approximate and uncovered-town answers; every exported row is found by its own address (test_addresses.py).`
8. Test plan table, `Worker E2E` row: change `Two paths are moot (no Supabase, no address box).` to `One path is moot (no Supabase). The address box's outside-covered-towns path is tested in render.test.js.`
9. Pending table: delete rows 1, 2, 5 and 8, and renumber the remaining rows 1–4 (occupants, siting, towns, MECOLS).
10. Add to the end of "Deliberate divergences from the spec":

```markdown
**7. The drawer's day chart is twenty-four hours wide but only thirteen hours deep.** The spec
asks for a 24-hour load sparkline. The measured half's cache keeps the 52 billed intervals and
the month's overnight maximum, not the overnight shape, and re-reading 13 timeseries from S3
for a line the tariff never bills was not worth a network dependency in the build. The chart
draws the billed intervals as a line, the overnight maximum as a dashed line labelled unbilled,
and the method page says so.
```

- [ ] **Step 3: Commit the document**

```bash
git add docs/spec-coverage.md
git commit -m "docs: coverage review after the day chart and the address box

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

- [ ] **Step 4: Merge, push, deploy**

```bash
git checkout main
git pull --ff-only origin main
git merge --no-ff feat/finish-and-ship -m "merge: suite runtime, the day chart and the address box

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

If `git pull --ff-only` refuses, stop and report rather than merging over unseen commits.

- [ ] **Step 5: Verify live**

```bash
URL="https://shave.pjayav.workers.dev"
curl -s -o /dev/null -w 'index     %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked    %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/ranked.json"
curl -s -o /dev/null -w 'addresses %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/addresses.json"
curl -s "$URL/data/ranked.json" | uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['schema_version'], d['day_axis'])"
```

**Pass conditions, declared in advance:** all three `200`; index plus `ranked.json` under **3 s** combined (success criterion 1 — `addresses.json` is not part of first load); schema `1.4.0` with `day_axis` present.

Then, in a browser on the live URL: rank 1's drawer shows the day chart; **Look up** `360 Plantation St, Worcester` finds UMass Chan and opens it on the modelled list; the Method tab lists `day_chart_is_one_day`, `address_box_is_the_screen_only` and `map_shows_no_siting`.

---

## What the next plans pick up

| Next | Carries | Est. |
|---|---|---|
| **Siting** — `STRUCTURES_POLY` join and the wall-run screen | Unblocks step 2's roofprint fallback, fills the drawer's siting slot, adds the hatched wall run the map legend omits, and retires `map_shows_no_siting`. | 4.5h |
| **New Bedford and Chicopee** | L3 download, crosswalk pass, `county_gisjoin` for Bristol and Hampden. `addresses.build_index` already takes a `towns` list; `build_site.py` still takes one town per run and will need to write one index across all three. | 2h |
| **MECOLS class-shape check** | Criterion 4. Re-fetch the workbook first. | 1h + fetch |
| Occupant resolution, 46 remaining | Hand work; the ratchet rises as rows land. | 3h |

**One measurement worth a look, not a task here.** `pipeline.score_parcels` over Worcester takes about **25 s** in the suite, but its docstring says *"Measured at 2.1 s for Worcester's 1,446 ComStock rows."* Two candidates, neither verified:
- `modeled.peak_kw_for` calls `implied_load_factor`, which evaluates the day shape for all 365 days, once per modelled parcel, even though it depends only on the archetype's parameters;
- `ModeledArchetype._annual_max_shape` recomputes twelve full-day shapes on every `peak_day_window` call, and `score_parcel` makes 26 of those per parcel.

Profile before changing anything. The docstring is either stale or describing the ComStock half only, and either way it should be corrected.

---

## Self-Review

**Spec coverage.**
- Step 9's *"24h load sparkline with the 08:00–21:00 window shaded"* → Tasks 3–4. The overnight shape is a declared divergence, stated on the method page (T3 Step 7) and in the coverage review (T7 divergence 7).
- Step 9's *"confidence tier"* → Task 4 Step 4.
- Step 9's *"siting result"* → deferred to the siting plan; the drawer adds no empty slot for it.
- D5 and step 10, the address box as a static index with no database → Tasks 5–6.
- Interaction States, Address lookup:
  - *Loading*, "inline spinner in the field" → `aria-busy` on the input plus an inline loading line (T6 Step 5).
  - *Error* → the message names what still works. The spec's "database is paused" wording does not apply, because there is no database.
  - *Partial*, "fuzzy match offers nearest, labelled as approximate" → `lookup` `approximate` and its label in `lookupHTML`.
- Test plan, *"address outside covered towns"* → `lookup` `outside` tests.
- Success criterion 7 → Task 5's real-data test plus Task 6's browser check.
- Criterion 1, re-verified after each deploy → T1 Step 8, T7 Step 5.
- The map's remaining step (map plan Task 4) → Task 1.
- Pending item 8, suite runtime → Task 2, with a measured pass condition.

**Placeholder scan.** No TBD or "handle edge cases". Every code step carries its code, and every test step its test. Two defects were caught and fixed in review:
- Task 2 miscounted `test_site_data.py` as six integration tests. Lines 105–197 hold five (field presence, JSON size, top-row occupant, dollar ranking, map path), and the task now says five and gives a `grep -c` that must print 0.
- `lookupHTML`'s uncovered-town copy did not contain the phrase its own test matches (`not been screened`). The copy now does.

Task 7 Step 2 gives exact replacement text rather than "update the counts".

**Type consistency.**
- `ScoredRow.peak_day_month/peak_day_kw/peak_day_held_kw` (T3) are read by `site_data.day_profile` (T3) through `row.get(...)` and by `daySVG` (T4) as `row.peak_day_month` and `row.peak_day_held_kw`.
- `day_profile` returns `day_kw/day_held/day_offpeak`, exactly the names `daySVG` reads.
- `payload.day_axis` keys `window_start_hour/window_end_hour/step_hours` (T3) match `daySVG`'s `axis.*` and the test's `DAY_AXIS`.
- `drawerHTML(row, flagMeanings, dayAxis)` (T4) is called from `select` with `state.dayAxis`, set in `boot`.
- `addresses.build_index` entry keys (T5) match what `hitHTML`/`lookupHTML` read (T6): `key, addr, loc_id, status, list, rank, source, archetype, sqft, rate_class, annual_savings_usd`. `avg_12mo_kw` and `confidence` are carried but not rendered.
- `index.towns/abbreviations/statuses/entries` (T5) match `lookup`/`lookupHTML` (T6).
- `parse_query(query, towns)` (Python) and `parseQuery(query, towns, abbrev)` (JS) share `tests/fixtures/address_cases.json`, whose `abbreviations` is asserted equal to `addresses.ABBREVIATIONS`.
- `worcester_parcels`/`worcester_scored` (T2) are consumed in T3 and T5 tests by those exact names.

**Count arithmetic.**
- Python: 954 → T1 +1 = 955 → T2 +1 = 956 → T3 +3 pipeline +5 site_data +1 method = 965 → T5 +15 addresses (9 parametrised + 6) +1 method = **981**.
- Render: 31 → T4 +7 = 38 → T6 +12 = **50**.

**Risks worth naming.**
- The `clipPath` id `dayshaved` is document-global. It is safe only while exactly one drawer exists; a second `daySVG` on the page would share it.
- `Object.hasOwn` needs ES2022, which every browser the site targets supports. Vitest on Node 22 supports it too.
- `feat/encoding-map` has never been pushed, so Task 1's merge is the first time that work reaches `origin`.
