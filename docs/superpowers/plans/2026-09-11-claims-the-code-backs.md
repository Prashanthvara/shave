# Claims The Code Backs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every claim the published page makes true, then deploy it.

**Architecture:** Four corrections to shipped code, then the deploy that was Task 5 of the published-ledger plan. Each correction closes a gap between something the artifact asserts and something the code or the world actually supports: a provenance label the arithmetic does not back, a superseded function whose semantics contradict the shipped chain, a count the page prints but cannot show, and a link to a repository that does not exist.

**Tech Stack:** Python 3.11, numpy, pandas, pytest, vanilla ES2020, Cloudflare Workers static assets, wrangler 4.x, vitest.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` — premise **P6** ("publish the method, lineage and failure modes"), success criteria **1** and **3**, and the "Distribution Plan" section ("Public GitHub repo linked from the method page as the appendix. The URL is the deliverable.").

**Prior plans:** `2026-09-10-comstock-extractor.md`, `2026-09-10-first-ranked-list.md`, `2026-09-11-occupants-and-method.md` all complete. `2026-09-11-published-ledger.md` Tasks 1–4 complete at `c9d3743`; **its Task 5 (deploy) is superseded by Task 5 of this plan**, which adds the repository link that must ship with it.

## Why these four together

They are one defect wearing four hats. This artifact's entire argument is that it publishes its own method and failure modes, so a claim it cannot back is worse here than a bug would be. Three of the four were found by auditing the code against the plans; the fourth was found by driving a browser. None is a crash, and all four are visible to the one reader who matters.

## Global Constraints

- Python `>=3.11`. **Do not add any new Python dependency.** Everything needed is in `pyproject.toml`. (This is why the audit could not produce line coverage: `pytest-cov` is not installed and adding it is forbidden.)
- **Never restate a constant.** Import from `src/shave/assumptions.py`. New constants go *into* it with a matching `Assumption(...)` row in `PUBLISHED`.
- Every constant a reader could dispute needs `provenance` of `FILED`, `ASSUMED` or `DERIVED` and a real `source`. **`DERIVED` means the code derives it.** If the code hard-codes the result, the honest label is `FILED` or `ASSUMED` — that distinction is the subject of Task 1.
- **JavaScript has no runtime dependencies.** The page loads no framework and no library.
- **`node`, `npm` and `npx` are nvm SHELL FUNCTIONS, and exporting PATH is not enough** — a shell function takes precedence over a PATH lookup. Call binaries by absolute path:
  ```bash
  NB="$HOME/.nvm/versions/node/v22.18.0/bin"
  "$NB/npx" vitest run
  ```
  Verified 2026-09-11: node v22.18.0, npm 11.5.2, `"$NB/npx" wrangler --version` → 4.131.1. `/usr/local/bin/wrangler` is a stub that prints "You have not installed wrangler"; never invoke it.
- Python suite: `cd /Users/pjay/powertown && uv run pytest` — currently **944 passing, 4 deselected**. Render suite: `"$NB/npx" vitest run` — currently **20 passing**.
- Commit after each task. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48
  ```

---

## Verified facts, measured 2026-09-11

Do not re-derive these. Do verify the checks each task names.

**The derived anchor.** `assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_manufacturing"]` is the literal `23.4`, published with provenance `DERIVED`. `assumptions.BTU_PER_KWH = 3412.0` exists and **participates in no expression anywhere in the codebase**. Recomputing from the MECS figures in the comment: NAICS 332 = `124e12 / 3412 / 1e6 / 1530` = **23.753**; NAICS 333 = `80e12 / 3412 / 1e6 / 1021` = **22.964**; mean **23.3588**, which rounds to 23.4. The literal is right; the label is the problem.

**Dead code, confirmed by full-repo grep** — each has exactly one reference, its own definition:
`archetype.scale_to_floor_area` (line 267), `assumptions.comstock_glob` (line 152), `archetype.DAY_TYPES` (line 42). None appears in any plan, test, script or page.

**The sweet-spot truncation.** The counts line prints `172 in the sweet spot`. The exported lists contain **68** — all in `comstock`, because **all 172 sweet-spot rows are ComStock-backed and zero are modelled**. `export.TOP_N = 250` takes the top rows *by dollars*; sweet-spot rows sit at dollar ranks **min 32, median 316, max 526**, so **104 of 172 fall outside the cut**. The median site of the population the thesis is about ranks 316th by the metric the thesis argues is the wrong one to rank on.

**The repository link.** `public/index.html:82` links "the repository" to `https://github.com/prashanthvara`, which is a **user profile, not a repository**. `git remote -v` returns nothing: this repo has no remote at all.

**Constants for unbuilt features**, surfacing nowhere and harmless but worth knowing: `G3_EXIT_KW` (rate switch), `CABINET_WIDTH_IN`, `CABINET_DEPTH_IN`, `CABINET_HEIGHT_IN` (siting screen). `KVA_CLAUSE_FACTOR` and `CABINETS_PER_SYSTEM` do reach the method page and are doing their job.

---

## File Structure

| File | Responsibility in this plan |
|---|---|
| `src/shave/assumptions.py` *(modify)* | The MECS anchor becomes an expression, not a literal. |
| `src/shave/archetype.py` *(modify)* | Delete the superseded `scale_to_floor_area` and the dead `DAY_TYPES`. |
| `src/shave/export.py` *(modify)* | Select rows so the sweet-spot view can show what the counts line promises. |
| `public/index.html` *(modify)* | The repository link, or none. |
| `README.md` *(modify)* | How to rebuild and deploy. |
| `tests/test_assumptions.py` *(new)* | The derivation, pinned. |

---

## Task 1: `DERIVED` should mean the code derives it

`intensity_industrial_manufacturing` is published with provenance `DERIVED` and a comment spelling out the MECS arithmetic. The value is a hard-coded `23.4`, and `BTU_PER_KWH` participates in nothing. Change the constant and no number moves.

On a page whose argument is *"the published assumptions are provably the computed ones"*, that is the most expensive kind of small defect. It is also the third instance of this exact pattern in this project: the regression text asserted "~1.000 by construction" above a table reading 0.878, and `methodHTML` read a figure shape that did not exist. Each time, a claim outran the code.

**Files:**
- Modify: `src/shave/assumptions.py`
- Test: `tests/test_assumptions.py` (new)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `assumptions.MECS_NET_ELECTRICITY_TBTU: dict[str, float]`
  - `assumptions.MECS_FLOORSPACE_MSQFT: dict[str, float]`
  - `assumptions.mecs_intensity(naics: str) -> float`
  - `assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_manufacturing"]` unchanged in value, now computed.

- [ ] **Step 1: Write the failing test**

Create `tests/test_assumptions.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_assumptions.py -v`
Expected: FAIL — `AttributeError: module 'shave.assumptions' has no attribute 'mecs_intensity'`

- [ ] **Step 3: Make the anchor an expression**

In `src/shave/assumptions.py`, immediately after `BTU_PER_KWH = 3412.0`, insert:

```python
#: MECS 2018 Table 3.2, column "Net Electricity(b)", trillion Btu. Read from
#: eia.gov/consumption/manufacturing/data/2018/xls/Table3_2.xlsx on 2026-09-11.
MECS_NET_ELECTRICITY_TBTU: dict[str, float] = {
    "332": 124.0,   # Fabricated Metal Products
    "333": 80.0,    # Machinery
}

#: MECS 2018 Table 9.1, enclosed floorspace of all buildings, million sq ft.
#: eia.gov/consumption/manufacturing/data/2018/xls/Table9_1.xlsx
MECS_FLOORSPACE_MSQFT: dict[str, float] = {
    "332": 1530.0,
    "333": 1021.0,
}


def mecs_intensity(naics: str) -> float:
    """kWh per square foot per year for one MECS subsector.

    Derived, not quoted: trillion Btu of net electricity over million square
    feet of enclosed floorspace, converted at BTU_PER_KWH. The arithmetic
    lives here rather than in a comment so that the DERIVED provenance on the
    published row is a statement about the code, not about a past session.
    """
    btu = MECS_NET_ELECTRICITY_TBTU[naics] * 1e12
    sqft = MECS_FLOORSPACE_MSQFT[naics] * 1e6
    return btu / BTU_PER_KWH / sqft
```

Then replace the literal in `ELECTRIC_INTENSITY_KWH_PER_SQFT_YR`. The entry currently reads:

```python
    # MECS NAICS 332 Fabricated Metal Products: 124 trillion Btu net
    # electricity over 1,530 million sq ft = 23.75. NAICS 333 Machinery:
    # 80 over 1,021 = 22.96. The machine shops and metal fabricators of
    # Worcester are 332/333; the mean of the two, 23.36, is the anchor.
    "industrial_manufacturing": 23.4,
```

Replace those five lines with:

```python
    # The machine shops and metal fabricators of Worcester are NAICS 332 and
    # 333. The mean of the two subsector intensities is the anchor: 23.75 and
    # 22.96, for 23.36. Computed rather than quoted -- see mecs_intensity.
    "industrial_manufacturing": (mecs_intensity("332") + mecs_intensity("333")) / 2,
```

**`mecs_intensity` must be defined above the dict that calls it**, since the dict literal is evaluated at import.

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_assumptions.py -v`
Expected: PASS, all five.

- [ ] **Step 5: Check the published value did not move**

Run:
```bash
uv run python -c "
from shave import assumptions as a
v = a.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR['industrial_manufacturing']
print('anchor:', v)
row = [r for r in a.published_rows() if r['key']=='intensity_industrial_manufacturing'][0]
print('published as:', row['value'], '|', row['provenance'])
"
```

**Pass condition:** the anchor prints `23.3588...`, the published row still reads `DERIVED`, and the rendered value rounds to 23.4. A change in the third decimal is expected and correct — the literal was the rounded figure; this is the real one.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest`
Expected: PASS. **`tests/test_modeled.py::test_the_chain_reproduces_the_published_annual_energy` reads the same constant and must still pass** — it asserts a round trip, not a literal. If any test fails on the third decimal, fix the test's tolerance, not the derivation.

- [ ] **Step 7: Commit**

```bash
git add src/shave/assumptions.py tests/test_assumptions.py
git commit -m "fix: DERIVED now means the code derives it

intensity_industrial_manufacturing was published with provenance DERIVED and
the MECS arithmetic spelled out in a comment, but the value was the literal
23.4 and BTU_PER_KWH participated in no expression anywhere. Changing the Btu
conversion moved nothing.

On a page whose argument is that the published assumptions are provably the
computed ones, that is the most expensive kind of small defect, and it is the
third of its shape in this project: the regression text asserted ~1.000 above
a table reading 0.878, and methodHTML read a figure shape that did not exist.

The anchor is now (mecs_intensity(332) + mecs_intensity(333)) / 2 = 23.3588,
which still rounds to the 23.4 already on the method page. A test breaks
BTU_PER_KWH deliberately to prove the conversion is load-bearing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 2: Delete the superseded magnitude API

`archetype.scale_to_floor_area(archetype, sqft, kw_per_1000sqft)` takes an **asserted** intensity per 1,000 sq ft. The shipped chain does the opposite and deliberately so: magnitude from published intensity, load factor **derived** from the declared shape. That replacement was the entire point of first-ranked-list Task 3, whose module docstring says *"The load factor is not asserted anywhere."*

The function has one reference in the whole repository — its own `def`. It is in no plan, no test, no script and no page. Anyone who finds it will reach for the mechanism the project explicitly rejected, and nothing will stop them.

**Files:**
- Modify: `src/shave/archetype.py` — delete `scale_to_floor_area` and `DAY_TYPES`
- Modify: `src/shave/assumptions.py` — delete `comstock_glob`
- Test: `tests/test_modeled.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a smaller surface. `archetype.scale_to_floor_area`, `archetype.DAY_TYPES` and `assumptions.comstock_glob` no longer exist.

- [ ] **Step 1: Write the test that pins the deletion**

Append to `tests/test_modeled.py`:

```python
def test_the_superseded_asserted_intensity_api_is_gone():
    """`scale_to_floor_area(archetype, sqft, kw_per_1000sqft)` took an ASSERTED
    intensity. The shipped chain derives the load factor from the declared
    shape and takes magnitude from published intensity -- the opposite, and
    the whole point of the modelled-magnitude work.

    It survived with zero callers. A superseded mechanism left in the public
    surface is a trap: the next reader uses it and gets a magnitude this
    project deliberately stopped producing.
    """
    from shave import archetype

    assert not hasattr(archetype, "scale_to_floor_area"), (
        "the asserted-intensity path is back; magnitude must come from "
        "modeled.peak_kw_for, which derives the load factor rather than "
        "taking one"
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_modeled.py -k superseded -v`
Expected: FAIL — the attribute still exists.

- [ ] **Step 3: Delete the three dead symbols**

In `src/shave/archetype.py`, delete the whole `scale_to_floor_area` function — the `def` line at 267 through the end of its body — and the line:

```python
DAY_TYPES = ("weekday", "saturday", "sunday")
```

In `src/shave/assumptions.py`, delete the whole `comstock_glob` function, including its docstring.

**Do not delete `COMSTOCK_S3_BASE`, `COMSTOCK_RELEASE`, `COMSTOCK_UPGRADE` or `COMSTOCK_STATE`** — `comstock.py` builds its paths from all four and they are live.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest`
Expected: PASS, 944 + Task 1's 5 + 1 here. If anything fails with `ImportError` or `AttributeError`, a reference existed that the grep missed — restore that symbol rather than editing the caller, and record which one.

- [ ] **Step 5: Confirm nothing else is dead**

Run:
```bash
uv run python - <<'PY'
import ast, pathlib, re
src = list(pathlib.Path('src/shave').glob('*.py'))
corpus = "\n".join(p.read_text() for p in src)
for d in ('tests', 'scripts'):
    corpus += "\n".join(p.read_text() for p in pathlib.Path(d).glob('*.py'))
orphans = []
for p in src:
    for node in ast.parse(p.read_text()).body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            if len(re.findall(rf'\b{node.name}\b', corpus)) <= 1:
                orphans.append(f"{p.name}:{node.lineno} {node.name}")
print("orphaned public functions:", orphans or "none")
PY
```

**Pass condition:** `none`. Report the output either way.

- [ ] **Step 6: Commit**

```bash
git add src/shave/archetype.py src/shave/assumptions.py tests/test_modeled.py
git commit -m "refactor: delete the superseded asserted-intensity API

scale_to_floor_area took an asserted kW per 1,000 sq ft. The shipped chain
takes magnitude from published intensity and DERIVES the load factor from the
declared shape -- the opposite, and the point of the modelled-magnitude work.
It had exactly one reference in the repository: its own def.

A superseded mechanism left in the public surface is a trap, so a test now
asserts it stays gone. Also drops two dead constants, DAY_TYPES and
comstock_glob.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 3: The sweet-spot view shows what the counts line promises

The page prints `172 in the sweet spot` and can display **68**. `export.TOP_N = 250` cuts by dollars, and sweet-spot rows sit at dollar ranks **32 to 526, median 316** — so **104 of 172 are gone** before the filter runs.

This is the thesis losing an argument with its own ranking. The spec's whole claim is that the sweet spot — G-2, spiky, mid-size — is the population worth calling, and that ranking on absolute dollars surfaces the wrong buildings. Cutting the export by dollars and then filtering for the sweet spot bakes in exactly the bias the spec set out to expose.

The fix is not to change the ranking. It is to export the union of two selections, so each view is complete within itself. The ranks stay dollar ranks within each list; nothing about the ordering changes.

**Files:**
- Modify: `src/shave/export.py` — `build_export`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `pipeline.score_parcels` output.
- Produces: `export.SWEET_SPOT_N: int = 250`; `build_export` selects `top_n` by dollars **plus** `SWEET_SPOT_N` sweet-spot rows by dollars, de-duplicated. `SCHEMA_VERSION` rises to `"1.2.0"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export.py`:

```python
def test_the_export_carries_every_sweet_spot_row_the_counts_line_promises():
    """The page prints a sweet-spot count and then filters the exported rows.
    If the export was cut by dollars first, the view shows a fraction of the
    number beside it -- and sweet-spot sites are small by construction, so
    they are exactly the rows a dollar cut removes. Measured on Worcester:
    172 promised, 68 shown, median sweet-spot dollar rank 316 of 526.
    """
    rows = [_row(f"L{i}", usd=100_000.0 - i) for i in range(60)]
    # Twenty sweet-spot sites, all ranked below the dollar cut.
    for i in range(60, 80):
        rows.append(_row(f"S{i}", usd=10.0 - i / 1000.0, sweet_spot=True))
    scored = pd.DataFrame(rows)
    parcels = _parcels([r["loc_id"] for r in rows])

    payload = export.build_export(scored, parcels,
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)

    exported = payload["lists"]["comstock"]
    sweet = [r for r in exported if r["sweet_spot"]]
    assert len(sweet) == 20, "every sweet-spot row must survive the dollar cut"
    assert payload["counts"]["sweet_spot"] == 20


def test_the_dollar_ranking_is_unchanged_by_the_sweet_spot_union():
    """Adding sweet-spot rows must not reorder the list or renumber its head."""
    rows = [_row(f"L{i}", usd=100_000.0 - i) for i in range(60)]
    rows.append(_row("S1", usd=5.0, sweet_spot=True))
    scored = pd.DataFrame(rows)

    payload = export.build_export(scored, _parcels([r["loc_id"] for r in rows]),
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)
    exported = payload["lists"]["comstock"]

    usd = [r["annual_savings_usd"] for r in exported]
    assert usd == sorted(usd, reverse=True), "still ranked by dollars"
    assert [r["rank"] for r in exported] == list(range(1, len(exported) + 1))
    assert exported[0]["loc_id"] == "L0", "the head of the list is untouched"
    assert exported[-1]["loc_id"] == "S1", "the sweet-spot row joins at its own rank"


def test_a_row_that_is_both_top_by_dollars_and_sweet_spot_appears_once():
    rows = [_row("A", usd=90_000.0, sweet_spot=True), _row("B", usd=80_000.0)]
    payload = export.build_export(pd.DataFrame(rows), _parcels(["A", "B"]),
                                  town={"name": "Worcester", "town_id": 348},
                                  top_n=50)
    ids = [r["loc_id"] for r in payload["lists"]["comstock"]]
    assert ids == ["A", "B"], f"duplicate or reordered: {ids}"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_export.py -k "sweet_spot or dollar_ranking" -v`
Expected: FAIL — `test_the_export_carries_every_sweet_spot_row...` finds 0 sweet-spot rows, because all 20 sit below the `top_n=50` dollar cut.

- [ ] **Step 3: Select the union**

In `src/shave/export.py`, add beneath `TOP_N`:

```python
#: Sweet-spot rows kept per list, on top of TOP_N. These are G-2 sites with a
#: spiky shape -- small by construction, so a cut by dollars removes exactly
#: them. Measured on Worcester: of 172 sweet-spot rows, dollar ranks run 32 to
#: 526 with a median of 316, so a TOP_N of 250 lost 104 of them. Exporting the
#: union lets each view be complete within itself without changing any ranking.
SWEET_SPOT_N = 250
```

In `build_export`, replace this:

```python
        subset = merged[(merged["source"] == source) & merged["keep"].astype(bool)]
        subset = subset.nlargest(top_n, "annual_savings_usd")
```

with:

```python
        kept = merged[(merged["source"] == source) & merged["keep"].astype(bool)]
        by_dollars = kept.nlargest(top_n, "annual_savings_usd")
        sweet = kept[kept["sweet_spot"].astype(bool)].nlargest(
            SWEET_SPOT_N, "annual_savings_usd"
        )
        # Union, then re-sort. A row in both appears once; the ordering is
        # still dollars descending, so ranks mean what they have always meant.
        subset = (
            pd.concat([by_dollars, sweet])
            .drop_duplicates(subset="loc_id", keep="first")
            .sort_values("annual_savings_usd", ascending=False)
        )
```

Bump the version:

```python
SCHEMA_VERSION = "1.2.0"
```

- [ ] **Step 4: Run the export tests**

Run: `uv run pytest tests/test_export.py -v`
Expected: PASS, all eleven.

- [ ] **Step 5: Record the schema change**

In `docs/ranked-json-schema.md`, change `**Current version: `1.1.0`**` to `**Current version: `1.2.0`**`, and add to the versioning section:

```markdown
**1.2.0** — row *selection* widened. Each list now carries the top `TOP_N` rows
by dollars plus up to `SWEET_SPOT_N` sweet-spot rows, de-duplicated and still
ordered by dollars. No field was added, removed or retyped, so a 1.1.0 consumer
keeps working; the list is simply longer and complete for the sweet-spot view.
```

- [ ] **Step 6: Rebuild and confirm the page can show what it prints**

Run:
```bash
uv run python scripts/build_site.py
uv run python -c "
import json
d = json.load(open('public/data/ranked.json'))
print('counts line promises:', d['counts']['sweet_spot'])
for name, rows in d['lists'].items():
    sw = [r for r in rows if r['sweet_spot']]
    print(f'  {name:9s} {len(rows):3d} rows, sweet spot {len(sw)}')
print('total sweet spot exported:', sum(len([r for r in v if r['sweet_spot']]) for v in d['lists'].values()))
"
```

**Pass condition, declared in advance:** total sweet-spot rows exported equals the `counts.sweet_spot` figure, **172**. Report the new `ranked.json` size; it must stay under `export.MAX_BYTES` (5 MB), and `write_export` refuses it if not.

- [ ] **Step 7: Run both suites**

Run: `uv run pytest` and `"$NB/npx" vitest run`
Expected: PASS both. The page needs no change — it filters whatever it is given.

- [ ] **Step 8: Commit**

```bash
git add src/shave/export.py tests/test_export.py docs/ranked-json-schema.md
git commit -m "fix: the sweet-spot view shows what the counts line promises

The page printed '172 in the sweet spot' and could display 68. TOP_N cut the
export by dollars, and sweet-spot rows are small by construction: their dollar
ranks run 32 to 526 with a median of 316, so a cut at 250 lost 104 of them.

That is the thesis losing an argument with its own ranking. The spec's claim is
that ranking on absolute dollars surfaces the wrong buildings; cutting by
dollars and then filtering for the sweet spot baked in exactly that bias.

Each list now carries the top rows by dollars plus the sweet-spot rows, unioned
and de-duplicated. No ranking changes and no field changes, so this is a MINOR
schema bump.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 4: A repository link that resolves, or none

`public/index.html:82` links "the repository" to `https://github.com/prashanthvara` — a user profile. `git remote -v` returns nothing: there is no remote.

The spec's distribution plan says *"Public GitHub repo linked from the method page as the appendix. The URL is the deliverable."* A page whose argument is "check my work" that links to a profile is worse than one that links to nothing, because it invites the click that fails.

**This task needs the user.** Creating a repository is an outward-facing action on their account; do not create one unprompted.

**Files:**
- Modify: `public/index.html`
- Modify: `README.md`

- [ ] **Step 1: Ask, and stop**

Ask the user, in these terms, and wait:

> The page links "the repository" to a GitHub profile, and this repo has no remote. Three options: (a) you create a public repo and give me the URL, and I wire it up and push; (b) I remove the link and the page stands alone; (c) I leave it and you fix the link before sharing. Which?

Do not proceed past this step without an answer. `gh repo create` publishes work to the internet under their account and is not yours to decide.

- [ ] **Step 2a: If they supply a URL — wire it up**

Replace the link in `public/index.html`:

```html
  <div class="foot" id="sitefoot">
    Estimates from public data, never measurements. Method, source and the
    full assumption table:
    <a href="THE_URL_THEY_GAVE" rel="noopener">the repository</a>.
  </div>
```

Then verify it resolves before committing:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -L "THE_URL_THEY_GAVE"
```

**Pass condition:** `200`. A `404` means the repo is private or the URL is wrong — go back and ask rather than shipping it.

- [ ] **Step 2b: If they decline — remove the link**

Replace the footer with a claim that needs no external resource:

```html
  <div class="foot" id="sitefoot">
    Estimates from public data, never measurements. Every assumption, its
    source and its provenance are on the Method tab.
  </div>
```

- [ ] **Step 3: Document the rebuild in the README**

`README.md` has a `## Development` section that stops at `uv run pytest`. Nothing tells a reader how the published page is produced. Append to that section:

```markdown
### Rebuilding the published page

    uv run python scripts/build_site.py     # pipeline -> public/data/*.json
    NB="$HOME/.nvm/versions/node/v22.18.0/bin"
    "$NB/npx" wrangler dev                  # serve it locally on :8787
    "$NB/npx" wrangler deploy               # publish

`data/raw/` holds the MassGIS L3 extract and is gitignored, so a fresh clone
must download it before the pipeline will run. `data/interim/comstock/` is the
cached ComStock profile per archetype; delete it and
`scripts/warm_comstock_cache.py` refetches from S3, about six minutes.

`node`, `npm` and `npx` are nvm shell functions here, so `export PATH` does not
reach them — call the binaries by absolute path, as above.
```

- [ ] **Step 4: Commit**

```bash
git add public/index.html README.md
git commit -m "fix: a repository link that resolves, or none at all

The page linked 'the repository' to a GitHub profile, and this repo has no
remote. A page whose argument is 'check my work' that links to a profile is
worse than one that links to nothing: it invites the click that fails.

Also documents how the published page is rebuilt, including the nvm
shell-function trap that makes export PATH insufficient.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 5: Deploy

Success criterion 1: a public URL, the ranked list in under three seconds, no signup. This supersedes Task 5 of the published-ledger plan, which did not include the repository link.

- [ ] **Step 1: Rebuild from a clean state**

```bash
cd /Users/pjay/powertown
uv run python scripts/build_site.py
ls -la public/data/
git status --short
```

**Pass condition:** both JSON files present, working tree clean apart from the gitignored `public/data/`.

- [ ] **Step 2: Authenticate — this needs the user**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler whoami
```

If it reports no account, **stop and ask the user to run `"$NB/npx" wrangler login` themselves.** It opens a browser for OAuth; do not attempt to automate a login or to paste credentials.

- [ ] **Step 3: Deploy**

```bash
NB="$HOME/.nvm/versions/node/v22.18.0/bin"
"$NB/npx" wrangler deploy
```

Record the `*.workers.dev` URL it prints.

- [ ] **Step 4: Verify the live site against criterion 1**

```bash
URL="https://shave.<subdomain>.workers.dev"
curl -s -o /dev/null -w 'index  %{http_code}  %{time_total}s\n' "$URL/"
curl -s -o /dev/null -w 'ranked %{http_code}  %{time_total}s  %{size_download}b\n' "$URL/data/ranked.json"
curl -s -o /dev/null -w 'method %{http_code}  %{time_total}s\n' "$URL/data/method.json"
```

**Pass conditions, declared in advance:** all three return `200`; index plus `ranked.json` totals **under 3 seconds**; no request carries a credential. Report the measured times.

- [ ] **Step 5: Verify the live page in a real browser**

Load the URL and confirm, by eye and by reading the DOM:

- rank 1 is selected and its reason is visible **with no interaction**;
- the top row of each list names a real business, not a holding company;
- the sweet-spot view now shows the number the counts line prints;
- the Method tab renders 15 limitations, 4 gaps, 23 assumptions and the regression table with real figures, and contains no `undefined`;
- at 400px the body does not scroll sideways;
- the repository link resolves, if one was wired up.

Every one of these has broken at least once in this project's history, and four were found only by driving a browser rather than by reading tests.

- [ ] **Step 6: Commit the URL**

Add the live URL to the top of `README.md`, then:

```bash
git add README.md
git commit -m "docs: the live URL

Success criterion 1: a public URL, the ranked list under three seconds, no
signup and no database on the request path.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## What this plan deliberately leaves alone

| Left | Why |
|---|---|
| **The encoding map** | The job posting's headline ask and design review D2. It needs parcel polygons in the export — a schema addition, not a fix. Highest-value next work. |
| Address box, interaction-states gallery | Deferred with the map. |
| `STRUCTURES_POLY` and the siting screen | Would fill the drawer's empty clear-wall slot. Independent of everything here. |
| New Bedford and Chicopee | The municipality control is built for them; each needs an L3 download and a crosswalk pass. |
| MECOLS class-shape check | `MECOLS.xlsx` still not on disk. Already a named gap on the method page. |
| `G3_EXIT_KW`, `CABINET_WIDTH_IN/DEPTH_IN/HEIGHT_IN` | Constants for unbuilt features, surfacing nowhere. Harmless, and deleting them would only mean retyping them when the siting screen and rate switch land. Named in the audit so they are not mistaken for implemented capability. |
| Line coverage | `pytest-cov` is not installed and Global Constraints forbid adding a Python dependency. `site_data`, `export`, `regression` and `app.js` have never been mutation-tested; that is the honest gap in this review. |

---

## Self-Review

**Spec coverage.** Task 1 restores premise P6 — the published assumptions being provably the computed ones — where a `DERIVED` label had outrun the arithmetic. Task 3 restores the spec's central claim, that the sweet spot is the population worth calling, by making the view able to show it. Task 4 satisfies the Distribution Plan's "public GitHub repo linked from the method page as the appendix." Task 5 closes success criterion 1. Task 2 implements no spec requirement; it removes a mechanism the spec's modelled-magnitude section explicitly replaced.

**Placeholder scan:** clean. Every code step carries its code; every test step carries its test. Two steps are explicitly human — Task 4 Step 1 (create a repository) and Task 5 Step 2 (OAuth login) — and both say to stop and ask rather than to automate an outward-facing action. Task 5 Step 5 is a judgement step and enumerates exactly what to look at.

**Type consistency.** `assumptions.mecs_intensity(naics: str) -> float` is defined in Task 1 above the dict that calls it, and read by `tests/test_assumptions.py` in the same task; nothing else consumes it. `export.SWEET_SPOT_N` is read only inside `build_export`, and the union changes row *selection* while leaving every field name and the dollar ordering intact, which is why the schema bump is MINOR and `site_data.REQUIRED_ROW_FIELDS` needs no change. Task 2 deletes three symbols and a test asserts one stays deleted; the audit confirmed each had exactly one reference — its own definition.

**One risk, measured rather than guessed.** Task 1 changes the anchor from `23.4` to `23.3588`, moving every modelled-industrial magnitude by **−0.176%**. Simulated before writing this plan by patching the derived value in and running the suite: a 20,000 sq ft machine shop goes **195.2 → 194.9 kW**, still inside the 150–260 kW band `test_a_machine_shop_lands_in_the_g2_band` declares, and **all 17 tests in `tests/test_modeled.py` pass unchanged**. The figures recorded in the SDD ledgers shift in the third significant figure and are not re-pinned anywhere; that is accepted, because the ledger records what was measured on the day.
