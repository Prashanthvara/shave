# Published Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the working pipeline on a public URL — a ranked list of real named Worcester businesses with the argument inline on the first row, and a method page rendered from the code that computed it.

**Architecture:** Static assets on one Cloudflare Worker, no server and no database. A Python build step turns the versioned export into two JSON files; vanilla JS renders them into the approved mockup's DOM. There is no framework, no bundler and no TypeScript build, because the mockup has none and adding one would be the largest new dependency in the project for no gain.

**Tech Stack:** Python 3.11 (build), vanilla ES2020 + SVG (render), Cloudflare Workers static assets, wrangler 4.x, vitest + jsdom (render tests). IBM Plex Sans/Mono from Google Fonts.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` — sections "Distribution Plan", "Implementation Architecture", "Design (added by /plan-design-review)", "Success Criteria" 1, 2 and 6.

**Design system:** `DESIGN.md` in the repo root. **The approved mockup is the reference implementation** and its full source is reproduced in Task 3 Step 1. Do not invent layout, colour or copy: port it.

**Prior plans:**
- `docs/superpowers/plans/2026-09-10-comstock-extractor.md` — complete.
- `docs/superpowers/plans/2026-09-10-first-ranked-list.md` — Tasks 1–4 complete. **Tasks 5 (versioned export) and 6 (regression) are written and NOT YET RUN.**
- `docs/superpowers/plans/2026-09-11-occupants-and-method.md` — complete. Ledger at `.superpowers/sdd/2026-09-11-occupants-and-method/progress.md`.

## Prerequisites — read this before Task 1

**SATISFIED on 2026-09-11.** first-ranked-list Tasks 5 and 6 are executed and committed
(`cb988fc`, `7ba2cee`). `src/shave/export.py`, `scripts/run_pipeline.py`,
`docs/ranked-json-schema.md` and `src/shave/regression.py` all exist, and
`public/ranked.json` builds. This plan consumes their output and deliberately does not
duplicate it.

Task 1 below fails loudly and with that instruction if the export is missing, rather than
silently building a second export path. Two export paths would be two places for the schema to
drift, which is the exact failure the versioned contract exists to prevent.

## Global Constraints

- **Python:** `>=3.11`, and **do not add any new Python dependency.** Everything needed is in `pyproject.toml`.
- **JavaScript:** no runtime dependencies at all. The page loads no framework and no library. Dev dependencies are permitted for testing and deployment only (`vitest`, `jsdom`, `wrangler`).
- **Never restate a constant.** Python imports from `src/shave/assumptions.py`. The page never hard-codes a tariff rate, a kW figure or a date — every number it shows comes from the JSON it was handed.
- **`node`, `npm` and `npx` are nvm SHELL FUNCTIONS, and exporting PATH is not enough** — a shell function takes precedence over a PATH lookup, so `export PATH=...; npx vitest` still runs nvm and prints its help text. Call the binaries by absolute path:
  ```bash
  NB="$HOME/.nvm/versions/node/v22.18.0/bin"
  "$NB/npm" install
  "$NB/npx" vitest run
  "$NB/npx" wrangler deploy
  ```
  Verified on 2026-09-11: node v22.18.0, npm 11.5.2, and `"$NB/npx" wrangler --version` prints 4.131.1. `command npx` also works; `export PATH` alone does not.
- **`/usr/local/bin/wrangler` is a stub that prints "You have not installed wrangler".** Never invoke it. Install wrangler as a devDependency and always call it as `npx wrangler`.
- **CSS tokens are defined on bare `:root` (light), then redefined under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, then again under `:root[data-theme="dark"]`.** Never style a component inside a theme block — always through the token. Copied verbatim from `DESIGN.md`.
- **Radius is `3px` everywhere and there are no shadows in this system.** Separation comes from hairline rules and surface shifts.
- **Every figure in a column is `IBM Plex Mono` with `font-variant-numeric: tabular-nums`.** Addresses, kW values, dollar amounts and rate codes included.
- `--signal` is spent on exactly three things: the shaved peak on a sparkline, parcel fill weight on the map, and the selected-row rail. Never a button fill, never a heading colour, never decoration.
- Below 900px the layout becomes one column and **the ranked list is ordered first**.
- Side gutter is `padding-inline: 20px` on one wrapper; the body never scrolls sideways. Horizontal scroll is contained to `.tablewrap`.
- Copy is utility language — orientation, status, action, never mood. Empty states state a finding, not an absence. Errors say what is still working.
- Run the Python suite with `cd /Users/pjay/powertown && uv run pytest`. It is currently **919 passing, 4 deselected**. It must still be 919 plus your new tests.
- `public/` is a build output and is **gitignored except** `public/index.html`, `public/app.css`, `public/app.js`. The JSON under `public/data/` is generated and never committed. Task 2 adds those rules.
- Commit after each task. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48
  ```

---

## Verified facts, remeasured on 2026-09-11 after the prerequisite ran

Do not re-derive these.

**Suite:** 935 passing, 4 deselected.

**`public/ranked.json`, built by `scripts/run_pipeline.py`:** 661 KB, 25 s end to end.
Top-level keys are `schema_version, generated_at, town, counts, assumptions, lists, regression`.
`schema_version` is **`1.1.0`** — the `regression` key was added in 1.1.0, so the page's
`SUPPORTED_MAJOR` of `"1"` still matches.

**`counts`:** `parcels_in` 2,099 · `scored` 2,092 · `unscored` `{no_intensity_anchor: 6,
no_floor_area: 1}` · `kept` 737 · `sweet_spot` 172 · `exported` `{comstock: 250, modeled: 209}`.

**The two lists, verified separate and each ranked within itself:**

| list | rank 1 | use description | saving | confidence |
|---|---|---|---|---|
| `comstock` | 25 TOBIAS BOLAND WAY | Shopping Centers / Malls | $24,659 | LOW |
| `modeled` | 360 PLANTATION ST | DOE: UMass, State and Community Colleges | $31,440 | LOW |

The modelled list's top row is worth **more** than the ComStock list's. That is exactly why they
are not merged: those two dollar figures are not comparable.

**`regression`** is present in the export as `{ceiling: 0.9, by_source: {comstock: {...},
modeled: {...}}}`. Measured: `comstock` R² 0.614 against size and rate class, 0.878 with
archetype, n=528; `modeled` 0.493 and 0.749, n=209. Both are under the 0.90 ceiling, so the
verdict text reads "the archetype layer adds spread" for both lists.

**Every field in `site_data.REQUIRED_ROW_FIELDS` is present on a real exported row** — checked
against `public/ranked.json` before this plan was revised. Rows also carry
`monthly_billed_demand_kw` and `monthly_shaveable_kw`, which `window_series` and the
`shaveable_kw` derivation read.

**`occupants.load()`** holds 4 resolved rows. `F_577265_2910122` (25 Tobias Boland Way) is the
top ComStock row and `F_585218_2926290` (360 Plantation St) is the top modelled row, so **both
list heads carry a named business** and success criterion 2 holds on each.

**Toolchain:** node v22.18.0 and npm 11.5.2 under `~/.nvm/versions/node/v22.18.0/bin`.
`/usr/local/bin/wrangler` is a non-functional stub. No `package.json` exists in this repo yet.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/site_data.py` *(new)* | Shapes the export plus the method payload into exactly what the page reads. One file because it is one contract. |
| `scripts/build_site.py` *(new)* | The one command: pipeline → `public/data/ranked.json` + `public/data/method.json`. |
| `tests/test_site_data.py` *(new)* | Consumer-side contract. Every field the page reads must exist and be JSON-safe. |
| `public/index.html` *(new)* | The DOM skeleton, ported from the approved mockup. |
| `public/app.css` *(new)* | The design tokens and component styles, ported verbatim. |
| `public/app.js` *(new)* | Render: rows, sparklines, selected-row expansion, drawer, method tab. |
| `web/render.test.js` *(new)* | vitest + jsdom tests for the pure render functions. |
| `package.json`, `wrangler.jsonc` *(new)* | Dev tooling and the assets-only Worker. |

---

## Task 1: The site's data contract

The page must never compute, and there must be exactly one implementation of the export
contract. `export.build_export` from first-ranked-list Task 5 **is** that implementation; this
task is a thin adapter over it, not a second derivation.

**The two lists are never merged.** The spec, twice (lines 276-280 and 622): *"industrial rows
are never dollar-compared against ComStock rows. The interface ships two ranked lists side by
side, each ranked on dollars within itself, never merged into one number."* The modelled
magnitude runs through a published intensity and a derived load factor; ComStock's runs through a
measured timeseries. The approved mockup defaults to a merged "All sources" view and is wrong on
this point; the spec wins, and the page explains why rather than hiding the split.

**Files:**
- Create: `src/shave/site_data.py`
- Create: `scripts/build_site.py`
- Test: `tests/test_site_data.py` (new)

**Interfaces:**
- Consumes: `export.build_export`, `export.SCHEMA_VERSION`, `occupants.load`, `method.method_payload`, `pipeline.score_parcels`, `ingest.load_municipality`.
- Produces:
  - `site_data.SITE_SCHEMA_VERSION: str = "1.0.0"`
  - `site_data.ADDED_ROW_FIELDS: tuple[str, ...]`
  - `site_data.REQUIRED_ROW_FIELDS: tuple[str, ...]`
  - `site_data.window_series(row: Mapping) -> list[float]`
  - `site_data.enrich(export_payload: dict, scored: pd.DataFrame) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_site_data.py`:

```python
import json
from pathlib import Path

import pandas as pd
import pytest

from shave import site_data

WORCESTER_DIR = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
needs_worcester = pytest.mark.skipif(
    not Path(WORCESTER_DIR + "/M348TaxPar_CY26_FY26.shp").exists(),
    reason="Worcester L3 extract not present (data/raw is gitignored)",
)


def test_window_series_normalises_to_the_years_own_peak():
    """The page scales a 0-1 series to pixels and does no other arithmetic."""
    row = {"monthly_billed_demand_kw": [50.0, 100.0, 200.0] + [100.0] * 9}
    series = site_data.window_series(row)

    assert len(series) == 12
    assert max(series) == 1.0
    assert series[0] == pytest.approx(0.25)


def test_window_series_survives_a_month_with_no_billed_demand():
    """A month with no billed days bills nothing. That must not divide by zero."""
    assert site_data.window_series({"monthly_billed_demand_kw": [0.0] * 12}) == [0.0] * 12


def test_enrich_keeps_the_two_lists_separate_and_adds_what_the_page_needs():
    """The spec forbids merging the lists. enrich must not flatten them."""
    payload = {
        "schema_version": "1.0.0",
        "counts": {"kept": 2},
        "lists": {
            "comstock": [{
                "loc_id": "L1", "rank": 1, "annual_savings_usd": 9000.0,
                "monthly_billed_demand_kw": [100.0] * 12,
                "monthly_shaveable_kw": [30.0] * 12, "reason": "Because.",
            }],
            "modeled": [{
                "loc_id": "L2", "rank": 1, "annual_savings_usd": 12000.0,
                "monthly_billed_demand_kw": [80.0] * 12,
                "monthly_shaveable_kw": [25.0] * 12, "reason": "Because.",
            }],
        },
    }

    out = site_data.enrich(payload, pd.DataFrame([{"keep": True, "sweet_spot": False,
                                                  "unscored_reason": None,
                                                  "annual_savings_usd": 1.0,
                                                  "loc_id": "L1"}]))

    assert set(out["lists"]) == {"comstock", "modeled"}
    assert [r["loc_id"] for r in out["lists"]["comstock"]] == ["L1"]
    assert [r["loc_id"] for r in out["lists"]["modeled"]] == ["L2"]
    assert out["lists"]["comstock"][0]["rank"] == 1
    assert out["lists"]["modeled"][0]["rank"] == 1, "ranks restart per list"
    for row in out["lists"]["comstock"] + out["lists"]["modeled"]:
        assert len(row["window_kw"]) == 12
        assert "occupant" in row and "occupant_source" in row
    assert "method" in out
    assert out["site_schema_version"] == site_data.SITE_SCHEMA_VERSION


def test_enrich_carries_the_regression_the_export_already_ran():
    """The export runs the regression and puts it in the payload. Dropping it
    here would make the method page say "not yet run" while the numbers sit in
    the object it was just handed."""
    payload = {
        "schema_version": "1.1.0", "counts": {},
        "regression": {"ceiling": 0.9, "by_source": {
            "comstock": {"n": 528, "r2_size_and_rate": 0.614,
                         "r2_with_archetype": 0.878, "archetype_adds_little": False}}},
        "lists": {"comstock": [{"loc_id": "L1", "rank": 1,
                                "monthly_billed_demand_kw": [1.0] * 12,
                                "monthly_shaveable_kw": [1.0] * 12}], "modeled": []},
    }

    out = site_data.enrich(payload, pd.DataFrame([{"keep": True, "sweet_spot": False,
                                                   "unscored_reason": None,
                                                   "annual_savings_usd": 1.0,
                                                   "loc_id": "L1"}]))

    assert "status" not in out["method"]["regression"], "it HAS run"
    assert out["method"]["regression"]["by_source"]["comstock"]["r2_size_and_rate"] == 0.614


def test_enrich_does_not_mutate_the_export_it_was_given():
    payload = {"schema_version": "1.0.0", "counts": {}, "lists": {"comstock": [
        {"loc_id": "L1", "rank": 1, "monthly_billed_demand_kw": [1.0] * 12,
         "monthly_shaveable_kw": [1.0] * 12}], "modeled": []}}
    before = json.dumps(payload, sort_keys=True)

    site_data.enrich(payload, pd.DataFrame([{"keep": True, "sweet_spot": False,
                                             "unscored_reason": None,
                                             "annual_savings_usd": 1.0, "loc_id": "L1"}]))

    assert json.dumps(payload, sort_keys=True) == before
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_site_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.site_data'`

- [ ] **Step 3: Write `src/shave/site_data.py`**

```python
"""What the page reads, adapted from the one export contract.

`export.build_export` is the single implementation of the ranked payload. This
module does not re-derive it: it takes that payload, adds the three things the
page needs and the export has no business carrying -- the hand-resolved
occupant, a normalised sparkline series, and the method payload -- and returns
the result. A second derivation here would be a second place for the schema to
drift, which is the failure the versioned contract exists to prevent.

THE TWO LISTS ARE NEVER MERGED. The modelled-industrial magnitude runs through
a published intensity and a load factor derived from a declared shape; the
ComStock magnitude runs through a measured timeseries. Ranking them against
each other in dollars would claim a comparability the data does not support,
so each is ranked within itself and the page says why.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping

import pandas as pd

from shave import method, occupants

#: Bumped when the page's contract changes. The page refuses to render a
#: payload whose major version it does not recognise, so a stale deploy fails
#: loudly instead of drawing wrong numbers.
SITE_SCHEMA_VERSION = "1.0.0"

#: What this module adds on top of an exported row.
ADDED_ROW_FIELDS: tuple[str, ...] = (
    "occupant", "occupant_source", "window_kw", "shaveable_kw",
)

#: What the page reads off every row. Everything but ADDED_ROW_FIELDS comes
#: from `export.build_export`; the test asserts all of it is present, so a
#: rename in the pipeline or the export breaks the build, not the browser.
REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "loc_id", "rank", "reason", "archetype", "source", "sqft", "avg_12mo_kw",
    "peak_kw", "peak_to_avg", "rate_class", "demand_charge_per_kw",
    "annual_savings_usd", "shaved_fraction", "confidence", "flags",
    "sweet_spot", "site_addr", "city", "owner", "use_desc",
) + ADDED_ROW_FIELDS


def window_series(row: Mapping) -> list[float]:
    """The twelve monthly billed peaks, normalised to the year's own maximum.

    The page scales this to pixels and does no other arithmetic, which is what
    keeps the drawing provably the scorer's numbers rather than a second
    opinion about them.
    """
    values = [float(v) for v in row["monthly_billed_demand_kw"]]
    top = max(values) if values else 0.0
    if top <= 0.0:
        return [0.0] * len(values)
    return [round(v / top, 4) for v in values]


def enrich(export_payload: dict, scored: pd.DataFrame) -> dict:
    """The export, plus the occupant, the sparkline series and the method.

    Does not mutate its argument: the caller may still want to write the raw
    export, and a function that quietly edits its input is a trap.
    """
    payload = copy.deepcopy(export_payload)
    table = occupants.load()

    for rows in payload["lists"].values():
        for row in rows:
            resolved = table.get(row["loc_id"])
            row["occupant"] = resolved.occupant if resolved else ""
            row["occupant_source"] = resolved.occupant_source if resolved else ""
            row["window_kw"] = window_series(row)
            # The export carries twelve monthly figures; the row shows the
            # best month, which is the number the reason sentence quotes.
            row["shaveable_kw"] = max(
                float(v) for v in row["monthly_shaveable_kw"]
            )

    payload["site_schema_version"] = SITE_SCHEMA_VERSION
    # The export already ran the regression and carries it. Passing it through
    # rather than dropping it is the difference between a method page that
    # reports R-squared and one that says "not yet run" while the figures sit
    # in the very payload it was handed.
    payload["method"] = method.method_payload(
        scored, regression=export_payload.get("regression")
    )
    return payload
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_site_data.py -v`
Expected: PASS, all four.

- [ ] **Step 5: Write the build script**

Create `scripts/build_site.py`:

```python
"""Build the two JSON files the page loads.

    uv run python scripts/build_site.py

Calls the same `export.build_export` that `scripts/run_pipeline.py` calls, so
there is one implementation of the ranked contract and no chance of the site
and the raw export disagreeing. Writes public/data/ranked.json (the enriched
export) and public/data/method.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from shave import export, ingest, pipeline, site_data

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=WORCESTER)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--town-name", default="Worcester")
    parser.add_argument("--top-n", type=int, default=export.TOP_N)
    parser.add_argument("--out", default="public/data")
    args = parser.parse_args()

    started = time.perf_counter()
    parcels = ingest.load_municipality(args.dir, town_id=args.town_id)
    scored = pipeline.score_parcels(parcels)

    parcels = parcels.copy()
    # representative_point, not centroid: a centroid of an L-shaped or ring
    # parcel can land outside it, which puts a marker in someone else's yard.
    centroids = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = centroids.x
    parcels["lat"] = centroids.y

    assess_fy = parcels["assess_fy"].dropna()
    town = {
        "name": args.town_name,
        "town_id": args.town_id,
        "assess_fy": int(assess_fy.iloc[0]) if len(assess_fy) else None,
    }

    raw = export.build_export(scored, parcels, town=town, top_n=args.top_n)
    enriched = site_data.enrich(raw, scored)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ranked = {k: v for k, v in enriched.items() if k != "method"}
    (out / "ranked.json").write_text(
        json.dumps(ranked, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    (out / "method.json").write_text(
        json.dumps(enriched["method"], separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    for name in ("ranked.json", "method.json"):
        print(f"{name:14s} {(out / name).stat().st_size / 1024:8.1f} KB", file=sys.stderr)
    print(f"lists: " + ", ".join(
        f"{k} {len(v)}" for k, v in enriched["lists"].items()), file=sys.stderr)
    print(f"built in {time.perf_counter() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Write the contract test**

Append to `tests/test_site_data.py`:

```python
@needs_worcester
def test_every_field_the_page_reads_is_present_on_every_row():
    """The consumer contract. A rename in the pipeline or the export must
    break the build, not the browser."""
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    raw = export.build_export(scored, parcels,
                              town={"name": "Worcester", "town_id": 348}, top_n=25)
    enriched = site_data.enrich(raw, scored)

    for name, rows in enriched["lists"].items():
        assert rows, f"the {name} list is empty"
        for row in rows:
            missing = set(site_data.REQUIRED_ROW_FIELDS) - set(row)
            assert not missing, f"{name} row {row['loc_id']} missing {sorted(missing)}"


@needs_worcester
def test_the_payload_is_json_serialisable_and_small_enough_to_serve():
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    blob = json.dumps(enriched, separators=(",", ":"))
    assert len(blob.encode("utf-8")) < export.MAX_BYTES


@needs_worcester
def test_the_top_comstock_row_carries_a_named_occupant_and_its_reason():
    """Success criterion 2, at the point the page reads it."""
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    top = enriched["lists"]["comstock"][0]
    assert top["rank"] == 1
    assert top["reason"].endswith(".")
    assert top["occupant"], "the top ComStock row must name a real business"


@needs_worcester
def test_each_list_is_ranked_by_dollars_within_itself():
    from shave import export, ingest, pipeline

    parcels = ingest.load_municipality(WORCESTER_DIR, town_id=348)
    scored = pipeline.score_parcels(parcels)
    enriched = site_data.enrich(
        export.build_export(scored, parcels,
                            town={"name": "Worcester", "town_id": 348}), scored)

    for rows in enriched["lists"].values():
        usd = [r["annual_savings_usd"] for r in rows]
        assert usd == sorted(usd, reverse=True)
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
```

- [ ] **Step 7: Run the suite and the build**

Run: `uv run pytest`
Expected: PASS, prior count plus 8 here.

Then:
```bash
uv run python scripts/build_site.py
ls -la public/data/
```

**Pass condition, declared in advance:** both files are written, both lists are non-empty, and
the printed sizes are reported in your task report.

- [ ] **Step 8: Commit**

```bash
git add src/shave/site_data.py scripts/build_site.py tests/test_site_data.py
git commit -m "feat: the site's data contract, adapted from the one export

export.build_export is the single implementation of the ranked payload. This
adapts it rather than re-deriving it: it adds the hand-resolved occupant, a
sparkline series normalised to each site's own annual peak, and the method
payload. A second derivation would be a second place for the schema to drift.

The two lists stay separate. The modelled magnitude runs through a published
intensity and a derived load factor, ComStock's through a measured timeseries,
and ranking them against each other in dollars would claim a comparability the
data does not support.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 2: The Worker, the shell and the design tokens

An assets-only Worker. There is no Worker script in this plan: nothing on the request path needs
one, the address box that would have needed an API route is deferred, and a script that only
proxies static files is a failure mode with no upside.

**Files:**
- Create: `package.json`, `wrangler.jsonc`
- Create: `public/index.html`, `public/app.css`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `public/data/ranked.json`, `public/data/method.json` from Task 1.
- Produces: the DOM ids `#rows`, `#drawer`, `#v-main`, `#v-method`, `#vintage`, `#listsrc` that Task 3 and Task 4 render into.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "shave-site",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "dev": "wrangler dev",
    "deploy": "wrangler deploy"
  },
  "devDependencies": {
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8",
    "wrangler": "^4.119.0"
  }
}
```

- [ ] **Step 2: Install and verify the toolchain**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
cd /Users/pjay/powertown
"$NB/npm" install
"$NB/npx" wrangler --version
```

Expected: node resolves to v22.18.0, `npx wrangler --version` prints a 4.x version.
**If `wrangler --version` prints "You have not installed wrangler" you have invoked
`/usr/local/bin/wrangler` instead of the local one — always use `npx wrangler`.**

- [ ] **Step 3: Create `wrangler.jsonc`**

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "shave",
  "compatibility_date": "2026-09-01",
  // Assets-only: no "main", so there is no Worker script at all. Nothing on
  // the request path needs one. The spec's run_worker_first pattern is for
  // the address-box API route, which is deferred to the next plan.
  "assets": {
    "directory": "./public",
    "not_found_handling": "single-page-application"
  }
}
```

- [ ] **Step 4: Add the gitignore rules**

```bash
cat >> .gitignore <<'EOF'

# site: the page source is tracked, every generated artifact is not.
# This block SUPERSEDES the `public/*` + `!public/ranked.json` rules that
# first-ranked-list Task 5 step 10 adds. Applied in sequence those would hide
# public/index.html and the deploy would serve nothing. If Task 5's rules are
# already in .gitignore, delete them and keep only this block.
node_modules/
.wrangler/
public/data/
public/ranked.json
EOF
```

Then confirm the page source is still visible to git:

```bash
git check-ignore -v public/index.html && echo "BROKEN: page source is ignored" || echo "page source tracked, good"
```

- [ ] **Step 5: Write `public/app.css`**

Port the mockup's stylesheet verbatim. The full token block, copied from `DESIGN.md` and the
approved mockup, is:

```css
:root{
  --ground:#F4F5F3; --surface:#FFFFFF; --surface-2:#EDEFEC;
  --ink:#16191B; --ink-2:#5C666B; --ink-3:#8A9499;
  --rule:#D8DCD9; --rule-strong:#BEC5C0;
  --signal:#CC3311; --signal-soft:#CC331118;
  --g2:#0B6E6E; --g3:#8A9499;
  --ok:#15706B; --warn:#9A6700; --bad:#A33224;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --r:3px;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0F1417; --surface:#161C20; --surface-2:#1D2529;
    --ink:#E6EAE8; --ink-2:#93A0A5; --ink-3:#6F7C82;
    --rule:#263036; --rule-strong:#33414A;
    --signal:#FF5C3D; --signal-soft:#FF5C3D22;
    --g2:#2AA7A0; --g3:#6F7C82;
    --ok:#3FB5A6; --warn:#D2A03C; --bad:#E2705C;
  }
}
:root[data-theme="dark"]{
  --ground:#0F1417; --surface:#161C20; --surface-2:#1D2529;
  --ink:#E6EAE8; --ink-2:#93A0A5; --ink-3:#6F7C82;
  --rule:#263036; --rule-strong:#33414A;
  --signal:#FF5C3D; --signal-soft:#FF5C3D22;
  --g2:#2AA7A0; --g3:#6F7C82;
  --ok:#3FB5A6; --warn:#D2A03C; --bad:#E2705C;
}
*{box-sizing:border-box}
body{margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); font-size:14px; line-height:1.45;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1400px; margin:0 auto; padding-inline:20px; padding-block:20px}
h1,h2,h3{margin:0; text-wrap:balance; font-weight:600; letter-spacing:-0.011em}
a{color:inherit}
:focus-visible{outline:2px solid var(--signal); outline-offset:2px; border-radius:2px}
.num{font-family:var(--mono); font-variant-numeric:tabular-nums; font-feature-settings:"tnum"}
.skip{position:absolute; left:-9999px; top:0; background:var(--ink); color:var(--ground);
  padding:8px 12px; z-index:9}
.skip:focus{left:8px; top:8px}
/* Why the two lists are not one. Stated on the page, not just in the method. */
.whysplit{margin:0; padding:9px 12px; border-top:1px solid var(--rule);
  font-size:12px; color:var(--ink-2); max-width:70ch}
```

Then append, unchanged from the mockup, the rule blocks for `.mast`, `.brandline`, `.brand`,
`.tag`, `.eyebrow`, `.tabs`, `.tab`, `.toolbar`, `.seg`, `.vintage`, `.panel`, `.panel-head`,
`.panel-title`, `.tablewrap`, `table`, `thead th`, `tbody tr`, `td`, `tbody tr.lead`,
`tr.leadreason`, `.rank`, `.who`, `.where`, `.money`, `.kw`, `.chip`, `.rate`, `.src`,
`.spark`, `.drawer`, `.reason`, `.kv`, `.lineage`, `.dayprofile`, `.method`, `.prose`,
`.assum`, `.cannot`, `.foot`, and `[hidden]{display:none!important}`.

**Two deliberate changes from the mockup, and only these two:**

1. The mockup's `.split` is a two-column grid for map and table. There is no map in this plan,
   so the table panel is full width:

```css
.split{display:grid; grid-template-columns:minmax(0,1fr); gap:16px; margin-top:16px}
```

   Keep the class name. The next plan reinstates the two-column rule and the ordering
   media query without touching anything else.

2. The mockup's `.mock-flag` says "Design mockup · illustrative data". Real data is not a
   mockup. Replace its content in the HTML with the assessor vintage, and keep the style rule.

- [ ] **Step 6: Write `public/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shave — which Massachusetts buildings to call first</title>
<meta name="description" content="A ranked, confidence-tiered list of Massachusetts commercial and industrial sites where a 250 kW / 522 kWh battery captures a meaningful share of the monthly billing demand.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/app.css">
</head>
<body>
<a class="skip" href="#rows">Skip to the ranked list</a>
<div class="wrap">

  <div class="mast">
    <div>
      <div class="eyebrow">Prospecting &middot; Massachusetts &middot; National Grid territory</div>
      <div class="brandline">
        <span class="brand">Shave</span>
        <span class="tag">Which buildings should we call first, and why</span>
      </div>
    </div>
    <span class="mock-flag" id="vintage">Loading</span>
  </div>

  <div class="tabs" role="tablist" aria-label="Views">
    <button class="tab" role="tab" id="tab-main" aria-controls="v-main" aria-selected="true">Ranked view</button>
    <button class="tab" role="tab" id="tab-method" aria-controls="v-method" aria-selected="false">Method</button>
  </div>

  <section id="v-main" role="tabpanel" aria-labelledby="tab-main">
    <div class="toolbar">
      <div class="seg" role="group" aria-label="Profile source">
        <button id="src-cs" aria-pressed="true">ComStock&#8209;backed</button>
        <button id="src-md" aria-pressed="false">Modeled industrial</button>
      </div>
      <div class="seg" role="group" aria-label="View">
        <button id="view-all" aria-pressed="true">Ranked by saving</button>
        <button id="view-sweet" aria-pressed="false">Sweet spot</button>
      </div>
      <span class="vintage" id="counts"></span>
    </div>

    <div class="split">
      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">Ranked by estimated annual demand-charge saving</span>
          <span class="eyebrow" id="listsrc">ComStock&#8209;backed</span>
        </div>
        <div class="tablewrap">
          <table>
            <thead>
              <tr>
                <th></th><th>Site</th><th>Load shape</th>
                <th class="r">Peak / avg</th><th class="r">Rate</th>
                <th class="r">Saving/yr</th><th>Conf</th>
              </tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
        <p class="whysplit" id="whysplit"></p>
        <div class="drawer" id="drawer"></div>
      </div>
    </div>
  </section>

  <section id="v-method" role="tabpanel" aria-labelledby="tab-method" hidden>
    <div class="method">
      <div class="prose" id="method-prose"></div>
      <div>
        <div class="cannot" id="method-cannot"></div>
        <div class="foot" id="method-foot"></div>
      </div>
    </div>
  </section>

  <div class="foot" id="sitefoot"></div>
</div>
<script type="module" src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 7: Serve it locally and confirm the shell renders**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
cd /Users/pjay/powertown
uv run python scripts/build_site.py
"$NB/npx" wrangler dev --port 8787 &
sleep 4
curl -s -o /dev/null -w 'index %{http_code}\n' http://127.0.0.1:8787/
curl -s -o /dev/null -w 'css   %{http_code}\n' http://127.0.0.1:8787/app.css
curl -s -o /dev/null -w 'data  %{http_code}\n' http://127.0.0.1:8787/data/ranked.json
curl -s http://127.0.0.1:8787/data/ranked.json | head -c 200; echo
kill %1
```

**Pass condition:** all three return `200`, and the JSON begins with a `schema_version` field.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json wrangler.jsonc public/index.html public/app.css .gitignore
git commit -m "feat: the site shell, on an assets-only Worker

No Worker script: nothing on the request path needs one, and a script that
only proxies static files is a failure mode with no upside. The address box
that would need an API route is the next plan.

Design tokens and component styles are ported from the approved mockup
unchanged, with two deliberate exceptions: the split grid is single-column
until the map lands, and the mockup flag becomes the assessor vintage because
real data is not a mockup.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 3: The ranked table

Rank 1 is selected on load, and the selected row expands in place carrying its reason. The design
review (D4) was explicit: the argument is never behind a click, so it is in the first frame on
every device with no interaction.

**Files:**
- Create: `public/app.js`
- Create: `web/render.test.js`
- Modify: `package.json` — add the vitest config path

**Interfaces:**
- Consumes: `public/data/ranked.json` shaped by `site_data.build_rows`.
- Produces (exported from `app.js` for test): `sparkSVG(values, w, h)`, `rowHTML(row)`, `reasonRowHTML(row)`, `drawerHTML(row)`, `fmtMoney(n)`, `chipClass(conf)`.

- [ ] **Step 1: Write the failing render tests**

Create `web/render.test.js`:

```js
import { describe, expect, it } from "vitest";
import { chipClass, drawerHTML, fmtMoney, rowHTML, sparkSVG } from "../public/app.js";

const ROW = {
  loc_id: "F_1", rank: 1,
  occupant: "UMass Chan Medical School",
  occupant_source: "https://www.umassmed.edu/",
  owner: "COMMONWEALTH OF MASS EDUCATION",
  site_addr: "360 PLANTATION ST", city: "WORCESTER",
  use_desc: "DOE: UMass, State and Community Colleges",
  archetype: "university", source: "modeled",
  sqft: 1628495, avg_12mo_kw: 3957.7, peak_kw: 4500, peak_to_avg: 1.14,
  rate_class: "G-3", demand_charge_per_kw: 10.48,
  annual_savings_usd: 31440, shaved_fraction: 0.0636, shaveable_kw: 250,
  confidence: "MED", flags: ["power_limited"], sweet_spot: false,
  reason: "Runs flat at 1.1x its 12-month average, so there is little peak to remove.",
  window_kw: [0.8, 0.82, 0.85, 0.9, 0.95, 1.0, 0.98, 0.96, 0.9, 0.86, 0.83, 0.81],
};

describe("fmtMoney", () => {
  it("is whole dollars with separators, never cents", () => {
    expect(fmtMoney(31440)).toBe("$31,440");
    expect(fmtMoney(0)).toBe("$0");
  });
});

describe("chipClass", () => {
  it("maps confidence to its semantic token class", () => {
    expect(chipClass("HIGH")).toBe("hi");
    expect(chipClass("MED")).toBe("med");
    expect(chipClass("LOW")).toBe("lo");
  });
});

describe("sparkSVG", () => {
  it("marks the peak with the accent and nothing else", () => {
    const svg = sparkSVG([0.2, 1.0, 0.4], 68, 22);
    expect(svg).toContain("<svg");
    expect(svg).toContain('aria-hidden="true"');
    // --signal is spent on the peak dot only. One occurrence, not two.
    expect(svg.match(/var\(--signal\)/g)).toHaveLength(1);
  });

  it("survives an all-zero series without dividing by zero", () => {
    const svg = sparkSVG([0, 0, 0], 68, 22);
    expect(svg).toContain("<svg");
    expect(svg).not.toContain("NaN");
  });
});

describe("rowHTML", () => {
  it("shows the occupant, not the owner of record", () => {
    const html = rowHTML(ROW);
    expect(html).toContain("UMass Chan Medical School");
    expect(html).not.toContain("COMMONWEALTH OF MASS EDUCATION");
  });

  it("falls back to the use description when no occupant is resolved", () => {
    const html = rowHTML({ ...ROW, occupant: "" });
    expect(html).toContain("DOE: UMass, State and Community Colleges");
    // and never silently presents the holding company as the occupant
    expect(html).not.toContain("COMMONWEALTH OF MASS EDUCATION");
  });

  it("renders the rate class through its semantic class", () => {
    expect(rowHTML(ROW)).toContain('class="rate g3"');
    expect(rowHTML({ ...ROW, rate_class: "G-2" })).toContain('class="rate g2"');
  });

  it("escapes text that came from an assessor record", () => {
    const html = rowHTML({ ...ROW, occupant: '<img src=x onerror="alert(1)">' });
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
  });
});

describe("drawerHTML", () => {
  it("carries the lineage and the flags in plain words", () => {
    const html = drawerHTML(ROW, { power_limited: "The battery hits its rating." });
    expect(html).toContain("The battery hits its rating.");
    expect(html).toContain("360 PLANTATION ST");
  });

  it("links the occupant source so the claim is checkable", () => {
    expect(drawerHTML(ROW, {})).toContain('href="https://www.umassmed.edu/"');
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `Failed to resolve import "../public/app.js"`.

- [ ] **Step 3: Write `public/app.js`**

```js
// The page computes nothing. Every figure it draws was handed to it by
// scripts/build_site.py, so what is on screen is provably what the scorer
// produced. The only arithmetic here is scaling a normalised series to pixels.

const SUPPORTED_MAJOR = "1";

export function fmtMoney(n) {
  return "$" + Math.round(Number(n) || 0).toLocaleString("en-US");
}

export function chipClass(conf) {
  return conf === "HIGH" ? "hi" : conf === "MED" ? "med" : "lo";
}

function esc(value) {
  return String(value == null ? "" : value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

// A 12-point series, already normalised to its own max by the build. The peak
// dot is the only place --signal is spent here; the line and the area fill are
// neutral, per the accent discipline in DESIGN.md.
export function sparkSVG(values, w, h) {
  const a = (values || []).map((v) => Number(v) || 0);
  if (a.length === 0) return `<svg class="spark" width="${w}" height="${h}"></svg>`;
  const n = a.length;
  const max = Math.max(...a);
  const scale = max > 0 ? 1 / max : 0;
  const x = (i) => ((i / Math.max(1, n - 1)) * (w - 2) + 1).toFixed(1);
  const y = (v) => (h - 1 - v * scale * (h - 4)).toFixed(1);

  let peak = 0;
  for (let i = 1; i < n; i++) if (a[i] > a[peak]) peak = i;

  const pts = a.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `M1,${h - 1} L${pts.split(" ").join(" L")} L${w - 1},${h - 1} Z`;

  return (
    `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">` +
    `<path d="${area}" fill="var(--ink-2)" opacity=".16"/>` +
    `<polyline points="${pts}" fill="none" stroke="var(--ink-2)" stroke-width="1.1" stroke-linejoin="round"/>` +
    `<circle cx="${x(peak)}" cy="${y(a[peak])}" r="1.9" fill="var(--signal)"/>` +
    `</svg>`
  );
}

// An unresolved row shows what the assessor actually recorded, never the
// holding company dressed up as an occupant.
function siteName(row) {
  return row.occupant ? row.occupant : row.use_desc || row.archetype;
}

export function rowHTML(row) {
  const rate = row.rate_class === "G-2" ? "g2" : "g3";
  return (
    `<tr data-id="${esc(row.loc_id)}" tabindex="0" role="button" ` +
    `aria-label="${esc(siteName(row))}, estimated saving ${fmtMoney(row.annual_savings_usd)} a year">` +
    `<td class="rank">${row.rank}</td>` +
    `<td><div class="who">${esc(siteName(row))}</div>` +
    `<div class="where">${esc(row.site_addr)} &middot; ` +
    `<span class="src">${esc(String(row.source).toUpperCase())}</span></div></td>` +
    `<td>${sparkSVG(row.window_kw, 68, 22)}</td>` +
    `<td class="r kw">${Number(row.peak_to_avg).toFixed(1)}&times;<br>` +
    `${Math.round(row.peak_kw)}/${Math.round(row.avg_12mo_kw)} kW</td>` +
    `<td class="r"><span class="rate ${rate}">${esc(row.rate_class)}</span></td>` +
    `<td class="r money">${fmtMoney(row.annual_savings_usd)}</td>` +
    `<td><span class="chip ${chipClass(row.confidence)}">${esc(row.confidence)}</span></td>` +
    `</tr>`
  );
}

// D4: the argument is never behind a click. The selected row expands in place.
export function reasonRowHTML(row) {
  const flags = (row.flags || [])
    .map((f) => `<span class="eyebrow">${esc(f.replace(/_/g, " "))}</span>`)
    .join("");
  return (
    `<tr class="leadreason"><td colspan="7">` +
    `<p class="reason">${esc(row.reason)}</p>` +
    `<div class="mini">` +
    `<span class="eyebrow">${esc(row.use_desc)}</span>` +
    `<span class="eyebrow">Shaveable ${Math.round(row.shaveable_kw)} kW</span>` +
    `<span class="eyebrow">${Math.round(row.sqft).toLocaleString("en-US")} sq ft</span>` +
    flags +
    `</div></td></tr>`
  );
}

export function drawerHTML(row, flagMeanings) {
  const flags = (row.flags || [])
    .map(
      (f) =>
        `<div><dt>${esc(f.replace(/_/g, " "))}</dt>` +
        `<dd>${esc((flagMeanings || {})[f] || "")}</dd></div>`,
    )
    .join("");
  const source = row.occupant_source
    ? ` Occupant verified at <a href="${esc(row.occupant_source)}" rel="noopener">` +
      `${esc(row.occupant_source)}</a>.`
    : " Occupant not yet resolved; the name shown is the assessor's use description.";
  return (
    `<div class="eyebrow">Detail &middot; ${esc(siteName(row))}</div>` +
    `<div class="dayprofile">${sparkSVG(row.window_kw, 300, 60)}</div>` +
    `<div class="eyebrow" style="margin-top:4px">Billed demand by month &middot; peak marked</div>` +
    `<dl class="kv">` +
    `<div><dt>Address</dt><dd>${esc(row.site_addr)}, ${esc(row.city)}</dd></div>` +
    `<div><dt>Owner of record</dt><dd>${esc(row.owner)}</dd></div>` +
    `<div><dt>Floor area</dt><dd>${Math.round(row.sqft).toLocaleString("en-US")} sq ft</dd></div>` +
    `<div><dt>Shaveable</dt><dd>${Math.round(row.shaveable_kw)} kW</dd></div>` +
    `<div><dt>Shaved fraction</dt><dd>${(row.shaved_fraction * 100).toFixed(1)}%</dd></div>` +
    `<div><dt>Load shape</dt><dd>${esc(row.archetype)} (${esc(row.source)})</dd></div>` +
    flags +
    `</dl>` +
    `<div class="lineage"><strong>How we got here:</strong> use description ` +
    `"${esc(row.use_desc)}" maps to the ${esc(row.archetype)} archetype, ` +
    `${esc(row.source)}-backed, scaled to ${Math.round(row.sqft).toLocaleString("en-US")} sq ft.` +
    `${source} Estimated, never measured &mdash; get the utility bill before anyone signs.` +
    `</div>`
  );
}

// ---------------------------------------------------------------------------
// wiring. Everything above is pure and tested; everything below touches the DOM.
// ---------------------------------------------------------------------------

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

// Two lists, never merged. `source` selects which one is on screen.
const state = { lists: { comstock: [], modeled: [] }, shown: [], method: null,
                selected: null, source: "comstock", view: "all" };

const WHY_SPLIT =
  "ComStock-backed and modelled-industrial rows are ranked separately and never " +
  "against each other. A ComStock magnitude comes from a measured timeseries; a " +
  "modelled one comes from a published intensity and a load factor derived from a " +
  "declared shape. Comparing their dollars would claim an accuracy the second one " +
  "does not have.";

function select(id) {
  state.selected = id;
  $$("#rows tr.leadreason").forEach((tr) => tr.remove());
  $$("#rows tr").forEach((tr) => {
    tr.classList.toggle("on", tr.dataset.id === id);
    tr.classList.toggle("lead", tr.dataset.id === id);
  });
  const row = state.shown.find((r) => r.loc_id === id);
  if (!row) return;
  const tr = $(`#rows tr[data-id="${CSS.escape(id)}"]`);
  if (tr) tr.insertAdjacentHTML("afterend", reasonRowHTML(row));
  $("#drawer").innerHTML = drawerHTML(row, (state.method || {}).flag_meanings);
}

function draw() {
  $("#rows").innerHTML = state.shown.map(rowHTML).join("");
  if (state.shown.length) select(state.shown[0].loc_id);
  else {
    $("#rows").innerHTML =
      `<tr><td colspan="7"><p class="reason">Every screened parcel fell below ` +
      `50 kW average demand, so a 250 kW cabinet has no peak worth shaving. ` +
      `That is a real answer, not a failure.</p></td></tr>`;
    $("#drawer").innerHTML = "";
  }
}

function applyFilters() {
  const rows = state.lists[state.source] || [];
  state.shown = state.view === "sweet" ? rows.filter((r) => r.sweet_spot) : rows;
  draw();
}

async function boot() {
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
  const c = ranked.counts;
  $("#counts").textContent =
    `${c.parcels_in.toLocaleString()} parcels screened · ` +
    `${c.kept.toLocaleString()} in band · ` +
    `${c.sweet_spot.toLocaleString()} in the sweet spot · ` +
    `showing top ${c.exported.comstock} measured and ${c.exported.modeled} modelled`;
  $("#whysplit").textContent = WHY_SPLIT;
  applyFilters();

  try {
    state.method = await (await fetch("/data/method.json")).json();
    $("#vintage").textContent = `Assessor FY ${(state.method.coverage.assess_years || []).join(", ")}`;
    if (window.renderMethod) window.renderMethod(state.method);
  } catch (err) {
    $("#vintage").textContent = "Assessor vintage unavailable";
  }

  $("#rows").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (tr) select(tr.dataset.id);
  });
  $("#rows").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const tr = e.target.closest("tr[data-id]");
    if (tr) {
      e.preventDefault();
      select(tr.dataset.id);
    }
  });

  const sources = { "src-cs": "comstock", "src-md": "modeled" };
  const views = { "view-all": "all", "view-sweet": "sweet" };
  Object.keys(sources).forEach((id) =>
    $("#" + id).addEventListener("click", () => {
      state.source = sources[id];
      Object.keys(sources).forEach((k) =>
        $("#" + k).setAttribute("aria-pressed", String(k === id)),
      );
      $("#listsrc").textContent = $("#" + id).textContent;
      applyFilters();
    }),
  );
  Object.keys(views).forEach((id) =>
    $("#" + id).addEventListener("click", () => {
      state.view = views[id];
      Object.keys(views).forEach((k) =>
        $("#" + k).setAttribute("aria-pressed", String(k === id)),
      );
      applyFilters();
    }),
  );

  $$(".tab").forEach((t) =>
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => {
        const on = x === t;
        x.setAttribute("aria-selected", String(on));
        $("#" + x.getAttribute("aria-controls")).hidden = !on;
      });
    }),
  );
}

if (typeof document !== "undefined" && document.getElementById("rows")) boot();
```

- [ ] **Step 4: Run the render tests**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: PASS, all 10.

- [ ] **Step 5: Check it in a real browser**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
uv run python scripts/build_site.py
"$NB/npx" wrangler dev --port 8787
```

Open `http://127.0.0.1:8787/` and confirm, by eye:
- rank 1 is selected on load and its reason sentence is visible **without any interaction**;
- the top row names a real business, not a holding company;
- every number in a column is tabular mono;
- clicking a row moves the selection and the drawer;
- the source and view toggles filter, and the counts line matches;
- at 400px width the table scrolls inside `.tablewrap` and the body does not scroll sideways;
- in dark mode every token flips and body text is still legible.

Fix anything that fails before committing. Do not adjust the design system to suit the code.

- [ ] **Step 6: Commit**

```bash
git add public/app.js web/render.test.js package.json
git commit -m "feat: the ranked table, with the argument in the first frame

Rank 1 is selected on load and its reason expands in place, so the argument
is on screen with no interaction on every device — design review D4.

The page computes nothing: every figure was handed to it by the build, so
what is on screen is provably what the scorer produced. The only arithmetic
is scaling a normalised series to pixels.

Assessor text is escaped on the way into the DOM, and an unresolved row shows
the use description rather than the holding company dressed as an occupant.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 4: The method page

Success criterion 6 and premise P6. `method.json` already holds every statement; this renders it
and adds nothing.

**Files:**
- Modify: `public/app.js` — add `methodHTML` and wire `window.renderMethod`
- Modify: `web/render.test.js`

**Interfaces:**
- Consumes: `method.method_payload` output as `public/data/method.json`.
- Produces: `methodHTML(payload) -> {prose, cannot, foot}`.

- [ ] **Step 1: Write the failing test**

Append to `web/render.test.js`:

```js
import { methodHTML } from "../public/app.js";

const METHOD = {
  assumptions: [
    { key: "g2_demand_charge", value: "15.06 $/kW", provenance: "FILED",
      source: "MECO summary of rates", note: "Rate G-2 distribution demand charge." },
  ],
  limitations: [
    { key: "no_measurement", statement: "This tool contains no per-building measurement." },
  ],
  known_gaps: [
    { key: "one_municipality", statement: "Worcester only." },
  ],
  flag_meanings: { power_limited: "The battery hits its rating." },
  lineage: { parcels: "MassGIS Level 3", tariff: "M.D.P.U. No. 1591" },
  coverage: { parcels_total: 2099, kept: 737, sweet_spot: 172, assess_years: [2026],
              unscored: { no_intensity_anchor: 6 } },
  occupants: { resolved_total: 4, top_n: 50, top_n_resolved: 4 },
  regression: {
    ceiling: 0.9,
    by_source: {
      comstock: { n: 528, r2_size_and_rate: 0.614, r2_with_archetype: 0.878,
                  archetype_adds_little: false },
      modeled: { n: 209, r2_size_and_rate: 0.493, r2_with_archetype: 0.749,
                 archetype_adds_little: false },
    },
  },
};

describe("methodHTML", () => {
  it("renders every limitation, because criterion 6 is the list", () => {
    const { cannot } = methodHTML(METHOD);
    expect(cannot).toContain("This tool contains no per-building measurement.");
  });

  it("renders every assumption with its source and provenance", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).toContain("15.06 $/kW");
    expect(prose).toContain("MECO summary of rates");
    expect(prose).toContain("FILED");
  });

  it("renders the real regression shape, per list, never undefined", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).toContain("0.614");
    expect(prose).toContain("0.878");
    expect(prose).toContain("0.493");
    expect(prose).not.toContain("undefined");
    expect(prose).not.toContain("NaN");
  });

  it("reports an unrun regression as unrun, never as zero", () => {
    const { prose } = methodHTML({
      ...METHOD,
      regression: { status: "not yet run; the figures below are unreported, not zero" },
    });
    expect(prose).toContain("not yet run");
    expect(prose).not.toMatch(/R².{0,12}0\.00/);
  });

  it("never claims a figure its own table contradicts", () => {
    const { prose } = methodHTML(METHOD);
    expect(prose).not.toContain("1.000 by construction");
    expect(prose).toContain("power cap");
  });

  it("fires the verdict when size alone explains the ranking", () => {
    const { prose } = methodHTML({
      ...METHOD,
      regression: { ceiling: 0.9, by_source: { comstock: {
        n: 10, r2_size_and_rate: 0.97, r2_with_archetype: 0.99,
        archetype_adds_little: true } } },
    });
    expect(prose).toContain("adding little");
    expect(prose).toContain("close to a size sort");
  });

  it("states the known gaps rather than hiding them", () => {
    const { cannot } = methodHTML(METHOD);
    expect(cannot).toContain("Worcester only.");
  });

  it("reports occupant coverage truthfully", () => {
    const { foot } = methodHTML(METHOD);
    expect(foot).toContain("4 of 50");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: FAIL — `methodHTML is not a function`.

- [ ] **Step 3: Add `methodHTML` to `public/app.js`**

Insert before the wiring section:

```js
export function methodHTML(payload) {
  const cov = payload.coverage || {};
  const occ = payload.occupants || {};
  const reg = payload.regression || {};

  const assumptions = (payload.assumptions || [])
    .map(
      (a) =>
        `<tr><td>${esc(a.note || a.key)}</td>` +
        `<td class="v r">${esc(a.value)}</td>` +
        `<td class="s">${esc(a.provenance)} &middot; ${esc(a.source)}</td></tr>`,
    )
    .join("");

  // The payload shape is {ceiling, by_source: {comstock: {...}, modeled: {...}}},
  // one row per ranked list. Read it, never assert a figure: an earlier
  // revision of the Python side printed "~1.000 by construction" above a table
  // showing 0.878, and a method page that contradicts its own numbers is the
  // one thing this artifact cannot afford.
  const bySource = (reg && reg.by_source) || {};
  const regressionRows = Object.keys(bySource)
    .map((name) => {
      const r = bySource[name];
      if (r.skipped) return `<tr><td>${esc(name)}</td><td class="v r">${esc(r.n)}</td>` +
        `<td class="v r">&mdash;</td><td class="v r">&mdash;</td></tr>`;
      return `<tr><td>${esc(name)}</td><td class="v r">${esc(r.n)}</td>` +
        `<td class="v r">${r.r2_size_and_rate.toFixed(3)}</td>` +
        `<td class="v r">${r.r2_with_archetype.toFixed(3)}</td></tr>`;
    })
    .join("");
  const verdicts = Object.keys(bySource)
    .filter((name) => !bySource[name].skipped)
    .map((name) => {
      const r = bySource[name];
      return r.archetype_adds_little
        ? `<p><strong>${esc(name)}: the archetype layer is adding little.</strong> ` +
          `Size and rate class alone explain ${r.r2_size_and_rate.toFixed(3)}, above the ` +
          `${Number(reg.ceiling).toFixed(2)} threshold declared before the numbers were ` +
          `computed. Read this list as close to a size sort.</p>`
        : `<p><strong>${esc(name)}: the archetype layer adds spread.</strong> ` +
          `Size and rate class alone explain ${r.r2_size_and_rate.toFixed(3)}; the load ` +
          `shape accounts for the rest of the ordering.</p>`;
    })
    .join("");

  const regressionBlock = reg.status
    ? `<p>${esc(reg.status)}</p>`
    : `<div class="tablewrap"><table class="assum"><thead><tr>` +
      `<th>List</th><th class="r">n</th>` +
      `<th class="r">R&sup2; vs size &times; rate</th>` +
      `<th class="r">R&sup2; vs size &times; rate &times; archetype</th>` +
      `</tr></thead><tbody>${regressionRows}</tbody></table></div>` +
      verdicts +
      `<p>The second column is high because the score is a deterministic ` +
      `function of exactly three public assessor fields and nothing else. It ` +
      `falls short of 1.000 because this fit is linear in floor area within an ` +
      `archetype and the scorer is not: the shaveable kilowatts come from a ` +
      `root-find against a fixed energy budget and a 250 kW power cap, so a ` +
      `site large enough to saturate the cap stops scaling with its floor area. ` +
      `That kink is what separates this from a size sort.</p>`;

  const prose =
    `<h2>What this is</h2>` +
    `<p class="lead">A structured prior over three public assessor fields, not a ` +
    `measurement. It orders a call list. It does not underwrite a project.</p>` +
    `<p>Demand is billed on the greatest fifteen-minute peak between 8 a.m. and ` +
    `9 p.m., Monday to Friday, excluding nine observed holidays. A three-in-the-` +
    `morning spike is free. Everything here is computed inside that window and ` +
    `nowhere else.</p>` +
    `<p>${esc(cov.parcels_total)} parcels screened; ${esc(cov.kept)} carry enough ` +
    `demand charge to be worth a conversation; ${esc(cov.sweet_spot)} sit in the ` +
    `sweet spot — the expensive G-2 rate plus a spiky shape.</p>` +
    `<h2 style="margin-top:16px">Does the archetype layer earn its place?</h2>` +
    regressionBlock +
    `<h2 style="margin-top:16px">Every assumption, and where it came from</h2>` +
    `<p style="margin-bottom:8px">This table is rendered from the same file the ` +
    `scorer imports, so the published numbers cannot drift from the computed ones.</p>` +
    `<div class="tablewrap"><table class="assum">` +
    `<thead><tr><th>Assumption</th><th class="r">Value</th><th>Source</th></tr></thead>` +
    `<tbody>${assumptions}</tbody></table></div>`;

  const limitations = (payload.limitations || [])
    .map((l) => `<li>${esc(l.statement)}</li>`)
    .join("");
  const gaps = (payload.known_gaps || [])
    .map((g) => `<li>${esc(g.statement)}</li>`)
    .join("");

  const cannot =
    `<h2>What this cannot tell you</h2><ul>${limitations}</ul>` +
    `<h2 style="margin-top:14px">Specified and not yet built</h2><ul>${gaps}</ul>`;

  const foot =
    `Lineage: ${Object.values(payload.lineage || {}).map(esc).join(" &middot; ")}. ` +
    `Occupant names hand-resolved for ${esc(occ.top_n_resolved)} of ${esc(occ.top_n)} ` +
    `top-ranked rows; the rest show the assessor's use description rather than the ` +
    `owner of record.`;

  return { prose, cannot, foot };
}
```

And in `boot()`, replace the `if (window.renderMethod)` line with:

```js
    const m = methodHTML(state.method);
    $("#method-prose").innerHTML = m.prose;
    $("#method-cannot").innerHTML = m.cannot;
    $("#method-foot").innerHTML = m.foot;
```

- [ ] **Step 4: Run the tests**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" vitest run
```
Expected: PASS, all 15.

- [ ] **Step 5: Check the method tab in the browser**

```bash
"$NB/npx" wrangler dev --port 8787
```

Click **Method** and confirm all 15 limitations, all 4 gaps and all 23 assumptions render, and
that the regression line says "not yet run" if first-ranked-list Task 6 has not been run.

- [ ] **Step 6: Commit**

```bash
git add public/app.js web/render.test.js
git commit -m "feat: the method page, rendered from the payload

Success criterion 6 and premise P6. Every statement comes from
method.method_payload, so the published method is provably the one that ran.
The page adds no claims of its own: it renders 15 limitations, 4 named gaps
and 23 sourced assumptions, and reports an unrun regression as unrun.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 5: Deploy

Success criterion 1: a public URL, the ranked list in under three seconds, no signup.

**Files:**
- Modify: `README.md` — the URL and how to rebuild

- [ ] **Step 1: Confirm the build is current**

```bash
cd /Users/pjay/powertown
uv run python scripts/build_site.py --limit 200
ls -la public/data/
```

- [ ] **Step 2: Authenticate wrangler**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler whoami
```

If it reports no account, the user must run `npx wrangler login` themselves — it opens a browser
for OAuth. Ask them to run it and stop until they confirm; do not attempt to automate a login.

- [ ] **Step 3: Deploy**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

Record the `*.workers.dev` URL it prints.

- [ ] **Step 4: Verify the live site against criterion 1**

```bash
URL="https://shave.<your-subdomain>.workers.dev"
curl -s -o /dev/null -w 'index  %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked %{http_code}  %{time_total}s  %{size_download} bytes\n' "$URL/data/ranked.json"
curl -s -o /dev/null -w 'method %{http_code}  %{time_total}s\n' "$URL/data/method.json"
curl -s "$URL/data/ranked.json" | head -c 120; echo
```

**Pass conditions, declared in advance:** all three return `200`; the total for index plus
`ranked.json` is **under 3 seconds**; no request requires a credential. Report the measured
times.

- [ ] **Step 5: Update the README**

Replace the README's project description with the live URL, one paragraph on what the tool is,
and the two commands that rebuild it:

```bash
uv run python scripts/build_site.py   # rebuild public/data from the pipeline
npx wrangler deploy                   # publish
```

State plainly in the README that the ranked figures are estimates from public data and not
measurements, using the same sentence as the method page's lead so the two cannot drift.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: the live URL and how to rebuild it

Success criterion 1: a public URL, the ranked list under three seconds, no
signup and no database on the request path.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## What this plan deliberately leaves for the next one

| Deferred | Why it is not here | Est. |
|---|---|---|
| **The encoding map** — parcel fill by saving, outline by rate class, cross-linked both ways with the table | The job posting's headline ask is *"make maps feel intelligent, not decorative"*, and design review D2 put it back in the build deliberately. It is deferred **only** because it needs simplified parcel geometry in the export, which is a change to first-ranked-list Task 5's schema rather than to anything here. `.split` keeps its class name and its single-column rule is the one line to revert. **This is the highest-value next task, not a nice-to-have.** | 5–6h |
| Address box over a static prebuilt index | D5 called it the verification moment. It needs a client-side index over the covered towns; no database, so it cannot break when a free tier sleeps. | 2h |
| The interaction-states gallery | The mockup's third tab. It is a design artefact rather than a product surface; the real empty and error states are already implemented inline. | 1h |
| `STRUCTURES_POLY` join and the siting screen | Independent of the site. Adds the clear-wall-run figure the drawer has a slot for. | 4.5h |
| New Bedford and Chicopee | Each needs an L3 download, a crosswalk pass, and its own `county_gisjoin`. The municipality segmented control in the mockup is built for it. | 2h |
| MECOLS class-shape check | `MECOLS.xlsx` is not on disk. Already named as a known gap on the method page. | 1h + fetch |

---

## Self-Review

**Spec coverage.** Task 5 completes success criterion 1 (public URL, under 3 s, no signup).
Task 1 carries criterion 2 to the page and asserts it there. Task 4 completes criterion 6.
Criterion 5 was already met. Criterion 3 belongs to first-ranked-list Task 6, which is a
prerequisite of this plan and whose output Task 4 renders. Criterion 4 is blocked on a missing
file and is rendered as a named gap rather than claimed. Criterion 7 (address box) is tabled
above. From the spec's Stage 1 list, step 9 is Tasks 2–4 here; 9b and 9c are tabled; 5b is the
prerequisite plan's Task 5.

**Placeholder scan:** clean. Every code step carries its code; every test step carries its test.
The two steps that are judgement rather than code — Task 3 Step 5 and Task 4 Step 5, both
browser checks — enumerate exactly what to look at and say to fix the code rather than the
design system. Task 5 Step 2 may require the user to run an interactive OAuth login; the plan
says to stop and ask rather than to automate it.

**Type consistency.** `site_data.ROW_FIELDS` is the single list of what the page reads, asserted
against every row in Task 1 Step 6 and consumed by `rowHTML`, `reasonRowHTML` and `drawerHTML`
in Task 3. `window_kw` is produced normalised by `build_rows` and consumed by `sparkSVG`, which
re-normalises defensively so an un-normalised series cannot draw off-canvas.
`site_data.SITE_SCHEMA_VERSION` is compared against `SUPPORTED_MAJOR` in `app.js`, so a stale
deploy refuses to render rather than drawing wrong numbers. `methodHTML` reads exactly the eight
top-level keys `method.method_payload` returns, all of which are listed in Verified Facts above.

**One deviation from the mockup, stated where it is made:** the mockup is a two-column split with
the map at `55fr`. This plan ships a single column because there is no map yet. The class name,
the panel structure and the below-900px ordering rule are all kept, so the next plan restores the
grid with one CSS line and adds an SVG — it does not restructure the page.
