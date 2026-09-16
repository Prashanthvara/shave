# Three-Town Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Worcester, Fall River and Lowell on the live site, behind the mockup's Municipality control, with the address box, method page and coverage review covering all three.

**Architecture:**
- **Per-town payloads.** The build writes one ranked payload per town (`public/data/towns/<slug>/ranked.json`), each in its own map frame, plus a small `public/data/index.json` listing the towns.
- **Shared data.** The method payload and the address index are built once, over all three towns.
- **Loading.** The page loads the index, draws the Municipality control, and fetches a town's payload the first time it is chosen. First paint loads only the default town, so the 3-second criterion is unaffected.
- **Schema.** The page contract changes shape, so `SITE_SCHEMA_VERSION` goes to `2.0.0`.

**Tech Stack:** Python 3.11, vanilla ES2020 + inline SVG, vitest, Cloudflare Workers static assets.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`. Also the approved mockup `~/.gstack/projects/powertown/designs/shave-ranked-map-20260910/shave-mockup.html`, line 233: `<div class="seg" role="group" aria-label="Municipality">` in the toolbar.

**Depends on:**
- `2026-09-15-fall-river-and-lowell.md`, which provides `towns.TOWNS`, ingest `town_id` and both towns scoring.
- `2026-09-15-mecols-check.md`, only for the `calibration.run` call. If that plan has not landed, delete the one `calibration` line in Task 1's build script and the `calibration=` argument.

## Global Constraints

- **The two ranked lists are never merged, and neither are the towns.** Ranks restart per town and per list.
- **The page computes no figure it displays.**
- **First load (index + default town payload) stays under 3 s** (success criterion 1).
- **Every assessor-derived string goes through `esc()`.**
- **`--signal` keeps its three uses only.**
- **Tooling:**
  - `node`/`npx`: `NB="$HOME/.nvm/versions/node/v22.18.0/bin"`.
  - Run `uv run pytest` **without `-q`**.
  - `public/data/` is gitignored: payloads are built, never committed.
- **Baseline.** Record **B** and **R** (Python and render counts) in Task 1 Step 1.
- Branch: `git checkout -b feat/three-town-site`.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts

- **Worcester's payload today** is 1,437 KB raw / 269 KB gzipped for 563 rows (about 2.55 KB per row). Three towns in one file would be about 4.3 MB against `export.MAX_BYTES = 5 MB`, and would put three distant towns in one SVG frame. Per-town files keep each payload near today's size and each map in its own frame.
- **Parcel ids are unique statewide.** `LOC_ID` is built from state-plane coordinates (`F_577265_2910122`), so `occupants.csv` and the address index need no town key.
- **`addresses.build_index`** already takes a `towns` list. `parseQuery` already strips a trailing multi-word town name, so "FALL RIVER" works.
- **Assessor vintage.** Worcester's extract is `CY26_FY26`; Fall River's and Lowell's are `CY25_FY26`. The spec (lines 868–870) asks for assessor year per town, shown in row detail and on the method page.
- **Current boot sequence.** The start of `app.js`'s `boot()` fetches `/data/ranked.json`, checks the schema major, and sets `state.lists`, `viewBox`, `dayAxis` and `sitingRule`. It then writes `#counts` and `#vintage` and calls `applyFilters()`. The rest of `boot()` (method fetch, row/map/lookup/source/view/tab listeners) is unchanged by this plan.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/site_build.py` *(new)* | `town_payload`, `index_payload`: what the build writes per town and at the top. |
| `scripts/build_site.py` *(rewrite)* | Loop the towns; write per-town payloads, the index, method and addresses. |
| `src/shave/site_data.py`, `src/shave/addresses.py`, `src/shave/method.py` *(modify)* | Schema 2.0.0; `town` on address entries; towns on the method payload; the town-swap limitation. |
| `public/index.html`, `public/app.js`, `public/app.css` *(modify)* | The Municipality control and per-town loading. |
| `tests/test_site_build.py` *(new)*, `tests/test_addresses.py`, `tests/test_method.py`, `web/render.test.js` | |
| `docs/spec-coverage.md`, `docs/ranked-json-schema.md` *(modify)* | |

---

## Task 1: Per-town payloads and the index

**Files:**
- Create: `src/shave/site_build.py`, `tests/test_site_build.py`
- Rewrite: `scripts/build_site.py`
- Modify: `src/shave/site_data.py` (`SITE_SCHEMA_VERSION`), `src/shave/addresses.py` (`build_index`), `tests/test_addresses.py`, `docs/ranked-json-schema.md`

**Interfaces:**
- Consumes: `towns.TOWNS`, `towns.by_id`; ingest `town_id`.
- Produces:
  - `site_data.SITE_SCHEMA_VERSION = "2.0.0"`
  - `site_build.town_payload(town: towns.Town, parcels, scored) -> dict`: the enriched export minus `method`, with `town = {town_id, name, slug, assess_fy}`
  - `site_build.index_payload(payloads: list[dict]) -> dict`: `{site_schema_version, default, towns: [{town_id, name, slug, assess_fy, counts}]}`
  - `site_build.town_data_path(out, slug) -> Path`: `out/towns/<slug>/ranked.json`
  - address entries gain `town` (slug, or `""` when the parcel frame has no `town_id`)

- [ ] **Step 1: Branch and baselines**

```bash
git checkout -b feat/three-town-site
uv run pytest 2>&1 | tail -1
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run 2>&1 | grep "Tests "
```

Record **B** and **R**.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_site_build.py`:

```python
"""What the build writes for each town, and the index that lists them."""

import json
from pathlib import Path

from shave import site_build, site_data, towns


def test_the_index_lists_each_town_with_its_counts_and_defaults_to_the_first():
    payloads = [
        {"town": {"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026},
         "counts": {"kept": 737}},
        {"town": {"town_id": 160, "name": "Lowell", "slug": "lowell", "assess_fy": 2026},
         "counts": {"kept": 10}},
    ]

    index = site_build.index_payload(payloads)

    assert index["site_schema_version"] == site_data.SITE_SCHEMA_VERSION == "2.0.0"
    assert index["default"] == "worcester"
    assert [t["slug"] for t in index["towns"]] == ["worcester", "lowell"]
    assert index["towns"][1]["counts"] == {"kept": 10}


def test_a_town_payload_is_that_towns_own_export_in_its_own_frame(worcester_parcels, worcester_scored):
    town = towns.by_id(348)

    payload = site_build.town_payload(town, worcester_parcels, worcester_scored)

    assert payload["town"] == {"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026}
    assert "method" not in payload
    assert payload["site_schema_version"] == "2.0.0"
    assert payload["map"]["view_box"].startswith("0 0 620 ")
    rows = [r for l in payload["lists"].values() for r in l]
    assert rows and any(r["path"] for r in rows), "the town's map would draw nothing"
    json.dumps(payload)


def test_town_data_paths_are_per_slug():
    assert site_build.town_data_path(Path("public/data"), "fall-river") == Path(
        "public/data/towns/fall-river/ranked.json")
```

Append to `tests/test_addresses.py`:

```python
def test_each_entry_names_its_town_by_slug():
    parcels, scored, lists = _frames()
    parcels = parcels.assign(town_id=[160, 160, 95, 348, 348])

    index = addresses.build_index(parcels, scored, lists, towns=["WORCESTER", "FALL RIVER", "LOWELL"])
    by_id = {e["loc_id"]: e["town"] for e in index["entries"]}

    assert by_id == {"A": "lowell", "B": "lowell", "C": "fall-river", "D": "worcester"}
```

Run: `uv run pytest tests/test_site_build.py tests/test_addresses.py`
Expected: FAIL — `ImportError: cannot import name 'site_build'`.

- [ ] **Step 3: Implement**

In `src/shave/site_data.py`, replace `SITE_SCHEMA_VERSION = "1.0.0"` with:

```python
#: 2.0.0: the page loads index.json, then one ranked payload per town. A 1.x
#: page cannot read that layout, so it must refuse rather than draw nothing.
SITE_SCHEMA_VERSION = "2.0.0"
```

Create `src/shave/site_build.py`:

```python
"""What the build writes: one ranked payload per town, and an index of towns.

Towns are never merged into one ranked list, for the same reason the two
source lists are not: each town's payload ranks within itself, draws its own
map frame, and loads only when a reader asks for that town.
"""

from __future__ import annotations

from pathlib import Path

from shave import export, mapgeo, site_data, towns


def town_data_path(out: Path | str, slug: str) -> Path:
    return Path(out) / "towns" / slug / "ranked.json"


def town_payload(town: towns.Town, parcels, scored) -> dict:
    """One town's enriched export, in that town's own map frame."""
    parcels = parcels.copy()
    # representative_point, not centroid: a centroid of an L-shaped or ring
    # parcel can land outside it, which puts a marker in someone else's yard.
    points = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = points.x
    parcels["lat"] = points.y
    fy = parcels["assess_fy"].dropna()
    meta = {
        "town_id": town.town_id,
        "name": town.name,
        "slug": town.slug,
        "assess_fy": int(fy.iloc[0]) if len(fy) else None,
    }
    raw = export.build_export(scored, parcels, town=meta)
    frame = mapgeo.frame_for(parcels)
    enriched = site_data.enrich(
        raw, scored,
        paths=mapgeo.paths_for(parcels, frame),
        view_box=frame.view_box,
        walls=mapgeo.walls_for(parcels, frame),
    )
    return {k: v for k, v in enriched.items() if k != "method"}


def index_payload(payloads: list[dict]) -> dict:
    """The towns the page can show, in order; the first is the default."""
    return {
        "site_schema_version": site_data.SITE_SCHEMA_VERSION,
        "default": payloads[0]["town"]["slug"],
        "towns": [{**p["town"], "counts": p["counts"]} for p in payloads],
    }
```

In `src/shave/addresses.py`:

- Add `towns` to the import: `from shave import method, pipeline, towns`.
- In `build_index`, replace `detail = pd.DataFrame(parcels)[["loc_id", "site_addr", "confidence"]]` with:

  ```python
    wanted = ["loc_id", "site_addr", "confidence"] + (["town_id"] if "town_id" in parcels else [])
    detail = pd.DataFrame(parcels)[wanted]
  ```

- In the `entries.append({...})` dict, add after `"loc_id": loc_id,`:

  ```python
            "town": _town_slug(rec.get("town_id")),
  ```

- Add above `build_index`:

  ```python
def _town_slug(town_id) -> str:
    if town_id is None or pd.isna(town_id):
        return ""
    return towns.by_id(int(town_id)).slug
  ```

Replace `scripts/build_site.py` entirely:

```python
"""Build everything the page loads, for every covered town.

    uv run python scripts/build_site.py

Writes, under public/data:
  index.json                     the towns, their counts, the default
  towns/<slug>/ranked.json       one enriched export per town, in its own map frame
  method.json                    one method payload over all towns
  addresses.json                 one address index over all towns
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from shave import (
    addresses, calibration, ingest, method, pipeline, regression, siting, site_build, towns,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"  {str(path):48s} {path.stat().st_size / 1024:8.1f} KB", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="public/data")
    args = parser.parse_args()
    out = Path(args.out)
    started = time.perf_counter()

    payloads, all_parcels, all_scored = [], [], []
    for town in towns.TOWNS:
        parcels = ingest.load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        scored = pipeline.score_parcels(parcels)
        payload = site_build.town_payload(town, parcels, scored)
        _write(site_build.town_data_path(out, town.slug), payload)
        payloads.append(payload)
        all_parcels.append(parcels)
        all_scored.append(scored)

    parcels = pd.concat(all_parcels, ignore_index=True)
    scored = pd.concat(all_scored, ignore_index=True)
    index = site_build.index_payload(payloads)
    method_payload = method.method_payload(
        scored,
        regression=regression.run(scored),
        calibration=calibration.run(scored),
        towns=index["towns"],
    )
    lists = {
        source: [row for p in payloads for row in p["lists"][source]]
        for source in ("comstock", "modeled")
    }
    address_index = addresses.build_index(
        parcels, scored, lists, towns=[t.name for t in towns.TOWNS]
    )

    _write(out / "index.json", index)
    _write(out / "method.json", method_payload)
    _write(out / "addresses.json", address_index)
    print(f"built {len(payloads)} towns in {time.perf_counter() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`method.method_payload(..., towns=)` is added in Task 2. Until then, Step 4 below runs the tests only, not the build.

In `docs/ranked-json-schema.md`, add under the version history:

```markdown
**Site layout 2.0.0** — the page no longer loads `/data/ranked.json`. It loads `/data/index.json`
(`{site_schema_version, default, towns: [{town_id, name, slug, assess_fy, counts}]}`) and then
`/data/towns/<slug>/ranked.json` for the chosen town. Each town file is this document's payload for
one town, ranked within itself and drawn in its own map frame; its `town` object gains `slug`.
Address index entries gain `town` (a slug).
```

- [ ] **Step 4: Run and commit**

```bash
uv run pytest tests/test_site_build.py tests/test_addresses.py tests/test_site_data.py
git add src/shave/site_build.py scripts/build_site.py src/shave/site_data.py src/shave/addresses.py \
        tests/test_site_build.py tests/test_addresses.py docs/ranked-json-schema.md
git commit -m "feat: one ranked payload per town, and an index of towns

Three distant towns cannot share one map frame, and one file for all three
would be about 4.3 MB against the 5 MB ceiling. Each town now gets its own
enriched export in its own frame; a small index lists them, and method and
address data are built once over all three. Site schema 2.0.0: the page
contract changed shape.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: the targeted files PASS. The full suite is run at the end of Task 2, once `method_payload` accepts `towns`.

---

## Task 2: The method page names the towns and the swap

**Files:**
- Modify: `src/shave/method.py`, `tests/test_method.py`
- Modify: `public/app.js` (`methodHTML`), `web/render.test.js`

**Interfaces:**
- Produces:
  - `method.method_payload(scored, regression=None, calibration=None, towns=None)`, whose payload gains `towns: list[dict]`
  - `KNOWN_GAPS` loses `one_municipality`; `LIMITATIONS` gains `three_towns_not_the_design_docs_three`
  - `methodHTML` prose names each town with its assessor year

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_method.py`:

```python
def test_the_method_page_states_the_town_swap_and_why():
    assert "one_municipality" not in {g.key for g in method.KNOWN_GAPS}
    stated = {l.key: l.statement for l in method.LIMITATIONS}
    text = stated["three_towns_not_the_design_docs_three"]
    for words in ("Fall River", "Lowell", "New Bedford", "Chicopee", "Eversource", "municipal light plant"):
        assert words in text, words


def test_the_method_payload_carries_the_towns_it_was_given():
    towns = [{"town_id": 348, "name": "Worcester", "slug": "worcester", "assess_fy": 2026, "counts": {}}]
    assert method.method_payload(_fake_scored(), towns=towns)["towns"] == towns
    assert method.method_payload(_fake_scored())["towns"] == []
```

Append to `web/render.test.js`:

```js
describe("methodHTML towns", () => {
  it("names every covered town with its own assessor year", () => {
    const { prose } = methodHTML({
      ...METHOD,
      towns: [
        { name: "Worcester", slug: "worcester", assess_fy: 2026 },
        { name: "Fall River", slug: "fall-river", assess_fy: 2026 },
        { name: "Lowell", slug: "lowell", assess_fy: 2026 },
      ],
    });
    expect(prose).toContain("Worcester (assessor FY 2026)");
    expect(prose).toContain("Fall River (assessor FY 2026)");
    expect(prose).toContain("Lowell (assessor FY 2026)");
  });
});
```

Run both suites. Expected: FAIL (`unexpected keyword argument 'towns'`, and the missing prose).

- [ ] **Step 2: Implement**

In `src/shave/method.py`:
- Change `method_payload`'s signature to add `towns: list[dict] | None = None` after `calibration`. If the MECOLS plan has not landed, add it after `regression`.
- Add `"towns": list(towns or []),` to the returned dict.
- Delete the `Limitation("one_municipality", …)` entry from `KNOWN_GAPS`.
- Add as the last entry of `LIMITATIONS`:

```python
    Limitation(
        "three_towns_not_the_design_docs_three",
        "Three municipalities: Worcester, Fall River and Lowell. The design doc "
        "named New Bedford and Chicopee alongside Worcester, but MassGIS's "
        "electricity-provider layer lists New Bedford as Eversource and Chicopee "
        "as a municipal light plant, so National Grid's G-2/G-3 tariff never "
        "applies there. Fall River and Lowell, both National Grid mill cities, "
        "replace them. Each town's figures come from its own assessor extract, "
        "and the assessor year is shown per town.",
    ),
```

In `public/app.js` `methodHTML`, directly after the `${esc(cov.sweet_spot)} sit in the sweet spot …</p>` paragraph in `prose`, add:

```js
    ((payload.towns || []).length
      ? `<p>Covers ${(payload.towns || [])
          .map((t) => `${esc(t.name)} (assessor FY ${esc(t.assess_fy)})`)
          .join(", ")}.</p>`
      : "") +
```

- [ ] **Step 3: Run, rebuild, measure, commit**

```bash
uv run pytest
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run
uv run python scripts/build_site.py
uv run python -c "
import json, gzip, os
i = json.load(open('public/data/index.json')); print('default', i['default'], [(t['slug'], t['assess_fy'], t['counts']['kept']) for t in i['towns']])
for t in i['towns']:
    p = f\"public/data/towns/{t['slug']}/ranked.json\"; b = open(p,'rb').read()
    print(t['slug'], len(b)//1024, 'KB raw', len(gzip.compress(b))//1024, 'KB gzip')
a = json.load(open('public/data/addresses.json')); import collections; print('address entries by town', dict(collections.Counter(e['town'] for e in a['entries'])))
"
git add src/shave/method.py tests/test_method.py public/app.js web/render.test.js
git commit -m "feat: the method page names the three towns and why two changed

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

**Pass conditions, declared in advance:**
- Python **B + 6** (Task 1's 3 site_build + 1 addresses, and this task's 2 method tests); render **R + 1**;
- the index lists `worcester`, `fall-river`, `lowell` with `worcester` as default;
- each town payload under **2,000 KB raw** and **400 KB gzipped**;
- address entries exist for all three towns.

Report the figures.

---

## Task 3: The Municipality control

**Files:**
- Modify: `public/index.html` (toolbar), `public/app.js`, `public/app.css`
- Test: `web/render.test.js`

**Interfaces:**
- Produces:
  - `app.js` exports `townControlHTML(index, selected) -> string` and `townDataPath(slug) -> string`
  - `mapSVG(rows, viewBox, maxSaving, townName)`
  - address hits carry `data-town`

- [ ] **Step 1: Write the failing tests**

Append to `web/render.test.js`:

```js
import { townControlHTML, townDataPath } from "../public/app.js";

describe("townControlHTML", () => {
  const INDEX_2 = { towns: [
    { slug: "worcester", name: "Worcester" },
    { slug: "fall-river", name: "Fall River" },
    { slug: "lowell", name: "Low<ell" },
  ] };

  it("presses exactly the selected town", () => {
    const html = townControlHTML(INDEX_2, "fall-river");
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(html).toMatch(/data-town="fall-river" aria-pressed="true"/);
  });

  it("escapes town names and draws nothing without an index", () => {
    expect(townControlHTML(INDEX_2, "worcester")).not.toContain("Low<ell");
    expect(townControlHTML(null, "worcester")).toBe("");
  });

  it("builds each town's payload path from its slug", () => {
    expect(townDataPath("fall-river")).toBe("/data/towns/fall-river/ranked.json");
  });
});

describe("lookupHTML across towns", () => {
  it("tells a ranked hit which town to open", () => {
    const idx = { ...INDEX, entries: [{ ...INDEX.entries[0], town: "lowell" }] };
    const html = lookupHTML(lookup(idx, "385 Plantation St"), idx);
    expect(html).toContain('data-town="lowell"');
  });
});
```

Run vitest. Expected: FAIL — `townControlHTML is not a function`.

- [ ] **Step 2: Implement the pure pieces in `public/app.js`**

1. Change `const SUPPORTED_MAJOR = "1";` to `const SUPPORTED_MAJOR = "2";`.

2. Change `export function mapSVG(rows, viewBox, maxSaving) {` to `export function mapSVG(rows, viewBox, maxSaving, townName) {`, and in its final return replace the text `aria-label="Worcester parcels, shaded` with `aria-label="${esc(townName || "Covered")} parcels, shaded`.

3. In `hitHTML`, replace `data-list="${esc(entry.list)}">${body}</button></li>` with `data-list="${esc(entry.list)}" data-town="${esc(entry.town || "")}">${body}</button></li>`.

4. Insert directly before the `// wiring.` separator block:

```js
// ---------------------------------------------------------------------------
// towns. Each town's ranked payload loads when the reader first asks for it.
// ---------------------------------------------------------------------------

export function townDataPath(slug) {
  return `/data/towns/${encodeURIComponent(slug)}/ranked.json`;
}

export function townControlHTML(index, selected) {
  return ((index && index.towns) || [])
    .map(
      (t) =>
        `<button type="button" data-town="${esc(t.slug)}" ` +
        `aria-pressed="${t.slug === selected}">${esc(t.name)}</button>`,
    )
    .join("");
}
```

5. In the `state` object literal, add after `sitingRule: null,`:

```js
  index: null,
  town: null,
  townName: "",
  townCache: {},
```

6. In `draw()`, change `$("#map").innerHTML = mapSVG(state.shown, state.viewBox, maxSaving);` to `$("#map").innerHTML = mapSVG(state.shown, state.viewBox, maxSaving, state.townName);`.

7. Directly before `async function boot() {`, add:

```js
async function loadTown(slug) {
  if (!state.townCache[slug]) {
    const ranked = await (await fetch(townDataPath(slug))).json();
    if (String(ranked.site_schema_version || "").split(".")[0] !== SUPPORTED_MAJOR) {
      throw new Error(`town ${slug}: schema ${ranked.site_schema_version}`);
    }
    state.townCache[slug] = ranked;
  }
  const ranked = state.townCache[slug];
  state.town = slug;
  state.townName = (ranked.town || {}).name || "";
  state.lists = ranked.lists;
  state.viewBox = (ranked.map || {}).view_box || "0 0 620 818";
  state.dayAxis = ranked.day_axis || null;
  state.sitingRule = ranked.siting_rule || null;
  const c = ranked.counts;
  $("#counts").textContent =
    `${state.townName}: ${c.parcels_in.toLocaleString()} parcels screened · ` +
    `${c.kept.toLocaleString()} in band · ` +
    `${c.sweet_spot.toLocaleString()} in the sweet spot · ` +
    `showing top ${c.exported.comstock} measured and ${c.exported.modeled} modelled`;
  // Assessor vintage differs by town, so it is always stated with the town.
  const fy = (ranked.town || {}).assess_fy;
  $("#vintage").textContent = fy
    ? `${state.townName} assessor FY ${fy}`
    : "Assessor vintage unavailable";
  if (state.index) $("#towns").innerHTML = townControlHTML(state.index, slug);
  applyFilters();
}
```

- [ ] **Step 3: Rewire `boot()`**

Replace this block at the start of `boot()`:

```js
  let ranked;
  try {
    ranked = await (await fetch("/data/ranked.json")).json();
  } catch (err) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">The ranked list could not be loaded. ` +
      `It is served as static data, so this is a network problem rather than a ` +
      `problem with the data itself.</p></td></tr>`;
    return;
  }
  if (String(ranked.site_schema_version || "").split(".")[0] !== SUPPORTED_MAJOR) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">This page was built for schema ` +
      `${SUPPORTED_MAJOR}.x and the data is ${esc(ranked.site_schema_version)}. ` +
      `Refusing to render rather than draw wrong numbers.</p></td></tr>`;
    return;
  }

  state.lists = ranked.lists;
  state.viewBox = (ranked.map || {}).view_box || "0 0 620 818";
  state.dayAxis = ranked.day_axis || null;
  state.sitingRule = ranked.siting_rule || null;
  const c = ranked.counts;
  $("#counts").textContent =
    `${c.parcels_in.toLocaleString()} parcels screened · ` +
    `${c.kept.toLocaleString()} in band · ` +
    `${c.sweet_spot.toLocaleString()} in the sweet spot · ` +
    `showing top ${c.exported.comstock} measured and ${c.exported.modeled} modelled`;
  $("#whysplit").textContent = WHY_SPLIT;
  // The assessor vintage comes from the export's town block, not from the
  // method payload: `score_parcels` output carries no assess_fy -- that field
  // lives on the parcel frame -- so method.coverage.assess_years is empty.
  // Reading it here also shows the vintage before method.json has loaded.
  const fy = (ranked.town || {}).assess_fy;
  $("#vintage").textContent = fy ? `Assessor FY ${fy}` : "Assessor vintage unavailable";
  applyFilters();
```

with:

```js
  let index;
  try {
    index = await (await fetch("/data/index.json")).json();
  } catch (err) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">The ranked list could not be loaded. ` +
      `It is served as static data, so this is a network problem rather than a ` +
      `problem with the data itself.</p></td></tr>`;
    return;
  }
  if (String(index.site_schema_version || "").split(".")[0] !== SUPPORTED_MAJOR) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">This page was built for schema ` +
      `${SUPPORTED_MAJOR}.x and the data is ${esc(index.site_schema_version)}. ` +
      `Refusing to render rather than draw wrong numbers.</p></td></tr>`;
    return;
  }
  state.index = index;
  $("#whysplit").textContent = WHY_SPLIT;
  try {
    await loadTown(index.default);
  } catch (err) {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">This town's ranked list could not be ` +
      `loaded. It is served as static data, so this is a network problem rather ` +
      `than a problem with the data itself.</p></td></tr>`;
    return;
  }
  $("#towns").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-town]");
    if (b && b.dataset.town !== state.town) loadTown(b.dataset.town);
  });
```

Inside `boot()`, change the address jump helper and its caller:
- replace `function jumpTo(list, id) {` with `async function jumpTo(town, list, id) {`;
- insert as its first line `if (town && town !== state.town) await loadTown(town);`;
- replace `if (hit) jumpTo(hit.dataset.list, hit.dataset.id);` with `if (hit) jumpTo(hit.dataset.town, hit.dataset.list, hit.dataset.id);`.

- [ ] **Step 4: The control in the page**

In `public/index.html`, directly after `<div class="toolbar">`, insert:

```html
      <div class="seg" role="group" aria-label="Municipality" id="towns"></div>
```

In `public/index.html`, change the address input's `placeholder` to `e.g. 385 Plantation St, Worcester or 1 Merrimack St, Lowell`.

Append to `public/app.css`:

```css
/* ---------- municipality ---------- */
#towns:empty{display:none}
```

- [ ] **Step 5: Run, look, commit**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" vitest run
uv run pytest
uv run python scripts/build_site.py
"$NB/npx" wrangler dev --port 8787
```

**Pass conditions:** render **R + 5**; Python **B + 6**.

Confirm by eye at `http://127.0.0.1:8787/`, or with a Node render check if no browser is available, saying which:
- three town buttons, Worcester pressed;
- choosing Lowell redraws the list, map, counts and vintage for Lowell;
- the address box finds a Lowell address and opens it in Lowell's list;
- the network panel shows each town's `ranked.json` fetched once, on first choice.

```bash
git add public/index.html public/app.js public/app.css web/render.test.js
git commit -m "feat: the Municipality control

Worcester, Fall River and Lowell, each loaded the first time a reader asks for
it and cached after, so first paint still loads one town. Counts and assessor
vintage are stated per town. An address in another town opens in that town.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

---

## Task 4: Review and ship

- [ ] **Step 1: Update `docs/spec-coverage.md`**

- **Stage 1 row 1** notes: `Worcester, Fall River and Lowell — 3 towns of 3. The design doc's New Bedford (Eversource) and Chicopee (municipal light plant) are outside National Grid territory; see divergence 11.`
- **Stage 0 evidence:** the crosswalk now has 178 rows (121 statewide, 57 town-scoped for Fall River and Lowell).
- **Success criterion 7 evidence:** `Worcester, Fall River and Lowell.`
- **Pending table:** delete the New Bedford and Chicopee row and renumber.
- **Deliberate divergences:** add

  ```markdown
  **11. Fall River and Lowell, not New Bedford and Chicopee.** The design doc's own step — "None of the
  three towns is an MLP — confirm" — fails: MassGIS's electricity-provider layer (Department of Public
  Utilities, October 2025) lists New Bedford as Eversource and Chicopee as a municipal light plant, so the
  G-2/G-3 tariff every figure rests on never applies there. Fall River (a harbour mill city) and Lowell (a
  mill city) keep the doc's intent and are National Grid; `data/town_utilities.csv` is the committed record.
  ```

- **Header `Tests`** → the Task 3 counts.

- [ ] **Step 2: Commit, merge, deploy, verify**

```bash
git add docs/spec-coverage.md
git commit -m "docs: coverage review with three National Grid towns

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git checkout main && git pull --ff-only origin main
git merge --no-ff feat/three-town-site -m "merge: the three-town site

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" wrangler deploy
URL="https://shave.pjayav.workers.dev"; T=$(date +%s)
curl -s -o /dev/null -w 'index      %{http_code} %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'index.json %{http_code} %{time_total}s\n' "$URL/data/index.json?v=$T"
for s in worcester fall-river lowell; do curl -s -o /dev/null -w "$s %{http_code} %{time_total}s %{size_download}b\n" "$URL/data/towns/$s/ranked.json?v=$T"; done
```

**Pass conditions, declared in advance:** every request `200`; index + `index.json` + `towns/worcester/ranked.json` under **3 s** combined.

---

## Self-Review

**Spec coverage.**
- *"three towns ship"* → Tasks 1–3.
- The mockup's Municipality control → Task 3.
- *"assess_year per town … show it"* → the counts line, `#vintage`, and the method prose.
- Criterion 7 in every covered town → the address index over all three, with jump-to-town.
- Criterion 1 → first load is one town.

**Placeholder scan.** No code step is without code. The one conditional instruction (the MECOLS call) names the exact line to delete if that plan has not landed.

**Type consistency.**
- `town_payload` → `payload["town"]` carries `slug`, read by `index_payload`, by `loadTown` (`ranked.town.name`) and by `townControlHTML` (`t.slug`, `t.name`).
- `townDataPath(slug)` matches `site_build.town_data_path`.
- Address `entry.town` (slug) matches `data-town`, which `jumpTo(town, …)` passes to `loadTown`.

**Count arithmetic.** Python B → T1 +4 (3 site_build, 1 addresses) → T2 +2 (method) → **B + 6**, the figure both the Task 2 and Task 3 checkpoints use. Render R → T2 +1 → T3 +4 → **R + 5**.

**Risk.** `state.townCache` holds every visited town's payload in memory: about 1.4 MB each, three at most. That is acceptable, and noted rather than engineered around.
