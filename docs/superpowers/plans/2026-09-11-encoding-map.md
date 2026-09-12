# Encoding Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the ranked list on a map that argues for the thesis rather than decorating it — where flipping to the sweet-spot view visibly inverts the picture.

**Architecture:** Parcel polygons are simplified and projected into SVG coordinates **at build time**, so each row carries a ready-to-inject `path` string and the page still computes nothing. The map renders as one inline SVG with two encodings — fill opacity for annual saving, outline colour for rate class — cross-linked with the table in both directions. Restoring the two-column split is one CSS declaration, because the class name and ordering rule were kept when the single-column version shipped.

**Tech Stack:** Python 3.11, geopandas/shapely (already present), vanilla ES2020 + inline SVG, vitest, Cloudflare Workers static assets.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` — the "Design (added by /plan-design-review)" section, specifically **D2 ("The map is back in the build")**. Also the job posting quoted in the spec's Problem Statement: *"Turn scattered infrastructure data into a living map of opportunity… Make maps feel intelligent, not decorative."*

**Design system:** `DESIGN.md`. The approved mockup's map markup is reproduced in Task 2 Step 3.

**Prior plans:** all five complete. The site is live at **https://shave.pjayav.workers.dev**, repo at **https://github.com/Prashanthvara/shave**, `main` at `2a13d50`.

## Why this one next

The job posting's headline ask is a map, and design review D2 put it back into the build after it had silently fallen out across four revisions. Everything else outstanding — the address box, the siting screen, two more towns — is additive. This is the one piece whose absence is visible in the brief itself.

## The design decision this plan makes, and why it departs from DESIGN.md

`DESIGN.md` says the map *"has to argue against itself to be worth building: the largest parcel on screen (Union Station Logistics, 164,000 sq ft) is slate-outlined and faint, and ranks fifth. A reader learns 'big is not the same as good' from the picture before reading a word."*

**That is not true of the real data, and the mockup's illustrative figures hid it.** Measured on the shipped export:

| view | n | median floor area | share on G-2 |
|---|---|---|---|
| top 60 by dollars | 60 | 204,051 sq ft | **12%** |
| sweet spot | 172 | 15,014 sq ft | **100%** |

On absolute dollars, big genuinely wins — the regression already published this, and the method page already states it. A static map encoding saving as fill would therefore teach "big is good", the opposite of the thesis.

**The resolution is better than the mockup's, not a compromise.** Keep the encodings exactly as designed, and let the **view toggle** carry the argument: the default view shows a handful of enormous slate-outlined parcels, and one click on *Sweet spot* replaces them with 172 small teal ones. The reader watches the ranking's bias invert in a single interaction. That is a live map of opportunity rather than a picture of one, and it is honest about a result the project already publishes.

## Global Constraints

- Python `>=3.11`. **Do not add any new Python dependency.** `geopandas` and `shapely` are already in `pyproject.toml`.
- **JavaScript has no runtime dependencies.** No mapping library — no Leaflet, no Mapbox, no D3. The map is one inline `<svg>`; a tile library would also break the "no live calls from the page" rule in the spec's Distribution Plan.
- **The page computes nothing.** Projection, simplification and path construction all happen in `scripts/build_site.py`. The only arithmetic permitted in `app.js` is the existing sparkline pixel scaling.
- **Never restate a constant.** Import from `src/shave/assumptions.py`.
- **`--signal` is spent on exactly three things** (DESIGN.md): the shaved peak on a sparkline, **parcel fill weight on the map**, and the selected-row rail. Rate class uses `--g2` / `--g3`, which are separate semantic tokens and never borrow the accent.
- **Radius is 3px everywhere and there are no shadows in this system.**
- Below 900px the layout is one column and **the ranked list is ordered first**; the map follows.
- `prefers-reduced-motion` disables parcel transitions.
- Map parcels are keyboard reachable with `role` and `aria-label`, per DESIGN.md's accessibility floor.
- **`node`, `npm` and `npx` are nvm SHELL FUNCTIONS; `export PATH` does not reach them.** Call binaries by absolute path:
  ```bash
  NB="$HOME/.nvm/versions/node/v22.18.0/bin"
  "$NB/npx" vitest run
  ```
  `/usr/local/bin/wrangler` is a stub that prints "You have not installed wrangler"; never invoke it.
- Python suite: `uv run pytest` — currently **954 passing, 4 deselected**, and it takes about five minutes. Render suite: `"$NB/npx" vitest run` — currently **20 passing**.
- Commit after each task, and push to `origin main`. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48
  ```

---

## Verified facts, measured 2026-09-11

Do not re-derive these. Do verify the checks each task names.

**Geometry is cheap.** 563 rows are exported; **562 have usable geometry** and exactly one is null — `ingest` reports `missing_geometry: 1` for Worcester. Raw exterior vertices across those 562 parcels total **22,364**. After `simplify(tolerance, preserve_topology=True)` in EPSG:4326:

| tolerance | vertices | ≈ payload | per parcel |
|---|---|---|---|
| 0.00002 | 5,583 | 87 KB | 9.9 |
| 0.00005 | 4,742 | 74 KB | 8.4 |
| 0.0001 | 4,102 | 64 KB | 7.3 |

**0.00002 is the chosen tolerance** — about 2 m on the ground, which is finer than a parcel boundary needs at city scale, and 87 KB against a current 890 KB payload and a 5 MB `export.MAX_BYTES` ceiling.

**Worcester is portrait.** Bounding box of the exported parcels in EPSG:4326: lon −71.8731…−71.7428, lat 42.2108…42.3363. Correcting longitude by `cos(latitude)`, the aspect ratio **w/h is 0.76**. Cropping does not rescue it: 2nd–98th percentile gives 0.81 while dropping 48 parcels, and 5th–95th gives 0.77 while dropping 108. **Use the full extent.** At 620 units wide the viewBox is **818 tall**.

**Source CRS is EPSG:26986** (Massachusetts State Plane, metres). `ingest.load_municipality` returns a GeoDataFrame in that CRS; `.to_crs(4326)` is already used in `scripts/build_site.py` for the `lon`/`lat` representative points.

**`export.SCHEMA_VERSION` is `1.2.0`.** This plan takes it to `1.3.0` — a MINOR bump, because fields are added and none is removed or retyped.

**The split is ready for two columns.** `public/app.css` has `.split{grid-template-columns:minmax(0,1fr)}` with a comment saying the map restores it, and the below-900px block already carries the ordering rule and the `minmax(0,1fr)` floor that stops the body scrolling sideways.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/mapgeo.py` *(new)* | Simplify, project and serialise one parcel to an SVG path. One file because it is one concern: turning a polygon into a string the page can inject. |
| `scripts/build_site.py` *(modify)* | Call it, and put the frame and paths in the payload. |
| `src/shave/export.py` *(modify)* | `SCHEMA_VERSION` → `1.3.0`. |
| `src/shave/site_data.py` *(modify)* | `REQUIRED_ROW_FIELDS` gains `path`. |
| `public/index.html` *(modify)* | The map panel, restored into `.split`. |
| `public/app.css` *(modify)* | Two columns, sticky map, parcel styles, legend. |
| `public/app.js` *(modify)* | `mapSVG`, `parcelHTML`, and the two-way selection wiring. |
| `tests/test_mapgeo.py` *(new)*, `tests/test_site_data.py`, `web/render.test.js` | |

---

## Task 1: A polygon becomes a string the page can inject

Projection and simplification happen here, once, at build time. The page receives a finished `d` attribute and does no geometry at all — the same rule that keeps the sparkline honest.

**Files:**
- Create: `src/shave/mapgeo.py`
- Test: `tests/test_mapgeo.py` (new)

**Interfaces:**
- Consumes: a GeoDataFrame from `ingest.load_municipality`.
- Produces:
  - `mapgeo.SIMPLIFY_TOLERANCE_DEG: float = 0.00002`
  - `mapgeo.VIEW_WIDTH: int = 620`
  - `mapgeo.MapFrame` — frozen dataclass `min_lon, min_lat, max_lon, max_lat, width, height`
  - `mapgeo.frame_for(gdf) -> MapFrame`
  - `mapgeo.project(lon: float, lat: float, frame: MapFrame) -> tuple[float, float]`
  - `mapgeo.path_for(geom, frame: MapFrame) -> str` — returns `""` for null or empty geometry
  - `mapgeo.paths_for(gdf, frame) -> dict[str, str]` keyed by `loc_id`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mapgeo.py`:

```python
"""Polygons become SVG path strings at build time, never in the browser."""

import pytest
from shapely.geometry import MultiPolygon, Polygon

from shave import mapgeo


def _frame():
    return mapgeo.MapFrame(
        min_lon=-71.9, min_lat=42.2, max_lon=-71.7, max_lat=42.4,
        width=620.0, height=818.0,
    )


def test_projection_puts_the_northwest_corner_at_the_origin():
    """SVG y grows downward and latitude grows upward, so north is y=0."""
    x, y = mapgeo.project(-71.9, 42.4, _frame())
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_projection_puts_the_southeast_corner_at_the_far_edge():
    frame = _frame()
    x, y = mapgeo.project(-71.7, 42.2, frame)
    assert x == pytest.approx(frame.width, abs=1e-6)
    assert y == pytest.approx(frame.height, abs=1e-6)


def test_latitude_is_not_stretched_relative_to_longitude():
    """A degree of longitude is shorter than a degree of latitude at 42 North.
    Without the cosine correction Worcester comes out visibly wide and every
    parcel is the wrong shape."""
    frame = mapgeo.frame_for_bounds(-71.9, 42.2, -71.7, 42.4, width=620.0)
    # 0.2 deg lon x 0.2 deg lat at ~42.3N is taller than it is wide.
    assert frame.height > frame.width
    assert frame.width / frame.height == pytest.approx(0.74, abs=0.02)


def test_a_square_polygon_becomes_a_closed_path():
    square = Polygon([(-71.8, 42.3), (-71.75, 42.3), (-71.75, 42.35), (-71.8, 42.35)])
    d = mapgeo.path_for(square, _frame())

    assert d.startswith("M")
    assert d.endswith("Z")
    assert "L" in d
    assert "nan" not in d.lower()


def test_a_multipolygon_yields_one_subpath_per_part():
    a = Polygon([(-71.8, 42.3), (-71.79, 42.3), (-71.79, 42.31), (-71.8, 42.31)])
    b = Polygon([(-71.75, 42.25), (-71.74, 42.25), (-71.74, 42.26), (-71.75, 42.26)])
    d = mapgeo.path_for(MultiPolygon([a, b]), _frame())

    assert d.count("M") == 2
    assert d.count("Z") == 2


def test_null_and_empty_geometry_return_an_empty_string_not_a_crash():
    """One Worcester parcel has no geometry. It must still reach the table."""
    assert mapgeo.path_for(None, _frame()) == ""
    assert mapgeo.path_for(Polygon(), _frame()) == ""


def test_coordinates_are_rounded_so_the_payload_stays_small():
    """Full float precision would roughly triple the geometry payload for
    sub-millimetre detail nobody can see at city scale."""
    square = Polygon([(-71.8, 42.3), (-71.75, 42.3), (-71.75, 42.35), (-71.8, 42.35)])
    d = mapgeo.path_for(square, _frame())

    for token in d.replace("M", " ").replace("L", " ").replace("Z", " ").split():
        for part in token.split(","):
            _, _, decimals = part.partition(".")
            assert len(decimals) <= 1, f"{part} carries more precision than 0.1 units"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_mapgeo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.mapgeo'`

- [ ] **Step 3: Write `src/shave/mapgeo.py`**

```python
"""A parcel polygon, ready for the page to inject.

Simplification, projection and string-building all happen here, at build
time. The page receives a finished `d` attribute and does no geometry, which
is the same rule that keeps the sparkline honest: every figure on screen was
computed by the pipeline, not by a second implementation in JavaScript.

The projection is equirectangular with a cosine correction on longitude. At
city scale over a 0.13 degree span that is indistinguishable from a proper
projection, and it needs no dependency. A degree of longitude at 42 North is
about 0.74 of a degree of latitude on the ground; without that correction
Worcester renders visibly wide and every parcel is the wrong shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: About 2 m on the ground -- finer than a parcel boundary needs at city
#: scale. Measured over Worcester's 562 exported parcels: 22,364 raw exterior
#: vertices become 5,583, roughly 87 KB of path text.
SIMPLIFY_TOLERANCE_DEG = 0.00002

#: SVG user units across. Height follows from the data's own aspect ratio;
#: Worcester comes out portrait at 818.
VIEW_WIDTH = 620

#: Coordinates are rounded to this many decimals. At 620 units across a
#: 0.13 degree span, 0.1 of a unit is under two metres.
COORD_DECIMALS = 1


@dataclass(frozen=True)
class MapFrame:
    """The bounding box and the SVG canvas it maps onto."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    width: float
    height: float

    @property
    def view_box(self) -> str:
        return f"0 0 {self.width:g} {self.height:g}"


def frame_for_bounds(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    width: float = VIEW_WIDTH,
) -> MapFrame:
    """Derive the canvas height from the ground aspect ratio of the bounds."""
    mid_lat = (min_lat + max_lat) / 2.0
    ground_w = (max_lon - min_lon) * math.cos(math.radians(mid_lat))
    ground_h = max_lat - min_lat
    if ground_w <= 0 or ground_h <= 0:
        raise ValueError(f"degenerate bounds: {min_lon},{min_lat},{max_lon},{max_lat}")
    height = width * (ground_h / ground_w)
    return MapFrame(min_lon, min_lat, max_lon, max_lat, float(width), float(height))


def frame_for(gdf, width: float = VIEW_WIDTH) -> MapFrame:
    """The frame covering every usable geometry in `gdf`, in EPSG:4326.

    Null and empty geometries are excluded rather than allowed to poison the
    bounds -- one Worcester parcel has no geometry, and `total_bounds` over a
    frame containing it returns NaN for everything.
    """
    usable = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if usable.empty:
        raise ValueError("no usable geometry to build a map frame from")
    min_lon, min_lat, max_lon, max_lat = usable.to_crs(4326).total_bounds
    return frame_for_bounds(min_lon, min_lat, max_lon, max_lat, width=width)


def project(lon: float, lat: float, frame: MapFrame) -> tuple[float, float]:
    """Longitude/latitude to SVG user units. North is y=0, since SVG y grows
    downward and latitude grows upward."""
    fx = (lon - frame.min_lon) / (frame.max_lon - frame.min_lon)
    fy = (frame.max_lat - lat) / (frame.max_lat - frame.min_lat)
    return fx * frame.width, fy * frame.height


def _ring(coords, frame: MapFrame) -> str:
    points = []
    for lon, lat in coords:
        x, y = project(lon, lat, frame)
        points.append(f"{round(x, COORD_DECIMALS)},{round(y, COORD_DECIMALS)}")
    if not points:
        return ""
    return "M" + points[0] + "".join("L" + p for p in points[1:]) + "Z"


def path_for(geom, frame: MapFrame) -> str:
    """One SVG `d` string for a polygon or multipolygon, exteriors only.

    Returns "" for null or empty geometry rather than raising: a parcel with
    no polygon still belongs in the ranked table, it simply has nothing to
    draw. Interior rings are dropped -- a hole in a parcel is invisible at
    this scale and doubles the vertex count.
    """
    if geom is None or getattr(geom, "is_empty", True):
        return ""
    simple = geom.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
    if simple.is_empty:
        simple = geom
    if simple.geom_type == "Polygon":
        parts = [simple]
    elif simple.geom_type == "MultiPolygon":
        parts = list(simple.geoms)
    else:
        return ""
    return "".join(_ring(p.exterior.coords, frame) for p in parts if not p.is_empty)


def paths_for(gdf, frame: MapFrame) -> dict[str, str]:
    """`loc_id` to path string, for every row with usable geometry."""
    wgs = gdf.to_crs(4326)
    out: dict[str, str] = {}
    for loc_id, geom in zip(wgs["loc_id"], wgs.geometry):
        d = path_for(geom, frame)
        if d:
            out[str(loc_id)] = d
    return out
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_mapgeo.py -v`
Expected: PASS, all seven.

- [ ] **Step 5: Measure it on the real town**

Run:
```bash
uv run python -c "
from shave import ingest, mapgeo
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
frame = mapgeo.frame_for(g)
paths = mapgeo.paths_for(g, frame)
print('viewBox:', frame.view_box)
print('parcels with a path:', len(paths), 'of', len(g))
total = sum(len(d) for d in paths.values())
print(f'path text: {total/1024:.0f} KB, mean {total/len(paths):.0f} chars per parcel')
print('any NaN:', any('nan' in d.lower() for d in paths.values()))
"
```

**Pass condition, declared in advance:** the viewBox is portrait (height > width, close to `0 0 620 818`), **no path contains `nan`**, and the total path text is under 400 KB. Report the figures.

- [ ] **Step 6: Commit**

```bash
git add src/shave/mapgeo.py tests/test_mapgeo.py
git commit -m "feat: parcel polygons become SVG paths at build time

Simplification, projection and string-building happen in Python so the page
receives a finished d attribute and does no geometry. That is the same rule
that keeps the sparkline honest: every figure on screen was computed by the
pipeline, not by a second implementation in JavaScript.

Equirectangular with a cosine correction on longitude -- a degree of longitude
at 42 North is 0.74 of a degree of latitude, and without the correction
Worcester renders visibly wide and every parcel is the wrong shape. Null
geometry returns an empty string rather than raising: one Worcester parcel has
none, and it still belongs in the table.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
git push origin main
```

---

## Task 2: The map renders, and the legend promises only what is drawn

Two encodings, both from `DESIGN.md`: fill opacity for annual saving, outline colour for rate class. The hatched wall run in the mockup's legend is **not built** — the siting screen is deferred — so the legend must not mention it. A legend entry for something absent is the same defect class this project has already corrected three times.

**Files:**
- Modify: `scripts/build_site.py`, `src/shave/export.py`, `src/shave/site_data.py`
- Modify: `public/index.html`, `public/app.css`, `public/app.js`
- Test: `tests/test_site_data.py`, `web/render.test.js`

**Interfaces:**
- Consumes: `mapgeo.frame_for`, `mapgeo.paths_for`, `mapgeo.MapFrame.view_box`.
- Produces:
  - every exported row gains `path: str` (empty string when the parcel has no geometry)
  - the payload gains `map: {"view_box": str}`
  - `app.js` exports `parcelHTML(row, maxSaving) -> string` and `mapSVG(rows, viewBox, maxSaving) -> string`

- [ ] **Step 1: Write the failing Python test**

Append to `tests/test_site_data.py`:

```python
@needs_worcester
def test_every_exported_row_carries_a_map_path():
    """One Worcester parcel has no geometry and must still be exported, with
    an empty path rather than a missing key."""
    from shave import export, ingest, mapgeo, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    frame = mapgeo.frame_for(parcels)
    raw = export.build_export(scored, parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, scored, paths=mapgeo.paths_for(parcels, frame),
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

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_site_data.py -k map_path -v`
Expected: FAIL — `enrich() got an unexpected keyword argument 'paths'`

- [ ] **Step 3: Carry the geometry through**

In `src/shave/site_data.py`, add `"path"` to `ADDED_ROW_FIELDS`:

```python
ADDED_ROW_FIELDS: tuple[str, ...] = (
    "occupant", "occupant_source", "window_kw", "shaveable_kw", "path",
)
```

Change the signature and body of `enrich`:

```python
def enrich(
    export_payload: dict,
    scored: pd.DataFrame,
    paths: dict[str, str] | None = None,
    view_box: str | None = None,
) -> dict:
```

Inside the row loop, after `row["shaveable_kw"] = ...`, add:

```python
            # Empty string, not a missing key: a parcel with no polygon still
            # belongs in the table, and the page checks truthiness once.
            row["path"] = (paths or {}).get(row["loc_id"], "")
```

And before `return payload`, add:

```python
    if view_box:
        payload["map"] = {"view_box": view_box}
```

In `src/shave/export.py`, bump the version:

```python
SCHEMA_VERSION = "1.3.0"
```

In `scripts/build_site.py`, import `mapgeo` and build the frame. The file currently contains exactly one line reading `    enriched = site_data.enrich(raw, scored)`. Replace that single line with these three:

```python
    frame = mapgeo.frame_for(parcels)
    enriched = site_data.enrich(
        raw, scored, paths=mapgeo.paths_for(parcels, frame), view_box=frame.view_box
    )
```

Add `mapgeo` to the import at the top:

```python
from shave import export, ingest, mapgeo, pipeline, regression, site_data
```

- [ ] **Step 4: Run the Python tests and rebuild**

Run: `uv run pytest tests/test_site_data.py -v`
Expected: PASS, all ten.

```bash
uv run python scripts/build_site.py
uv run python -c "
import json; d=json.load(open('public/data/ranked.json'))
print('schema:', d['schema_version'], '| viewBox:', d['map']['view_box'])
rows=[r for l in d['lists'].values() for r in l]
drawn=[r for r in rows if r['path']]
print(f'{len(drawn)} of {len(rows)} rows have a path')
import os; print('ranked.json:', round(os.path.getsize('public/data/ranked.json')/1024), 'KB')
"
```

**Pass condition:** 562 of 563 rows carry a path, and `ranked.json` stays under 1,400 KB.

- [ ] **Step 5: Write the failing render test**

Append to `web/render.test.js`:

```js
import { mapSVG, parcelHTML } from "../public/app.js";

const MAP_ROWS = [
  { ...ROW, loc_id: "A", annual_savings_usd: 30000, rate_class: "G-3",
    path: "M10,10L20,10L20,20L10,20Z", occupant: "Big Slate Co" },
  { ...ROW, loc_id: "B", annual_savings_usd: 6000, rate_class: "G-2",
    path: "M40,40L45,40L45,45L40,45Z", occupant: "Small Teal Co" },
  { ...ROW, loc_id: "C", annual_savings_usd: 1000, rate_class: "G-2", path: "" },
];

describe("parcelHTML", () => {
  it("encodes rate class in the outline and never in the accent", () => {
    const a = parcelHTML(MAP_ROWS[0], 30000);
    const b = parcelHTML(MAP_ROWS[1], 30000);
    expect(a).toContain("var(--g3)");
    expect(b).toContain("var(--g2)");
    // the accent is reserved for fill weight; an outline must never take it
    expect(a).not.toMatch(/stroke="var\(--signal\)"/);
  });

  it("encodes saving as fill opacity, heavier for more money", () => {
    const rich = parcelHTML(MAP_ROWS[0], 30000);
    const poor = parcelHTML(MAP_ROWS[1], 30000);
    const op = (s) => parseFloat(s.match(/fill-opacity="([\d.]+)"/)[1]);
    expect(op(rich)).toBeGreaterThan(op(poor));
    expect(op(poor)).toBeGreaterThan(0);
  });

  it("is keyboard reachable and labelled for a screen reader", () => {
    const html = parcelHTML(MAP_ROWS[0], 30000);
    expect(html).toContain('tabindex="0"');
    expect(html).toContain('role="button"');
    expect(html).toMatch(/aria-label="[^"]*Big Slate Co[^"]*"/);
  });

  it("escapes the label, which came from an assessor record", () => {
    const html = parcelHTML({ ...MAP_ROWS[0], occupant: '"><script>x' }, 30000);
    expect(html).not.toContain("<script>");
  });
});

describe("mapSVG", () => {
  it("draws only the rows that have geometry", () => {
    const svg = mapSVG(MAP_ROWS, "0 0 620 818", 30000);
    expect(svg.match(/class="parcel"/g)).toHaveLength(2);
    expect(svg).not.toContain('data-id="C"');
  });

  it("carries the build's viewBox rather than inventing one", () => {
    expect(mapSVG(MAP_ROWS, "0 0 620 818", 30000)).toContain('viewBox="0 0 620 818"');
  });

  it("says so plainly when there is nothing to draw", () => {
    const svg = mapSVG([MAP_ROWS[2]], "0 0 620 818", 1000);
    expect(svg).toMatch(/no mapped parcel|nothing to draw/i);
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `mapSVG is not a function`.

- [ ] **Step 7: Add the renderers to `public/app.js`**

Insert before the wiring section:

```js
//: Fill opacity floor and ceiling. A parcel at the floor must still be
//: visible -- an invisible row is a row the reader cannot click.
const FILL_MIN = 0.16;
const FILL_MAX = 0.78;

export function parcelHTML(row, maxSaving) {
  const share = maxSaving > 0 ? Number(row.annual_savings_usd) / maxSaving : 0;
  const opacity = (FILL_MIN + (FILL_MAX - FILL_MIN) * Math.min(1, Math.max(0, share)))
    .toFixed(3);
  const stroke = row.rate_class === "G-2" ? "var(--g2)" : "var(--g3)";
  return (
    `<g class="parcel" data-id="${esc(row.loc_id)}" tabindex="0" role="button" ` +
    `aria-label="${esc(siteName(row))}, rate ${esc(row.rate_class)}, estimated ` +
    `saving ${fmtMoney(row.annual_savings_usd)} a year">` +
    `<path class="pfill" d="${esc(row.path)}" fill="var(--signal)" ` +
    `fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.1"/>` +
    `</g>`
  );
}

export function mapSVG(rows, viewBox, maxSaving) {
  const drawn = (rows || []).filter((r) => r.path);
  if (!drawn.length) {
    return (
      `<svg class="mapsvg" viewBox="${esc(viewBox)}" role="img" ` +
      `aria-label="No mapped parcel in this view."></svg>` +
      `<p class="whysplit">No mapped parcel in this view. The ranked list is ` +
      `unaffected; only the drawing has nothing to show.</p>`
    );
  }
  return (
    `<svg class="mapsvg" viewBox="${esc(viewBox)}" role="img" ` +
    `aria-label="Worcester parcels, shaded by estimated annual demand-charge ` +
    `saving and outlined by rate class.">` +
    `<g id="parcels">${drawn.map((r) => parcelHTML(r, maxSaving)).join("")}</g>` +
    `</svg>`
  );
}
```

- [ ] **Step 8: Add the map panel to `public/index.html`**

Inside `<div class="split">`, **before** the existing ranked-list panel:

```html
      <div class="panel mapbox">
        <div class="panel-head">
          <span class="panel-title">Opportunity, by parcel</span>
          <span class="eyebrow">Fill = annual saving &middot; Outline = rate class</span>
        </div>
        <div id="map"></div>
        <div class="legend">
          <span><i class="sw-fill"></i>Higher annual saving</span>
          <span><i class="sw-g2"></i>Rate G&#8209;2 &middot; $15.06/kW</span>
          <span><i class="sw-g3"></i>Rate G&#8209;3 &middot; $10.48/kW</span>
        </div>
      </div>
```

**There is no wall-run entry.** The mockup's legend has one; the siting screen is not built, and a legend promising a mark that never appears is a claim the code does not back.

- [ ] **Step 9: Add the map styles to `public/app.css`**

Restore the two-column split by replacing the single-column rule:

```css
.split{display:grid; grid-template-columns:minmax(0,55fr) minmax(0,45fr);
  gap:16px; margin-top:16px; align-items:start}
```

Leave the `@media (max-width:900px)` block exactly as it is — it already collapses to one column, orders the ranked list first, and carries the `minmax(0,1fr)` floor that stops the body scrolling sideways.

Append:

```css
/* ---------- map ---------- */
/* Worcester is portrait, aspect 0.76, so the drawing is taller than it is
   wide. Sticky keeps it beside the table while 354 rows scroll past, and the
   viewport cap stops it running off the screen on a laptop. */
.mapbox{position:sticky; top:20px}
.mapsvg{display:block; margin:0 auto; width:auto; height:auto;
  max-width:100%; max-height:76vh}
@media (max-width:900px){ .mapbox{position:static} .mapsvg{max-height:52vh} }

.legend{display:flex; flex-wrap:wrap; gap:14px; padding:9px 12px;
  border-top:1px solid var(--rule); font-size:11.5px; color:var(--ink-2)}
.legend i{display:inline-block; width:11px; height:11px; margin-right:5px;
  vertical-align:-1px; border-radius:1px}
.legend .sw-g2{background:transparent; border:1.5px solid var(--g2)}
.legend .sw-g3{background:transparent; border:1.5px solid var(--g3)}
.legend .sw-fill{background:var(--signal); opacity:.55}

.parcel{cursor:pointer; transition:opacity .12s ease}
@media (prefers-reduced-motion:reduce){ .parcel{transition:none} }
.parcel.dim{opacity:.22}
.parcel.on .pfill{stroke-width:2.6}
```

- [ ] **Step 10: Render it in `boot()`**

In `public/app.js`, inside `draw()`, after the rows are written, add:

```js
  const maxSaving = state.shown.reduce(
    (m, r) => Math.max(m, Number(r.annual_savings_usd) || 0), 0,
  );
  $("#map").innerHTML = mapSVG(state.shown, state.viewBox, maxSaving);
```

In `boot()`, after `state.lists = ranked.lists;`, add:

```js
  state.viewBox = (ranked.map || {}).view_box || "0 0 620 818";
```

and add `viewBox: "0 0 620 818"` to the `state` object literal.

- [ ] **Step 11: Run both suites and look at it**

```bash
uv run pytest tests/test_site_data.py -q
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
uv run python scripts/build_site.py
"$NB/npx" wrangler dev --port 8787
```

Open `http://127.0.0.1:8787/` and confirm by eye:

- the map draws recognisable Worcester parcels, not a smear or a single blob;
- big G-3 parcels are slate-outlined and dark; small G-2 parcels are teal;
- clicking **Sweet spot** visibly inverts the picture — few large slate shapes become many small teal ones;
- the legend has three entries and none mentions a wall run;
- at 400px the layout is one column with the ranked list first and the body does not scroll sideways.

- [ ] **Step 12: Commit**

```bash
git add src/shave/site_data.py src/shave/export.py scripts/build_site.py \
        public/index.html public/app.css public/app.js \
        tests/test_site_data.py web/render.test.js docs/ranked-json-schema.md
git commit -m "feat: the encoding map

Two encodings, both from DESIGN.md: fill opacity for annual saving, outline
colour for rate class. No mapping library and no tiles -- one inline SVG whose
paths were projected at build time, so the page still computes nothing.

The legend has three entries, not the mockup's four. The hatched wall run
needs the siting screen, which is not built, and a legend promising a mark
that never appears is a claim the code does not back.

Schema 1.3.0: rows gain `path`, the payload gains `map.view_box`. MINOR,
because nothing was removed or retyped.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
git push origin main
```

Also add to `docs/ranked-json-schema.md`, under the versioning rule:

```markdown
**1.3.0** — rows gain `path`, an SVG `d` string in the coordinate space of
`map.view_box`, empty for a parcel with no geometry. The payload gains a
top-level `map` object carrying `view_box`. Projection and simplification
happen at build time; the page injects the string unchanged.
```

---

## Task 3: The map and the table are one instrument

DESIGN.md: *"Dim / highlight — cross-linked selection with the ranked table, both directions."* Selecting a row highlights its parcel and dims the rest; clicking a parcel selects and scrolls to its row. Without that the map is a picture beside a table rather than a view onto it.

**Files:**
- Modify: `public/app.js`
- Test: `web/render.test.js`

**Interfaces:**
- Consumes: `select(id)`, `state.shown`, `parcelHTML`, `mapSVG`.
- Produces: `app.js` exports `parcelSelectionClasses(rows, selectedId) -> Record<string, string>` — the class each parcel should carry for a given selection.

- [ ] **Step 1: Write the failing test**

Append to `web/render.test.js`:

```js
import { parcelSelectionClasses } from "../public/app.js";

describe("parcelSelectionClasses", () => {
  const rows = [
    { loc_id: "A", path: "M0,0L1,1Z" },
    { loc_id: "B", path: "M0,0L1,1Z" },
    { loc_id: "C", path: "" },
  ];

  it("highlights the selected parcel and dims the others", () => {
    const cls = parcelSelectionClasses(rows, "A");
    expect(cls.A).toContain("on");
    expect(cls.A).not.toContain("dim");
    expect(cls.B).toContain("dim");
  });

  it("dims nothing when there is no selection", () => {
    const cls = parcelSelectionClasses(rows, null);
    expect(cls.A).not.toContain("dim");
    expect(cls.B).not.toContain("dim");
  });

  it("ignores rows with no geometry", () => {
    expect(parcelSelectionClasses(rows, "A")).not.toHaveProperty("C");
  });

  it("dims everything when the selection is not on the map", () => {
    // The selected row exists in the table but has no parcel: the map must
    // not silently keep a stale highlight on a different building.
    const cls = parcelSelectionClasses(rows, "C");
    expect(cls.A).toContain("dim");
    expect(cls.B).toContain("dim");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `parcelSelectionClasses is not a function`.

- [ ] **Step 3: Implement it and wire both directions**

In `public/app.js`, add beside the other renderers:

```js
export function parcelSelectionClasses(rows, selectedId) {
  const drawn = (rows || []).filter((r) => r.path);
  const out = {};
  const anySelected = selectedId != null;
  for (const row of drawn) {
    const on = row.loc_id === selectedId;
    out[row.loc_id] = on ? "parcel on" : anySelected ? "parcel dim" : "parcel";
  }
  return out;
}
```

In `select(id)`, after the drawer is written, add:

```js
  // The map is a view onto the table, not a picture beside it.
  const classes = parcelSelectionClasses(state.shown, id);
  $$("#map .parcel").forEach((g) => {
    g.setAttribute("class", classes[g.dataset.id] || "parcel");
  });
```

In `boot()`, beside the `#rows` listeners, add the reverse direction:

```js
  $("#map").addEventListener("click", (e) => {
    const g = e.target.closest(".parcel");
    if (!g) return;
    select(g.dataset.id);
    const tr = $(`#rows tr[data-id="${CSS.escape(g.dataset.id)}"]`);
    if (tr) tr.scrollIntoView({ block: "center", behavior: "smooth" });
  });
  $("#map").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const g = e.target.closest(".parcel");
    if (!g) return;
    e.preventDefault();
    select(g.dataset.id);
  });
```

`scrollIntoView` with `behavior: "smooth"` must respect `prefers-reduced-motion`. Replace that call with:

```js
    if (tr) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      tr.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
```

- [ ] **Step 4: Run both suites**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
uv run pytest -q
```
Expected: PASS both.

- [ ] **Step 5: Check both directions in a browser**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler dev --port 8787
```

Confirm:
- rank 1 is selected on load and its parcel is highlighted while the rest are dimmed;
- clicking a table row moves the highlight;
- clicking a parcel selects its row and scrolls it into view;
- tabbing reaches parcels and Enter selects;
- switching to the modelled list or the sweet-spot view redraws the map and the selection lands on the new rank 1.

- [ ] **Step 6: Commit**

```bash
git add public/app.js web/render.test.js
git commit -m "feat: the map and the table are one instrument

Selecting a row highlights its parcel and dims the rest; clicking a parcel
selects its row and scrolls to it. Without both directions the map is a
picture beside a table rather than a view onto it.

A selection with no parcel dims everything rather than leaving a stale
highlight on a different building, and scrollIntoView respects
prefers-reduced-motion.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
git push origin main
```

---

## Task 4: Ship it, and say what the map does not know

The map draws parcel outlines from assessor data. It shows nothing about whether a cabinet will fit, because the siting screen is not built — and the method page must say so, in the same place it names every other gap.

**Files:**
- Modify: `src/shave/method.py`
- Test: `tests/test_method.py`
- Deploy

**Interfaces:**
- Consumes: `method.KNOWN_GAPS`.
- Produces: a new `Limitation` with key `map_shows_no_siting`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_method.py`:

```python
def test_the_method_page_says_what_the_map_cannot_show():
    """The map draws parcel outlines. A reader will reasonably assume a shape
    on a map means a site was assessed for fit; nothing here checks that."""
    stated = {g.key: g.statement for g in method.KNOWN_GAPS}
    assert "map_shows_no_siting" in stated, sorted(stated)
    text = stated["map_shows_no_siting"]
    assert "wall" in text.lower()
    assert "outline" in text.lower() or "shape" in text.lower()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_method.py -k map_cannot -v`
Expected: FAIL — `assert 'map_shows_no_siting' in [...]`

- [ ] **Step 3: Add the gap**

In `src/shave/method.py`, add to `KNOWN_GAPS`, replacing the existing `no_siting_screen` entry so the two do not say overlapping things:

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

- [ ] **Step 4: Run the suites**

Run: `uv run pytest -q` and `"$NB/npx" vitest run`
Expected: PASS both. `test_limitation_keys_are_unique` and `test_every_limitation_has_a_real_sentence` both cover the new entry.

- [ ] **Step 5: Rebuild and deploy**

```bash
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

- [ ] **Step 6: Verify the live site**

```bash
URL="https://shave.pjayav.workers.dev"
curl -s -o /dev/null -w 'index  %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/ranked.json"
```

**Pass conditions, declared in advance:** both `200`; index plus `ranked.json` under **3 seconds**; the payload under 1,400 KB.

Then load the URL in a browser and confirm the map draws, both selection directions work, the sweet-spot toggle inverts the picture, and the Method tab lists the new gap.

- [ ] **Step 7: Commit**

```bash
git add src/shave/method.py tests/test_method.py
git commit -m "docs: say what the map cannot show

The map draws the assessor's parcel outline and nothing else. A reader will
reasonably take a shape on a map to mean the site was assessed for fit. No
siting screen has been run, so nothing computes the longest clear wall run or
rules out a zero-lot-line parcel, and the map cannot see loading docks, fire
lanes or egress.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
git push origin main
```

---

## What this plan deliberately leaves for the next one

| Deferred | Why | Est. |
|---|---|---|
| **Address box over a static prebuilt index** | D5 calls it the verification moment. Independent of the map: a client-side index over the covered towns, no database. Next after this. | 2h |
| `STRUCTURES_POLY` join and the siting screen | Would add the hatched wall run this plan's legend deliberately omits, and fill the drawer's empty clear-wall slot. | 4.5h |
| New Bedford and Chicopee | The municipality control in the mockup is built for them; each needs an L3 download, a crosswalk pass over its use codes, and its own `county_gisjoin`. The map frame is already computed per build from whatever parcels it is given. | 2h |
| Occupant resolution, 46 remaining | Hand lookups. `/tmp/worksheet.csv` carries them with addresses and dollar values; the ratchet in `tests/test_occupants.py` rises as they land. | 3h |
| MECOLS class-shape check | `MECOLS.xlsx` still not on disk. Already a named gap on the method page. | 1h + fetch |
| Suite runtime | ~5 minutes, because `test_site_data` and `test_occupants` re-run the full 2,099-parcel pipeline eleven-plus times. A session-scoped fixture would cut it to about one. Worth doing before the suite grows again. | 1h |

---

## Self-Review

**Spec coverage.** Task 1 and Task 2 implement design review **D2** — the encoding map, with fill opacity for saving and outline colour for rate class, drawn from precomputed geometry. Task 3 implements D2's cross-linking requirement in both directions. Task 4 satisfies premise **P6** for the new surface by naming what the map cannot show, and closes success criterion 1 again for the redeployed site. The map's third designed channel — the hatched wall run — is **not** implemented and is deliberately absent from the legend; the deferral table says why and the method page states it.

**Placeholder scan:** clean. Every code step carries its code and every test step its test. A first draft of Task 2 contained two deliberate awkwardnesses — an `if False else` to disambiguate a substitution target, and a doubled `npx` with a correction beneath it — each with a note telling the implementer to fix it. That is precisely what the No Placeholders rule forbids: a step that ships a known defect and asks the reader to catch it. Both are now written correctly, with the substitution target identified by quoting the unique line it replaces.

**Type consistency.** `mapgeo.MapFrame` is produced by `frame_for`/`frame_for_bounds` and consumed by `project`, `path_for` and `paths_for`, all in Task 1. `paths_for` returns `dict[str, str]` keyed by `loc_id`, which is exactly what `site_data.enrich`'s new `paths` parameter takes in Task 2, and `MapFrame.view_box` feeds its `view_box` parameter. `site_data.ADDED_ROW_FIELDS` gains `"path"`, so `REQUIRED_ROW_FIELDS` picks it up automatically through the existing concatenation and the contract test covers it with no edit. `parcelHTML(row, maxSaving)` and `mapSVG(rows, viewBox, maxSaving)` are defined in Task 2 and both consumed by `draw()`; `parcelSelectionClasses(rows, selectedId)` is added in Task 3 and consumed by `select()`. `esc`, `fmtMoney` and `siteName` already exist in `app.js` and the new renderers reuse them rather than reimplementing escaping.

**One risk worth naming.** `.mapbox{position:sticky}` inside a grid whose items are `align-items:start` works in current browsers, but sticky positioning inside a grid item is the kind of thing that silently degrades to static. It degrades safely — the map simply scrolls with the page — and Task 2 Step 11's browser check is where that would be noticed. No test can catch it.
