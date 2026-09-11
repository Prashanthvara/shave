# Occupants and Method Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Python half so the artifact is publishable — correct the one predicate that fires on 98% of rows, put a real named business on the top row, and assemble every statement the method page must make as tested data rather than prose.

**Architecture:** Three independent Python deliverables, no frontend. Task 1 fixes `scorer.recharge_feasible`, which must land before the export contract freezes the flag it produces. Task 2 adds `occupants.py` plus a committed CSV of hand-resolved operating businesses, closing the spec's success criterion 2. Task 3 adds `method.py`, which assembles the assumptions table, the limitations list, the coverage counts and the data lineage from the code that computed them — so the published method is provably the one that ran, which is a stronger form of premise P6 than prose.

**Tech Stack:** Python 3.11, numpy, pandas 3.0.5, geopandas, pytest, uv. No new dependencies.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` — sections "The scoring function" (recharge feasibility), "Recommended Approach" step 7, "Success Criteria" 2 and 6, "Premises" P6.

**Prior plans:**
- `docs/superpowers/plans/2026-09-10-comstock-extractor.md` — complete.
- `docs/superpowers/plans/2026-09-10-first-ranked-list.md` — Tasks 1–4 complete, ledger at `.superpowers/sdd/2026-09-10-first-ranked-list/progress.md`. **Its Tasks 5 (versioned export) and 6 (regression) are written and not yet run.**

## Sequencing against the unfinished prior plan

Task 1 here **must run before** first-ranked-list Task 5, because Task 5 freezes `recharge_feasible` into the `ranked.json` schema and onto every published row. Tasks 2 and 3 here are independent of it and may run in any order.

Recommended order: **Task 1 → first-ranked-list Task 5 → first-ranked-list Task 6 → Task 2 → Task 3.**

Task 3's `method_payload` reads the regression figures produced by first-ranked-list Task 6, and degrades to a stated "not yet run" rather than failing if they are absent — so Task 3 can still be executed first if Task 6 slips.

## Global Constraints

- Python `>=3.11`. **Do not add any new dependency.** Everything needed is in `pyproject.toml`.
- **Never restate a constant.** Import from `src/shave/assumptions.py`. A hard-coded tariff, energy or geometry number is a review rejection. New constants go *into* `assumptions.py` with a matching `Assumption(...)` row in `PUBLISHED`.
- Every new constant a reader could dispute needs `provenance` of `FILED`, `ASSUMED` or `DERIVED` and a real `source` string. Inventing a number without a source is a review rejection.
- No per-row Python loops over parquet rows. Vectorised pandas/numpy or SQL. A loop over the ~2,100 output parcels is fine and expected.
- Every network call is read-only and anonymous. No credentials.
- Tests that need the network are marked `@pytest.mark.network` and are skipped by default.
- Run the full suite with `cd /Users/pjay/powertown && uv run pytest`. It is currently **897 passing, 4 deselected**. It must still be 897 plus your new tests.
- pandas 3.0 traps, both already hit in this repo:
  - `date_range` returns `datetime64[us]`, **not** `[ns]`. Never read `.asi8` assuming nanoseconds.
  - The `str` dtype does **not** stringify NA to `"nan"`. Null checks use `.isna()`, never `.astype(str).isin([...])`.
- The Worcester L3 extract lives at `data/raw/M348_WORCESTER/L3_SHP_M348_Worcester` (town id `348`). It is gitignored and already downloaded.
- **`data/` is gitignored, but `data/occupants.csv` must be committed** — it is hand-authored domain work, not a build artifact. Task 2 adds the `!` negation rule.
- Commit after each task. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48
  ```

---

## Verified facts, established by live run on 2026-09-11

Do not re-derive these. Do verify the checks each task names.

**Pipeline output, real Worcester data:** 2,099 rows in, 2,099 out. Unscored exactly `{no_intensity_anchor: 6, no_floor_area: 1}`. 737 kept, 172 sweet spot. `by source` among kept: comstock 528, modeled 209. Rate class among kept: G-2 500, G-3 237. Max saving $31,440. Whole run 23.9 s including ingest.

**Flag counts across the 737 kept rows:** `recharge_constrained` **719 (98%)**, `scale_extrapolation` 90 (12%), `thin_cohort` 25 (3%), `power_limited` 13 (2%).

**Ranking composition:**

| slice | n | median sqft | median avg_12mo | median shaved fraction |
|---|---|---|---|---|
| all kept | 737 | 30,670 | 122.0 kW | 0.484 |
| top 60 by dollars | 60 | 204,051 | 714.5 kW | 0.186 |
| sweet spot | 172 | 15,014 | 74.9 kW | 0.716 |

**Owner of record is not the operating business.** 25 of the top 50 owners match a holding-company pattern. Real examples from the sweet-spot top rows: `MGM PENA LLC` at 662 MAIN ST (use desc "Supermarkets over 10000 sq ft"), `RK WORCESTER CROSSING LLC`, `440 LINCOLN STREET HOLDING`, `LAVINE,ROBERT M TRUSTEE`. Site addresses are present and clean (`662 MAIN ST`, `WORCESTER`).

**`ingest.OUTPUT_COLUMNS`** carries `loc_id, prop_id, use_code, use_desc, archetype, source, icp_sector, sqft, stories, year_built, owner, site_addr, city, zip, zoning, assess_fy, record_count, owner_count, confidence, confidence_reasons, multi_use, multi_meter, geometry`.

**`assumptions.PUBLISHED`** currently has 22 rows. `assumptions.published_rows()` returns them as `list[dict]` with keys `key, value, provenance, source, note`.

**`MECOLS.xlsx` is not on disk**, despite the spec recording it as downloaded. Success criterion 4 is blocked and Task 3 states that as a known gap rather than claiming the check was made.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/scorer.py` *(modify)* | `recharge_feasible` gains `required_charge_kw` and tests headroom against the rate the site actually needs. |
| `src/shave/assumptions.py` *(modify)* | one `Assumption` row recording what the charger constant now means. |
| `src/shave/occupants.py` *(new)* | load, validate and join the hand-resolved occupant table. One file because it is one concern: turning owner-of-record into the operating business. |
| `data/occupants.csv` *(new, committed)* | the hand-authored lookup. The domain work, browsable in the repo like `crosswalk.csv`. |
| `scripts/occupant_worksheet.py` *(new)* | emits the blank worksheet for a human to fill in. Not part of the scoring path. |
| `src/shave/method.py` *(new)* | every statement the method page makes, assembled from code. |
| `tests/test_occupants.py`, `tests/test_method.py` *(new)* | |

---

## Task 1: The recharge test asks for the rate it needs, not the rate it has

`recharge_constrained` fires on 719 of 737 kept rows. A flag true of 98% of a table carries no information and would print a warning on almost every published row.

The cause is in the predicate, not in the pipeline. `recharge_feasible` tests `l_offpeak_max_kw + CHARGER_KW < t_month` with `CHARGER_KW = RATED_POWER_KW = 250 kW`. A typical kept row has `t_month` of 100–200 kW, so the 250 kW term alone exceeds it and the test fails before the site's own overnight load is considered.

But charging at the full 250 kW rating is a choice, not a requirement. The most the battery ever replaces is `USABLE_ENERGY_KWH = 413.4 kWh`, over an `OFFPEAK_HOURS = 11` window — a required average of **37.6 kW**. The function's *first* predicate already computes exactly that quantity and then discards it. The fix is to use it in the second.

`CHARGER_KW` keeps its job in the first predicate, where it is the right bound: it is the most the charger can deliver, and it answers "is there enough time at all".

**Files:**
- Modify: `src/shave/scorer.py` — `recharge_feasible`, plus a new `required_charge_kw`
- Modify: `src/shave/assumptions.py` — one `PUBLISHED` row
- Test: `tests/test_scorer.py`

**Interfaces:**
- Consumes: `assumptions.CHARGER_KW`, `assumptions.USABLE_ENERGY_KWH`, `billing_window.OFFPEAK_HOURS`.
- Produces:
  - `scorer.required_charge_kw(e_used_kwh: float, offpeak_hours: float) -> float`
  - `scorer.recharge_feasible(...) -> bool` — same signature, changed second predicate.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scorer.py`:

```python
def test_headroom_is_tested_against_the_REQUIRED_rate_not_the_maximum():
    """The bug this fixes made the flag fire on 719 of 737 Worcester rows.

    A site holding a 150 kW threshold, drawing 40 kW overnight, that needs to
    put back 413 kWh over 11 hours. The required rate is 37.6 kW, so charging
    lands at 77.6 kW -- comfortably under the 150 kW threshold, and the
    recharge is feasible. Testing against the 250 kW charger RATING instead
    gives 290 kW and fails, which is what made the flag universal.
    """
    assert scorer.recharge_feasible(
        e_used_kwh=413.4,
        offpeak_hours=11.0,
        l_offpeak_max_kw=40.0,
        t_month=150.0,
    ) is True


def test_required_charge_rate_is_energy_over_the_window():
    assert scorer.required_charge_kw(413.4, 11.0) == pytest.approx(37.5818, rel=1e-4)
    assert scorer.required_charge_kw(0.0, 11.0) == 0.0


def test_headroom_still_fails_when_the_site_itself_fills_the_window():
    """The predicate must keep its teeth. A site already drawing 140 kW
    overnight against a 150 kW threshold has 10 kW of room and needs 37.6."""
    assert scorer.recharge_feasible(
        e_used_kwh=413.4,
        offpeak_hours=11.0,
        l_offpeak_max_kw=140.0,
        t_month=150.0,
    ) is False
```

- [ ] **Step 2: Run them to verify the first and second fail**

Run: `uv run pytest tests/test_scorer.py -k 'REQUIRED_rate or required_charge_rate or fills_the_window' -v`

Expected: `test_headroom_is_tested_against_the_REQUIRED_rate_not_the_maximum` FAILS (`assert False is True`); `test_required_charge_rate_is_energy_over_the_window` FAILS (`AttributeError: module 'shave.scorer' has no attribute 'required_charge_kw'`); `test_headroom_still_fails_when_the_site_itself_fills_the_window` PASSES already.

- [ ] **Step 3: Implement**

In `src/shave/scorer.py`, replace `recharge_feasible` with:

```python
def required_charge_kw(e_used_kwh: float, offpeak_hours: float) -> float:
    """The average rate that refills `e_used_kwh` across the off-peak window.

    This is what the site actually has to draw, which is never more than
    USABLE_ENERGY_KWH / OFFPEAK_HOURS ~= 37.6 kW. The charger's 250 kW rating
    is what it *could* draw, and using the rating where the requirement
    belongs is a 6.6x overstatement of the recharge footprint.
    """
    if offpeak_hours <= 0.0:
        return float("inf")
    return e_used_kwh / offpeak_hours


def recharge_feasible(
    e_used_kwh: float,
    offpeak_hours: float,
    l_offpeak_max_kw: float,
    t_month: float,
) -> bool:
    """Can the battery refill off-peak without creating a new billed peak?

    Two independent predicates, both required:

      1. There is enough off-peak time: the required rate is within what the
         charger can deliver. CHARGER_KW is the right bound here -- it is a
         capability question.
      2. Charging on top of the existing off-peak load stays strictly below
         the monthly threshold, so the recharge does not become the new
         billing determinant. The REQUIRED rate is the right term here, not
         the charger rating: the site draws what it needs, not what the
         hardware could take. Testing the rating made this flag fire on 98%
         of kept Worcester rows and told the reader nothing.

    Returns False rather than raising so the caller can flag the row
    "recharge-constrained" and keep it in the table.
    """
    if offpeak_hours <= 0.0:
        return False
    needed = required_charge_kw(e_used_kwh, offpeak_hours)
    time_ok = needed <= CHARGER_KW
    headroom_ok = (l_offpeak_max_kw + needed) < t_month
    return bool(time_ok and headroom_ok)
```

- [ ] **Step 4: Run the scorer tests**

Run: `uv run pytest tests/test_scorer.py -v`

Expected: the three new tests PASS. **Existing recharge tests may now fail** — `test_recharge_infeasible_on_headroom_alone` and `test_recharge_headroom_is_strict` were written against the old `CHARGER_KW` term. Read each one before touching it. If a test's *intent* still holds (headroom can fail; the comparison is strict), keep the test and adjust its numbers so the intent is expressed against the required rate. If its intent was only to pin `CHARGER_KW` in that position, replace it with an equivalent assertion about `required_charge_kw`. **Do not delete a test to make the suite green** — every one of these is a behaviour someone chose to pin, and the prior plan's ledger records a case where four orphaned tests were nearly lost this way.

- [ ] **Step 5: Add the assumption row**

In `src/shave/assumptions.py`, append to `PUBLISHED`:

```python
    Assumption(
        "charger_rating", CHARGER_KW, "kW", "ASSUMED",
        "Powertown spec page, read as symmetric with the discharge rating",
        "The most the charger can draw, used only to ask whether the "
        "overnight window is long enough. The recharge FOOTPRINT is the rate "
        "the site actually needs -- at most 413.4 kWh over 11 hours, about "
        "37.6 kW -- because the battery draws what it must replace, not what "
        "the hardware could take.",
    ),
```

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest`
Expected: PASS, 897 + 3 new (minus any existing test you replaced rather than adjusted). Record the exact number in your report.

- [ ] **Step 7: Measure the effect on real Worcester data**

Run:
```bash
uv run python -c "
from shave import ingest, pipeline
from collections import Counter
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
s = pipeline.score_parcels(g); k = s[s['keep']]
c = Counter(f for t in k['flags'] for f in t)
print('kept:', len(k))
for f, n in c.most_common():
    print(f'  {f:24s} {n:5d}  ({n/len(k)*100:.0f}%)')
print()
print('recharge_constrained by source:')
rc = k[k['flags'].apply(lambda t: 'recharge_constrained' in t)]
print(' ', rc.groupby('source').size().to_dict())
print('  median offpeak/threshold ratio among constrained rows is what to look at')
"
```

**Pass condition, declared in advance:** `recharge_constrained` must fall **below 50% of kept rows**, from 98%. Report the exact figure and the by-source split. If it does not fall below 50%, do not adjust the threshold — report it, because it would mean the constraint is real and the flag was right, and that is a finding for the method page.

- [ ] **Step 8: Commit**

```bash
git add src/shave/scorer.py src/shave/assumptions.py tests/test_scorer.py
git commit -m "fix: the recharge test asks for the rate it needs, not the rating

recharge_constrained fired on 719 of 737 kept Worcester rows. A flag true of
98% of a table carries no information and would warn on almost every
published row.

The headroom predicate tested l_offpeak_max + CHARGER_KW < t_month with
CHARGER_KW at the full 250 kW rating, so the charger term alone exceeded a
typical 100-200 kW threshold before the site's own overnight load was
considered. The battery never has to draw its rating: at most 413.4 kWh over
an 11-hour window, about 37.6 kW. The first predicate already computed that
and discarded it.

CHARGER_KW keeps its job in the time test, where a capability bound is the
right question.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 2: A real named business on the top row

Success criterion 2, which the spec calls non-deferrable: *"The top-ranked site is a real, named Massachusetts operating business at a verifiable address, with a one-sentence checkable reason."*

MassGIS gives **owner of record**, not the operating business. Measured on the current top 50: 25 of 50 owners match a holding-company pattern — `RK WORCESTER CROSSING LLC`, `440 LINCOLN STREET HOLDING`, `LAVINE,ROBERT M TRUSTEE`. A ranked list whose top row says `MGM PENA LLC` fails the criterion even though the row is correct.

The resolution is manual and the spec budgets 90 minutes for it. What ships in code is the scaffold: a worksheet generator, a committed CSV, validation that refuses to silently accept a bad row, and a test that fails if the top-ranked row has no occupant.

**Files:**
- Create: `src/shave/occupants.py`
- Create: `data/occupants.csv`
- Create: `scripts/occupant_worksheet.py`
- Modify: `.gitignore` — negate `data/occupants.csv`
- Test: `tests/test_occupants.py` (new)

**Interfaces:**
- Consumes: `ingest.load_municipality`, `pipeline.score_parcels`.
- Produces:
  - `occupants.OCCUPANTS_PATH: Path`
  - `occupants.Occupant` — frozen dataclass with `loc_id, occupant, occupant_source, verified_on, note`
  - `occupants.OccupantError(ValueError)`
  - `occupants.load(path: Path | None = None) -> dict[str, Occupant]`
  - `occupants.attach(scored: pd.DataFrame) -> pd.DataFrame` — adds `occupant` and `occupant_source` columns
  - `occupants.coverage(scored: pd.DataFrame, top_n: int = 50) -> dict[str, int]`

- [ ] **Step 1: Write the failing test for the schema**

Create `tests/test_occupants.py`:

```python
import csv
from pathlib import Path

import pandas as pd
import pytest

from shave import occupants
from shave.occupants import OccupantError

HEADER = ["loc_id", "occupant", "occupant_source", "verified_on", "note"]


def write_occupants(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "occ.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HEADER})
    return path


def good_row(**overrides: str) -> dict[str, str]:
    base = {
        "loc_id": "F_573183_2919659",
        "occupant": "Price Rite Marketplace",
        "occupant_source": "https://example.com/listing",
        "verified_on": "2026-09-11",
        "note": "",
    }
    base.update(overrides)
    return base


def test_a_row_without_a_source_is_rejected():
    """An unsourced occupant name is a guess, and a guess on the top row is
    exactly the claim a domain expert would check first."""
    with pytest.raises(OccupantError, match="occupant_source"):
        occupants.load(write_occupants(Path("/tmp"), [good_row(occupant_source="")]))


def test_a_row_without_a_verification_date_is_rejected():
    with pytest.raises(OccupantError, match="verified_on"):
        occupants.load(write_occupants(Path("/tmp"), [good_row(verified_on="")]))


def test_a_malformed_date_is_rejected():
    with pytest.raises(OccupantError, match="verified_on"):
        occupants.load(write_occupants(Path("/tmp"), [good_row(verified_on="11/09/2026")]))


def test_duplicate_loc_id_is_rejected():
    rows = [good_row(), good_row(occupant="Something Else")]
    with pytest.raises(OccupantError, match="duplicate"):
        occupants.load(write_occupants(Path("/tmp"), rows))


def test_a_good_row_loads(tmp_path):
    loaded = occupants.load(write_occupants(tmp_path, [good_row()]))
    assert loaded["F_573183_2919659"].occupant == "Price Rite Marketplace"
    assert loaded["F_573183_2919659"].verified_on == "2026-09-11"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_occupants.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.occupants'`

- [ ] **Step 3: Write `src/shave/occupants.py`**

```python
"""Owner of record is not the operating business.

MassGIS L3 carries the assessor's owner, which for leased commercial property
is a realty trust or an LLC: `RK WORCESTER CROSSING LLC`, `440 LINCOLN STREET
HOLDING`. Measured on the current top 50, 25 of 50 are of that shape. A ranked
list whose first row names a holding company is correct and useless -- the
spec's success criterion is a real, named, checkable business.

There is no public dataset that maps a Massachusetts parcel to its operating
tenant. This is hand-resolved, one row at a time, and the CSV is committed so
the work is visible and auditable rather than living in someone's notes.

Every row carries a source URL and a verification date. An unsourced name is a
guess, and a guess on the top row is the first thing a domain expert checks.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

OCCUPANTS_PATH = Path(__file__).resolve().parents[2] / "data" / "occupants.csv"

FIELDS = ("loc_id", "occupant", "occupant_source", "verified_on", "note")


class OccupantError(ValueError):
    """The occupant table is malformed or internally inconsistent."""


@dataclass(frozen=True)
class Occupant:
    loc_id: str
    occupant: str
    occupant_source: str
    verified_on: str
    note: str = ""


def _require(value: str, field: str, where: str) -> str:
    text = (value or "").strip()
    if not text:
        raise OccupantError(f"{where} {field} is blank")
    return text


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict[str, Occupant]:
    """Read and validate the occupant table. Cached; call `load.cache_clear()`."""
    src = Path(path) if path is not None else OCCUPANTS_PATH
    if not src.exists():
        raise OccupantError(f"occupant table not found at {src}")

    rows: dict[str, Occupant] = {}
    with src.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise OccupantError(f"{src} is missing columns {sorted(missing)}")
        for lineno, raw in enumerate(reader, start=2):
            where = f"{src.name}:{lineno}"
            loc_id = _require(raw.get("loc_id", ""), "loc_id", where)
            if loc_id in rows:
                raise OccupantError(f"{where} duplicate loc_id {loc_id!r}")
            occupant = _require(raw.get("occupant", ""), "occupant", where)
            source = _require(raw.get("occupant_source", ""), "occupant_source", where)
            verified = _require(raw.get("verified_on", ""), "verified_on", where)
            try:
                dt.date.fromisoformat(verified)
            except ValueError as exc:
                raise OccupantError(
                    f"{where} verified_on must be ISO yyyy-mm-dd, got {verified!r}"
                ) from exc
            rows[loc_id] = Occupant(
                loc_id=loc_id,
                occupant=occupant,
                occupant_source=source,
                verified_on=verified,
                note=(raw.get("note") or "").strip(),
            )
    return rows


def attach(scored: pd.DataFrame, path: Path | None = None) -> pd.DataFrame:
    """Add `occupant` and `occupant_source`. Unresolved rows get empty strings.

    Empty rather than the owner name: showing the holding company in a column
    labelled "occupant" would assert something the table does not know.
    """
    table = load(path)
    out = scored.copy()
    out["occupant"] = out["loc_id"].map(lambda k: table[k].occupant if k in table else "")
    out["occupant_source"] = out["loc_id"].map(
        lambda k: table[k].occupant_source if k in table else ""
    )
    return out


def coverage(scored: pd.DataFrame, top_n: int = 50, path: Path | None = None) -> dict[str, int]:
    """How much of the head of the ranking is resolved. For the method page."""
    table = load(path)
    kept = scored[scored["keep"]] if "keep" in scored else scored
    top = kept.nlargest(top_n, "annual_savings_usd")
    return {
        "resolved_total": len(table),
        "top_n": int(len(top)),
        "top_n_resolved": int(top["loc_id"].isin(table).sum()),
    }
```

- [ ] **Step 4: Run the schema tests**

Run: `uv run pytest tests/test_occupants.py -v`

Expected: the five tests PASS. Note the first four call `occupants.load` with an explicit path and rely on `lru_cache` being keyed by that path; if a test bleeds state, add an autouse fixture calling `occupants.load.cache_clear()` before and after, exactly as `tests/test_crosswalk.py` does for the crosswalk.

- [ ] **Step 5: Write the worksheet generator**

Create `scripts/occupant_worksheet.py`:

```python
"""Emit the blank occupant worksheet for the top N ranked parcels.

    uv run python scripts/occupant_worksheet.py > /tmp/worksheet.csv

Fill `occupant` and `occupant_source` by hand -- Google Maps, the business's
own site, a Secretary of the Commonwealth corporate filing -- then merge the
completed rows into data/occupants.csv. The spec budgets about 90 minutes for
50 rows and calls the result non-deferrable: it is the demo.
"""

from __future__ import annotations

import argparse
import csv
import sys

from shave import ingest, pipeline

WORCESTER = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
COLUMNS = [
    "loc_id", "occupant", "occupant_source", "verified_on", "note",
    "_site_addr", "_city", "_owner", "_use_desc", "_sqft", "_annual_savings_usd",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=WORCESTER)
    parser.add_argument("--town-id", type=int, default=348)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--sweet-spot", action="store_true",
                        help="rank within the sweet-spot view instead of all kept rows")
    args = parser.parse_args()

    parcels = ingest.load_municipality(args.dir, town_id=args.town_id)
    scored = pipeline.score_parcels(parcels)

    detail = parcels.drop(columns="geometry")
    merged = scored.merge(detail, on="loc_id", how="left", suffixes=("", "_parcel"))
    rows = merged[merged["keep"]]
    if args.sweet_spot:
        rows = rows[rows["sweet_spot"]]
    rows = rows.nlargest(args.top, "annual_savings_usd")

    writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows.to_dict("records"):
        writer.writerow({
            "loc_id": row["loc_id"],
            "occupant": "",
            "occupant_source": "",
            "verified_on": "",
            "note": "",
            "_site_addr": row.get("site_addr", ""),
            "_city": row.get("city", ""),
            "_owner": row.get("owner", ""),
            "_use_desc": row.get("use_desc", ""),
            "_sqft": row.get("sqft", ""),
            "_annual_savings_usd": round(float(row["annual_savings_usd"]), 2),
        })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The `_`-prefixed columns are context for the human and are **not** part of the occupant schema; `occupants.load` ignores unknown columns, so a filled worksheet can be merged without stripping them, but the committed CSV should carry only the five real fields.

- [ ] **Step 6: Generate the worksheet and resolve the rows by hand**

Run:
```bash
uv run python scripts/occupant_worksheet.py --top 50 > /tmp/worksheet.csv
head -5 /tmp/worksheet.csv
```

Then resolve each row. This is human work, not code. For each `loc_id`, use `_site_addr` + `_city` to identify the business currently operating at that address, and record where you found it.

**Rules, and they matter more than speed:**
- If the operating business cannot be identified confidently, **leave the row out**. A blank is honest; a guess on a published list is not.
- If the parcel is genuinely owner-occupied and the owner name *is* the business (`ABBY KELLEY FOSTER CHARTER PUBLIC SCHOOL`, `CITY OF WORCESTER PUBLIC SCHOOLS`), record it with `occupant_source` pointing at the assessor record and a `note` saying owner-occupied.
- `occupant_source` must be a URL or a citable record, not "Google".
- `verified_on` is the date you looked, in `yyyy-mm-dd`.

Write the resolved rows to `data/occupants.csv` with exactly this header and no `_` columns:

```csv
loc_id,occupant,occupant_source,verified_on,note
```

- [ ] **Step 7: Commit the CSV past .gitignore**

`data/` is gitignored. Add the negation so the hand-authored table is tracked while raw extracts stay out:

```bash
printf '\n# hand-authored domain data, not a build artifact\n!data/occupants.csv\n' >> .gitignore
git add -f data/occupants.csv
git check-ignore -v data/occupants.csv || echo "tracked, good"
```

- [ ] **Step 8: Write the criterion test**

Append to `tests/test_occupants.py`:

```python
needs_worcester = pytest.mark.skipif(
    not Path("data/raw/M348_WORCESTER/L3_SHP_M348_Worcester/M348TaxPar_CY26_FY26.shp").exists(),
    reason="Worcester L3 extract not present (data/raw is gitignored)",
)


def test_the_committed_table_is_valid():
    """The shipped CSV must load. It is domain work, and a typo in it is a
    wrong claim on a published page."""
    occupants.load.cache_clear()
    table = occupants.load()
    assert table, "data/occupants.csv has no rows"
    for loc_id, row in table.items():
        assert row.occupant_source.startswith(("http://", "https://")) or row.note, (
            f"{loc_id}: a non-URL source needs a note saying what the record is"
        )


@needs_worcester
def test_the_top_ranked_row_names_a_real_business():
    """Success criterion 2, as a test.

    The spec: 'The top-ranked site is a real, named Massachusetts operating
    business at a verifiable address, with a one-sentence checkable reason.'
    If the head of the ranking is a holding company, the deliverable does not
    meet its own bar and this must fail.
    """
    from shave import ingest, pipeline

    occupants.load.cache_clear()
    parcels = ingest.load_municipality(
        "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester", town_id=348
    )
    scored = occupants.attach(pipeline.score_parcels(parcels))
    top = scored[scored["keep"]].nlargest(1, "annual_savings_usd").iloc[0]

    assert top["occupant"], f"top-ranked parcel {top['loc_id']} has no resolved occupant"
    assert top["occupant_source"], "and no source for it"


@needs_worcester
def test_most_of_the_top_fifty_is_resolved():
    """A partly-resolved head is fine and is stated on the method page; a
    mostly-unresolved one means the demo does not hold up to clicking."""
    from shave import ingest, pipeline

    occupants.load.cache_clear()
    parcels = ingest.load_municipality(
        "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester", town_id=348
    )
    scored = pipeline.score_parcels(parcels)
    stats = occupants.coverage(scored, top_n=50)

    assert stats["top_n_resolved"] >= 40, (
        f"only {stats['top_n_resolved']} of the top 50 are resolved"
    )
```

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest`
Expected: PASS. Report the count and the output of:

```bash
uv run python -c "
from shave import ingest, pipeline, occupants
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
s = pipeline.score_parcels(g)
print(occupants.coverage(s, top_n=50))
top = occupants.attach(s)
top = top[top['keep']].nlargest(5, 'annual_savings_usd')
print(top[['loc_id','occupant','archetype','annual_savings_usd']].to_string(index=False))
"
```

**Pass condition:** the top-ranked row prints a business name, not a blank.

- [ ] **Step 10: Commit**

```bash
git add src/shave/occupants.py scripts/occupant_worksheet.py tests/test_occupants.py .gitignore
git add -f data/occupants.csv
git commit -m "feat: resolve the operating business behind the owner of record

MassGIS carries the assessor's owner, which for leased commercial property is
a realty trust or an LLC -- 25 of the current top 50. A ranked list whose
first row says RK WORCESTER CROSSING LLC is correct and useless.

There is no public parcel-to-tenant dataset for Massachusetts, so this is
hand-resolved and the table is committed, sourced and dated. A row without a
source URL or a verification date is refused at load: an unsourced name is a
guess, and a guess on the top row is the first thing a domain expert checks.

Closes success criterion 2.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## Task 3: The method page, as data

Premise P6: *publish the method, lineage and failure modes — not just the output.* Success criterion 6 names six things the page must say the tool cannot do.

Prose in an HTML file can drift from the code that ran. This task assembles the whole method payload **from the code**, so the published assumptions are provably the computed ones and the limitations list cannot quietly lose a row. The site plan then renders a dict and adds no claims of its own.

**Files:**
- Create: `src/shave/method.py`
- Test: `tests/test_method.py` (new)

**Interfaces:**
- Consumes: `assumptions.published_rows`, `assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR`, `assumptions.UNANCHORED_ARCHETYPES`, `crosswalk.load`, `crosswalk.coverage_summary`, `pipeline.UNSCORED_REASONS`, `occupants.coverage`, `comstock.COMSTOCK_RELEASE`.
- Produces:
  - `method.Limitation` — frozen dataclass `key: str`, `statement: str`
  - `method.LIMITATIONS: tuple[Limitation, ...]`
  - `method.FLAG_MEANINGS: dict[str, str]`
  - `method.KNOWN_GAPS: tuple[Limitation, ...]`
  - `method.method_payload(scored: pd.DataFrame, regression: dict | None = None) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_method.py`:

```python
import pandas as pd
import pytest

from shave import method


def test_every_limitation_the_spec_names_is_present():
    """Success criterion 6, verbatim: 'The method page states what the tool
    cannot do: no measurement, no interconnection feasibility, no per-feeder
    constraints, no underwriting, multi-tenant buildings overstated,
    industrial shapes modeled not measured.'"""
    required = {
        "no_measurement",
        "no_interconnection",
        "no_feeder_constraints",
        "no_underwriting",
        "multi_tenant_overstated",
        "industrial_modeled_not_measured",
    }
    present = {limitation.key for limitation in method.LIMITATIONS}
    assert required <= present, f"missing: {sorted(required - present)}"


def test_every_limitation_has_a_real_sentence():
    for limitation in method.LIMITATIONS:
        assert limitation.statement.endswith("."), limitation.key
        assert len(limitation.statement) > 40, f"{limitation.key} is a label, not a statement"


def test_every_pipeline_flag_is_explained():
    """A flag on a published row with no explanation is a warning the reader
    cannot act on."""
    from shave import pipeline

    for reason in pipeline.UNSCORED_REASONS:
        assert reason in method.FLAG_MEANINGS, f"unscored reason {reason} unexplained"
    for flag in ("power_limited", "scale_extrapolation", "recharge_constrained", "thin_cohort"):
        assert flag in method.FLAG_MEANINGS, f"row flag {flag} unexplained"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_method.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.method'`

- [ ] **Step 3: Write `src/shave/method.py`**

```python
"""Everything the method page says, assembled from the code that ran.

Premise P6 is to publish the method, the lineage and the failure modes rather
than only the output. Prose in a template drifts from the code; a payload
built here cannot. The published assumptions are the computed assumptions
because they are the same objects, and the limitations list cannot silently
lose a row because a test asserts the spec's own six are in it.

The site renders this dict. It adds no claims of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from shave import crosswalk, occupants, pipeline
from shave.assumptions import (
    COMSTOCK_RELEASE,
    ELECTRIC_INTENSITY_KWH_PER_SQFT_YR,
    LIKELY_SINGLE_METERED_MAX_SQFT,
    UNANCHORED_ARCHETYPES,
    published_rows,
)


@dataclass(frozen=True)
class Limitation:
    key: str
    statement: str


#: What the tool cannot do. The first six are success criterion 6 verbatim;
#: the rest are limits the spec names elsewhere and that a domain expert would
#: otherwise find on their own, which is the worse way to find them.
LIMITATIONS: tuple[Limitation, ...] = (
    Limitation(
        "no_measurement",
        "This tool contains no per-building measurement. It is a structured "
        "prior over three public assessor fields -- use code, building area, "
        "municipality -- plus a modelled load-shape library. Use it to order a "
        "call list, not to underwrite one.",
    ),
    Limitation(
        "no_interconnection",
        "Nothing here checks interconnection feasibility. Whether the utility "
        "will permit a 250 kW resource at a given service is a study, not a "
        "public dataset.",
    ),
    Limitation(
        "no_feeder_constraints",
        "Per-feeder hosting capacity is not modelled. Two identical buildings "
        "on different feeders can have entirely different answers, and that "
        "difference is invisible from the assessor record.",
    ),
    Limitation(
        "no_underwriting",
        "No figure here is an underwriting input. The savings estimate is a "
        "ranking key expressed in dollars because dollars are orderable, not "
        "because they are bankable.",
    ),
    Limitation(
        "multi_tenant_overstated",
        "Demand charges accrue to a service account, not a building. A "
        "multi-tenant building has many meters with non-coincident peaks and "
        "none of them equals the aggregate, so this systematically overstates "
        "large buildings.",
    ),
    Limitation(
        "industrial_modeled_not_measured",
        "Industrial load shapes are modelled, not measured. ComStock models 14 "
        "commercial building types and no industry at all, so every row marked "
        "modelled carries a synthesised shape whose magnitude comes from "
        "published intensity data and whose form comes from declared "
        "parameters. There is no US industrial ground truth to check them "
        "against, and they remain the weakest part of this work.",
    ),
    Limitation(
        "distribution_demand_only",
        "The saving is the distribution demand charge only. The optional "
        "Transmission Coincident Peak Demand Charge and the customer's ISO-NE "
        "capacity (ICAP) tag are both per-kW value streams and neither is "
        "modelled here.",
    ),
    Limitation(
        "kva_clause_not_modelled",
        "The tariff bills the greater of the fifteen-minute kW peak or 90% of "
        "the kVA peak, so poor power factor costs money. Motor-heavy loads run "
        "lower power factor, which means this is a signal, but it is not "
        "quantified anywhere in these numbers.",
    ),
    Limitation(
        "single_meter_proxy_is_conservative",
        f"The likely-single-metered proxy caps building area at "
        f"{LIKELY_SINGLE_METERED_MAX_SQFT:,} sq ft. Single-tenant distribution "
        "centres are routinely larger, so the one ICP sector ComStock covers "
        "well is capped at MED confidence by this rule. That is a deliberate "
        "trade, not an oversight.",
    ),
    Limitation(
        "clean_peak_not_quantified",
        "Demand charges bill the customer's non-coincident monthly peak; Clean "
        "Peak pays for output during the ISO-NE system coincident peak hour. "
        "These are different events and dispatching for one can forfeit the "
        "other, so no stacked-revenue number is published here.",
    ),
    Limitation(
        "customer_savings_not_developer_margin",
        "The ranking is customer demand-charge savings. A developer's own "
        "ranking is margin -- savings share minus cost to serve, including "
        "service upgrades, wall availability, permitting and trucking -- and "
        "those diverge.",
    ),
    Limitation(
        "collapse_points",
        "Two assessor use codes carry whole sectors inside them. Code 4000 is "
        "every manufacturer in the state, so machine shops, metal fabricators, "
        "food producers and commercial laundries are indistinguishable; code "
        "4010 hides refrigerated cold storage inside ambient warehousing, and "
        "the published intensity for those two differs by 5.6x. Within either "
        "code the ranking is driven by floor area and rate class, not by shape.",
    ),
    Limitation(
        "large_sites_still_rank_high",
        "Ranking on absolute dollars rewards having more kilowatts to remove, "
        "so the default order is led by large buildings that shave a small "
        "fraction of a big peak. The sweet-spot view is the one that answers "
        "the question this tool exists for, and the two are shown separately "
        "rather than blended into a score.",
    ),
)


#: Gaps that are real and unbuilt. Naming them is cheaper than being caught by
#: them, and a reader who finds an unnamed gap stops trusting the named ones.
KNOWN_GAPS: tuple[Limitation, ...] = (
    Limitation(
        "no_siting_screen",
        "No siting screen has been run. Whether a site has an unobstructed "
        "wall run long enough for two cabinets is not checked, so nothing here "
        "screens out zero-lot-line or fully-built parcels.",
    ),
    Limitation(
        "no_class_shape_check",
        "The bottom-up aggregate has not been compared against National Grid's "
        "published class load shapes. The source workbook is not in hand; the "
        "check is specified and unrun, and is described here as a plan rather "
        "than a result.",
    ),
    Limitation(
        "one_municipality",
        "Worcester only. The pipeline is municipality-parameterised and the "
        "method extends statewide, but only one town's assessor extract has "
        "been processed.",
    ),
)


#: Every flag and unscored reason a published row can carry, in plain words.
FLAG_MEANINGS: dict[str, str] = {
    "power_limited": (
        "The battery hits its 250 kW power rating in at least one month, so "
        "the saving shown is a floor rather than an estimate. The honest "
        "reading is that this site wants more than one unit."
    ),
    "scale_extrapolation": (
        "The parcel is more than five times the floor area of the measured "
        "building whose shape it borrows. A building five times the size is a "
        "different building, not a bigger one."
    ),
    "recharge_constrained": (
        "Refilling the battery overnight would either need more time than the "
        "off-peak window allows, or would push the site's overnight load above "
        "the threshold it is trying to hold."
    ),
    "thin_cohort": (
        "Fewer than 30 buildings of this type exist in the county's measured "
        "dataset, so the representative shape rests on a small sample."
    ),
    "no_floor_area": (
        "The assessor record carries no building area, and floor area is the "
        "entire scale factor. Carried unscored rather than guessed."
    ),
    "no_intensity_anchor": (
        "No defensible published electricity intensity exists for this "
        "building type, so no magnitude can be derived. Carried unscored "
        "rather than invented."
    ),
    "no_archetype_profile": (
        "No load-shape profile could be built for this archetype."
    ),
}


def method_payload(
    scored: pd.DataFrame, regression: dict | None = None
) -> dict[str, object]:
    """Everything the method page renders, computed from this run.

    `regression` is the output of the regression task if it has been run. When
    it is absent the payload says so in those words rather than omitting the
    section, because a missing R-squared and an unreported one look identical
    to a reader and only one of them is honest.
    """
    kept = scored[scored["keep"]] if "keep" in scored else scored
    unscored = scored[scored["unscored_reason"].notna()]

    return {
        "assumptions": published_rows(),
        "limitations": [
            {"key": limitation.key, "statement": limitation.statement}
            for limitation in LIMITATIONS
        ],
        "known_gaps": [
            {"key": gap.key, "statement": gap.statement} for gap in KNOWN_GAPS
        ],
        "flag_meanings": dict(FLAG_MEANINGS),
        "lineage": {
            "parcels": "MassGIS Level 3 Assessors Parcels, TaxPar and Assess",
            "load_shapes_measured": f"NREL ComStock {COMSTOCK_RELEASE}, upgrade 0",
            "load_shapes_modelled": "declared parameters; see intensity anchors",
            "intensity_anchors": "EIA CBECS 2018 Table C22, EIA MECS 2018 Tables 3.2 and 9.1",
            "tariff": "National Grid M.D.P.U. No. 1591 and the MECO summary of rates",
        },
        "coverage": {
            "parcels_total": int(len(scored)),
            "kept": int(len(kept)),
            "sweet_spot": int(kept["sweet_spot"].sum()) if "sweet_spot" in kept else 0,
            "unscored": (
                unscored["unscored_reason"].value_counts().to_dict()
                if len(unscored)
                else {}
            ),
            "crosswalk": crosswalk.coverage_summary(),
            "modelled_archetypes_anchored": sorted(ELECTRIC_INTENSITY_KWH_PER_SQFT_YR),
            "modelled_archetypes_unanchored": sorted(UNANCHORED_ARCHETYPES),
            "assess_years": (
                sorted(scored["assess_fy"].dropna().unique().tolist())
                if "assess_fy" in scored
                else []
            ),
        },
        "occupants": occupants.coverage(scored, top_n=50),
        "regression": regression
        if regression is not None
        else {"status": "not yet run; the figures below are unreported, not zero"},
    }
```

- [ ] **Step 4: Run the first tests**

Run: `uv run pytest tests/test_method.py -v`
Expected: PASS, all three.

- [ ] **Step 5: Write the payload tests**

Append to `tests/test_method.py`:

```python
def _fake_scored() -> pd.DataFrame:
    return pd.DataFrame([
        {"loc_id": "A", "keep": True, "sweet_spot": True,
         "annual_savings_usd": 100.0, "unscored_reason": None, "assess_fy": 2026},
        {"loc_id": "B", "keep": True, "sweet_spot": False,
         "annual_savings_usd": 50.0, "unscored_reason": None, "assess_fy": 2026},
        {"loc_id": "C", "keep": False, "sweet_spot": False,
         "annual_savings_usd": 0.0, "unscored_reason": "no_floor_area", "assess_fy": 2026},
    ])


def test_payload_counts_match_the_frame():
    payload = method.method_payload(_fake_scored())
    assert payload["coverage"]["parcels_total"] == 3
    assert payload["coverage"]["kept"] == 2
    assert payload["coverage"]["sweet_spot"] == 1
    assert payload["coverage"]["unscored"] == {"no_floor_area": 1}


def test_payload_carries_every_published_assumption():
    from shave.assumptions import PUBLISHED

    payload = method.method_payload(_fake_scored())
    assert len(payload["assumptions"]) == len(PUBLISHED)
    for row in payload["assumptions"]:
        assert row["source"], f"{row['key']} has no source"
        assert row["provenance"] in ("FILED", "ASSUMED", "DERIVED")


def test_an_unrun_regression_says_so_rather_than_reporting_zero():
    payload = method.method_payload(_fake_scored())
    assert "not yet run" in payload["regression"]["status"]


def test_a_supplied_regression_is_passed_through():
    payload = method.method_payload(
        _fake_scored(), regression={"r2_size_and_rate": 0.82, "r2_with_archetype": 1.0}
    )
    assert payload["regression"]["r2_size_and_rate"] == 0.82


def test_the_payload_is_json_serialisable():
    """It is going into a static file. A numpy scalar in here fails at deploy
    time, which is the worst time to find it."""
    import json

    json.dumps(method.method_payload(_fake_scored()))
```

- [ ] **Step 6: Run them**

Run: `uv run pytest tests/test_method.py -v`

Expected: PASS. `test_the_payload_is_json_serialisable` is the one likely to fail first — `value_counts().to_dict()` yields numpy integer keys or values in some pandas versions, and `crosswalk.coverage_summary()` may return numpy ints. If it fails, coerce with `int(...)` at the point the value is built in `method_payload`; do not add a custom JSON encoder, because the export in the prior plan's Task 5 writes this file and a bespoke encoder there would be a second place for the schema to drift.

- [ ] **Step 7: Run the whole suite and print the real payload**

Run: `uv run pytest`
Expected: PASS.

Then:
```bash
uv run python -c "
import json
from shave import ingest, pipeline, method
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
p = method.method_payload(pipeline.score_parcels(g))
print('assumptions:', len(p['assumptions']))
print('limitations:', len(p['limitations']), '| known gaps:', len(p['known_gaps']))
print('coverage:', json.dumps(p['coverage'], indent=2)[:600])
print('occupants:', p['occupants'])
print('bytes as json:', len(json.dumps(p)))
"
```

**Pass condition:** the payload serialises, `assumptions` is 23 (22 plus Task 1's charger row), `limitations` is 13, `known_gaps` is 3, and `coverage.parcels_total` is 2,099.

- [ ] **Step 8: Commit**

```bash
git add src/shave/method.py tests/test_method.py
git commit -m "feat: the method page, assembled from the code that ran

Premise P6 is to publish the method, the lineage and the failure modes.
Prose in a template drifts from the code; this payload cannot, because the
published assumptions are the same objects the scorer imported.

Thirteen limitations, including the spec's six verbatim, three named gaps for
work that is specified and unbuilt, and a plain-words meaning for every flag
and unscored reason a published row can carry. An unrun regression reports
itself as unrun rather than as zero.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01XBVg1CupSRWe1YGgZjes48"
```

---

## What this plan deliberately leaves for the next one

This is the Python half. The next plan is the site, and it is a different subsystem in a different language.

| Deferred | Why it is not here | Est. |
|---|---|---|
| Static ranked-list page: table, inline reason on the selected row, detail drawer, 24h sparkline with the billed window shaded | Consumes `ranked.json` from first-ranked-list Task 5 and the payload from Task 3 here. `DESIGN.md` and the approved mockup are already in the repo. | 6h |
| Encoding map: parcel fill by saving, outline by rate class, cross-linked with the table | Needs simplified geometry in the export, which Task 5 of the prior plan defines. | 5-6h |
| Address box over a static prebuilt index | Needs the export. No database, by design. | 2h |
| Deploy: one Cloudflare Worker with static assets, auto-deploy on push | Nothing to serve until the site exists. | 2h |
| `STRUCTURES_POLY` join and the siting screen | Independent of everything here. Unblocks the `BLD_AREA` fallback, which matters for one Worcester parcel today and more when other towns land. | 4.5h |
| New Bedford and Chicopee | Each needs an L3 download, a crosswalk pass over its use codes, and its own `county_gisjoin` — New Bedford is Bristol, Chicopee is Hampden. | 2h |
| MECOLS class-shape check | `MECOLS.xlsx` is not on disk. Re-fetch before scheduling. Task 3 already names this as a known gap. | 1h + fetch |

---

## Self-Review

**Spec coverage.** Task 1 completes the recharge predicate from the spec's "Recharge feasibility — as a test, not a wave". Task 2 completes Stage 1 step 7 and success criterion 2. Task 3 completes success criterion 6 and premise P6's "publish the method, lineage and failure modes", and names criterion 4 as an unrun gap rather than claiming it. Success criteria 1, 3 and 7 are the site and the prior plan's Task 6, both tabled above with reasons. Criterion 5 is already met.

**Placeholder scan:** clean. Every code step carries its code; every test step carries its test. The one step that is human work rather than code — Task 2 step 6 — says so explicitly, states the rules that govern it, and is bounded by a test in step 8 that fails if it was not done.

**Type consistency:** `occupants.Occupant` fields are the five CSV columns and `occupants.load` returns `dict[str, Occupant]` keyed by `loc_id`, which `attach` and `coverage` both index by the `loc_id` column that `ingest.OUTPUT_COLUMNS` and `pipeline.ScoredRow` share. `method.method_payload` reads `keep`, `sweet_spot`, `unscored_reason` and `assess_fy`, all of which `pipeline.score_parcels` emits except `assess_fy`, which comes from the parcel frame — `method_payload` guards it with an `in` check and returns `[]` when absent, so it is correct against a bare scored frame and richer against a merged one. `method.FLAG_MEANINGS` keys are asserted in test against `pipeline.UNSCORED_REASONS` and the four literal flag names `pipeline.score_parcel` appends.

**One deviation from the spec, stated where it is made:** the spec's recharge predicate is written as `L_offpeak_max + charger_kW < T_month`. Task 1 substitutes the required charge rate for the charger rating, because the rating form fires on 98% of kept rows and the spec's own intent — "does refilling create a new peak?" — is a question about the load the recharge actually adds.
