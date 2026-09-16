# Occupant Worksheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take occupant resolution from 4 of the top 50 toward the spec's bar. Research-assisted candidates are drafted for every unresolved head-of-list row, and **nothing reaches `data/occupants.csv` until a person has verified it**.

**Architecture:**
- **Selection.** A pure module selects the rows that need an operating business: the top 50 by dollars across all covered towns, plus each town's rank-1 row on each list. It writes them to a committed worksheet, `data/occupant_candidates.csv`.
- **Research.** An agent drafts `candidate_occupant`, one source URL and one sentence of evidence per row, leaving every row `pending`.
- **Verification.** The user marks rows `verified` or `rejected` and initials them.
- **Promotion.** A promote step moves only verified, sourced, initialled rows into `occupants.csv`. The existing loader validates them, and the coverage ratchet is raised to what was actually achieved.

**Tech Stack:** Python 3.11, pandas, pytest. The agent's web research uses WebSearch/WebFetch at execution time; nothing here calls the network from code.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`
- Stage 1 step 7: *"Occupant resolution for the top 50 rows. L3 gives owner of record, which for leased industrial is `123 ELM STREET REALTY TRUST`, not the operating business. Manual lookup is fine — 50 rows is about 90 minutes. This is the demo; it does not get cut."*
- Success criterion 2: *"The top-ranked site is a real, named Massachusetts operating business at a verifiable address, with a one-sentence checkable reason."*

**Depends on:** `2026-09-15-fall-river-and-lowell.md` and `2026-09-15-three-town-site.md`. Adding towns changes who is in the top 50, so resolving names before the towns land would spend the work on the wrong rows.

## Global Constraints

- **A person verifies every name.** The agent never sets `status` to `verified` and never edits `data/occupants.csv` directly. `promote` refuses a verified row without a `reviewer` and an http(s) source.
- **A blank is honest; a guess is not.** This is the rule already written in `scripts/occupant_worksheet.py`. A row with no confident match keeps an empty candidate and says what was checked.
- **One source URL per row**, of the kinds listed in Task 3's research protocol. Never a search-results page and never a bare map pin.
- **Research is never lost.** Regenerating the worksheet keeps every existing row's candidate, evidence, status and reviewer cells.
- **Tooling:**
  - Run `uv run pytest` **without `-q`**.
  - `node`/`npx`: `NB="$HOME/.nvm/versions/node/v22.18.0/bin"`.
- **Baseline.** Record **B** in Task 1 Step 1.
- Branch: `git checkout -b feat/occupant-worksheet`.
- Every commit ends with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR
  ```

---

## Verified facts

**The table today.** `data/occupants.csv` holds **4 rows**:
- UMass Chan Medical School (`F_585218_2926290`)
- RK Worcester Crossing / Walmart anchor (`F_577265_2910122`)
- The Hanover Insurance Group (`F_579517_2932440`)
- Saint Vincent Hospital (`F_575894_2921704`)

Every row has `loc_id, occupant, occupant_source, verified_on, note`.

**The loader.** `occupants.load` rejects a blank source, a blank or non-ISO `verified_on`, a duplicate `loc_id`, and a missing column. `test_the_committed_table_is_valid` additionally requires an http(s) source or a note.

**The ratchet.** `tests/test_occupants.py` has `RESOLVED_TOP_50_TODAY = 4`, `SPEC_TARGET_TOP_50 = 40`, and `occupants.coverage(scored, top_n=50)`. That call ranks **kept** rows of whatever frame it is given by `annual_savings_usd` and counts table hits in the top 50.

**The worksheet script.** `scripts/occupant_worksheet.py` loads Worcester only and prints a blank CSV to stdout, so filled cells are lost on every re-run.

**Why the owner is the wrong name.** Measured on the Worcester top 50 in an earlier plan, 25 of 50 owners are holding-company shapes (`… REALTY TRUST`, `… HOLDING`, `… LLC`).

**What a verified row looks like**, from the committed table: the Hanover row cites `https://www.hanover.com/`, with the note *"Owner of record is 440 LINCOLN STREET HOLDING. This is the case the occupant table exists for."*

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/occupant_worksheet.py` *(new)* | Select rows, merge with existing research, write the worksheet, promote verified rows. |
| `scripts/occupant_worksheet.py` *(rewrite)* | All covered towns → `data/occupant_candidates.csv`. |
| `scripts/promote_occupants.py` *(new)* | Verified worksheet rows → `data/occupants.csv`. |
| `data/occupant_candidates.csv` *(new, committed)* | The research, visible and auditable. |
| `tests/test_occupant_worksheet.py` *(new)*, `tests/test_occupants.py` | |

---

## Task 1: The worksheet, across towns, that never loses research

**Files:**
- Create: `src/shave/occupant_worksheet.py`, `tests/test_occupant_worksheet.py`
- Rewrite: `scripts/occupant_worksheet.py`

**Interfaces:**
- Consumes: `towns.TOWNS`, `towns.by_id` and ingest `town_id` (towns plan); `occupants.load`.
- Produces:
  - `occupant_worksheet.FIELDS: tuple[str, ...]`
  - `occupant_worksheet.STATUSES = ("pending", "verified", "rejected")`
  - `occupant_worksheet.select_rows(scored, parcels, existing: set[str], top_n: int = 50) -> pd.DataFrame`
  - `occupant_worksheet.write_worksheet(rows, path) -> int`, returning rows written, with existing research cells preserved
  - `occupant_worksheet.CANDIDATES_PATH = Path("data/occupant_candidates.csv")`

- [ ] **Step 1: Branch and baseline**

```bash
git checkout -b feat/occupant-worksheet
uv run pytest 2>&1 | tail -1
```

Record **B**.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_occupant_worksheet.py`:

```python
"""Which rows need an operating business, and how research survives re-runs."""

import csv

import pandas as pd
import pytest

from shave import occupant_worksheet as ow


def _frames():
    rows = []
    # Worcester: 3 comstock, 1 modeled. Lowell: 1 comstock, 1 modeled. One dropped row.
    spec = [
        ("W1", 348, "comstock", 9000.0, True), ("W2", 348, "comstock", 8000.0, True),
        ("W3", 348, "comstock", 100.0, True), ("W4", 348, "modeled", 7000.0, True),
        ("L1", 160, "comstock", 50.0, True), ("L2", 160, "modeled", 40.0, True),
        ("X9", 348, "comstock", 99_999.0, False),
    ]
    for loc_id, town_id, source, usd, keep in spec:
        rows.append({"loc_id": loc_id, "source": source, "annual_savings_usd": usd, "keep": keep})
    scored = pd.DataFrame(rows)
    parcels = pd.DataFrame([{
        "loc_id": loc_id, "town_id": town_id, "site_addr": f"{loc_id} MAIN ST",
        "owner": f"{loc_id} REALTY TRUST", "use_desc": "Warehouse", "sqft": 10_000.0,
    } for loc_id, town_id, *_ in spec])
    return scored, parcels


def test_selection_is_the_top_n_plus_every_towns_list_heads_minus_resolved():
    scored, parcels = _frames()

    rows = ow.select_rows(scored, parcels, existing={"W2"}, top_n=2)

    ids = list(rows["loc_id"])
    # top 2 kept by dollars: W1, W2 (W2 already resolved); heads: W1, W4, L1, L2
    assert set(ids) == {"W1", "W4", "L1", "L2"}
    assert "X9" not in ids, "a dropped row is never on the list"
    assert ids == sorted(ids, key=lambda i: -dict(zip(scored.loc_id, scored.annual_savings_usd))[i])
    lowell_head = rows.set_index("loc_id").loc["L1"]
    assert (lowell_head["town"], lowell_head["list"], lowell_head["rank"]) == ("Lowell", "comstock", 1)


def test_rewriting_the_worksheet_keeps_every_research_cell(tmp_path):
    scored, parcels = _frames()
    path = tmp_path / "candidates.csv"
    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        table = list(csv.DictReader(fh))
    for row in table:
        if row["loc_id"] == "L1":
            row.update(candidate_occupant="Acme Mills", candidate_source="https://acme.example/lowell",
                       evidence="Contact page lists L1 MAIN ST.", status="verified", reviewer="PJ")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ow.FIELDS)
        writer.writeheader()
        writer.writerows(table)

    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        again = {r["loc_id"]: r for r in csv.DictReader(fh)}
    assert again["L1"]["candidate_occupant"] == "Acme Mills"
    assert again["L1"]["status"] == "verified" and again["L1"]["reviewer"] == "PJ"
    assert again["W4"]["status"] == "pending"


def test_a_new_row_starts_pending_with_empty_research():
    scored, parcels = _frames()
    rows = ow.select_rows(scored, parcels, existing=set(), top_n=1)
    assert set(rows["status"]) == {"pending"}
    assert set(rows["candidate_occupant"]) == {""}
```

Run: `uv run pytest tests/test_occupant_worksheet.py`
Expected: FAIL — `ImportError: cannot import name 'occupant_worksheet'`.

- [ ] **Step 3: Write `src/shave/occupant_worksheet.py`**

```python
"""The occupant worksheet: which rows need an operating business, and the
research drafted for each, waiting for a person to verify it.

The assessor records the owner of record, which for leased commercial property
is a realty trust or a holding company. The operating business is what a
reader checks first, and there is no public dataset that maps one to the
other. So candidates are drafted -- one name, one source, one sentence of
evidence -- and nothing reaches data/occupants.csv until a person marks the
row verified and initials it.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pandas as pd

from shave import occupants, towns

CANDIDATES_PATH = Path("data/occupant_candidates.csv")

FIELDS: tuple[str, ...] = (
    "loc_id", "town", "list", "rank", "site_addr", "owner", "use_desc", "sqft",
    "annual_savings_usd",
    # research, drafted by the agent
    "candidate_occupant", "candidate_source", "evidence",
    # verification, by a person
    "status", "reviewer", "reviewer_note",
)
RESEARCH_FIELDS: tuple[str, ...] = (
    "candidate_occupant", "candidate_source", "evidence", "status", "reviewer", "reviewer_note",
)
STATUSES: tuple[str, ...] = ("pending", "verified", "rejected")


def select_rows(
    scored: pd.DataFrame, parcels: pd.DataFrame, existing: set[str], top_n: int = 50
) -> pd.DataFrame:
    """The top `top_n` kept rows by dollars across every town, plus each town's
    rank-1 row on each list, less the rows already resolved.

    Rank is within town and list, which is what the page shows.
    """
    detail = pd.DataFrame(parcels)[["loc_id", "town_id", "site_addr", "owner", "use_desc", "sqft"]]
    kept = scored[scored["keep"].astype(bool)].merge(detail, on="loc_id", how="left")
    kept = kept.assign(
        rank=kept.groupby(["town_id", "source"])["annual_savings_usd"]
        .rank(ascending=False, method="first").astype(int)
    )
    top = kept.nlargest(top_n, "annual_savings_usd")
    heads = kept[kept["rank"] == 1]
    rows = (
        pd.concat([top, heads])
        .drop_duplicates("loc_id")
        .loc[lambda f: ~f["loc_id"].isin(existing)]
        .sort_values("annual_savings_usd", ascending=False)
    )
    out = pd.DataFrame({
        "loc_id": rows["loc_id"].astype(str),
        "town": [towns.by_id(int(t)).name for t in rows["town_id"]],
        "list": rows["source"].astype(str),
        "rank": rows["rank"].astype(int),
        "site_addr": rows["site_addr"].fillna("").astype(str),
        "owner": rows["owner"].fillna("").astype(str),
        "use_desc": rows["use_desc"].fillna("").astype(str),
        "sqft": rows["sqft"].round(0),
        "annual_savings_usd": rows["annual_savings_usd"].round(0),
    })
    for field in RESEARCH_FIELDS:
        out[field] = "pending" if field == "status" else ""
    return out.reset_index(drop=True)[list(FIELDS)]


def _read(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["loc_id"]: row for row in csv.DictReader(fh)}


def write_worksheet(rows: pd.DataFrame, path: Path | str = CANDIDATES_PATH) -> int:
    """Write the worksheet, keeping every research cell already in the file."""
    path = Path(path)
    previous = _read(path)
    records = rows.to_dict("records")
    for record in records:
        old = previous.get(str(record["loc_id"]))
        if old:
            for field in RESEARCH_FIELDS:
                record[field] = old.get(field, record[field])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(records)
    return len(records)
```

Rewrite `scripts/occupant_worksheet.py`:

```python
"""Write the occupant worksheet for every covered town.

    uv run python scripts/occupant_worksheet.py

Rows: the top 50 kept parcels by dollars across all towns, plus each town's
rank-1 row on each list, less anything already in data/occupants.csv.
Research already in data/occupant_candidates.csv is kept on every re-run.

Rules that matter more than speed:
  - If the operating business cannot be identified confidently, leave the
    candidate blank and say in `evidence` what was checked. A blank is honest;
    a guess on a published list is not.
  - `candidate_source` is one URL a reader can open, never a search page.
  - Only a person sets `status` to verified or rejected, and initials `reviewer`.
"""

from __future__ import annotations

import sys

import pandas as pd

from shave import ingest, occupant_worksheet, occupants, pipeline, siting, towns


def main() -> int:
    all_parcels, all_scored = [], []
    for town in towns.TOWNS:
        parcels = ingest.load_municipality(
            town.l3_dir, town_id=town.town_id,
            structures_path=siting.structures_path(town.town_id),
        )
        all_parcels.append(pd.DataFrame(parcels.drop(columns=["geometry", "wall_segment"])))
        all_scored.append(pipeline.score_parcels(parcels))
    parcels = pd.concat(all_parcels, ignore_index=True)
    scored = pd.concat(all_scored, ignore_index=True)

    rows = occupant_worksheet.select_rows(scored, parcels, existing=set(occupants.load()))
    n = occupant_worksheet.write_worksheet(rows)
    print(f"{n} rows -> {occupant_worksheet.CANDIDATES_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run, generate, commit**

```bash
uv run pytest tests/test_occupant_worksheet.py
uv run python scripts/occupant_worksheet.py
uv run python -c "
import csv, collections; rows = list(csv.DictReader(open('data/occupant_candidates.csv')))
print(len(rows), 'rows', dict(collections.Counter(r['town'] for r in rows)), dict(collections.Counter(r['list'] for r in rows)))"
uv run pytest
git add src/shave/occupant_worksheet.py scripts/occupant_worksheet.py data/occupant_candidates.csv tests/test_occupant_worksheet.py
git commit -m "feat: an occupant worksheet across towns that never loses research

The top 50 kept rows by dollars across Worcester, Fall River and Lowell, plus
each town's rank-1 row on each list, less what is already resolved. The old
script printed a blank sheet to stdout, so filled cells were lost on every
re-run; the worksheet is now a committed file whose research cells survive
regeneration.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **B + 3 passed**. The worksheet holds between 46 and 52 rows: the top 50 less the 4 resolved, plus any town's list heads outside the top 50. Report the counts by town and list.

---

## Task 2: Promote only what a person verified

**Files:**
- Modify: `src/shave/occupant_worksheet.py` (append `promote`)
- Create: `scripts/promote_occupants.py`
- Test: `tests/test_occupant_worksheet.py`

**Interfaces:**
- Produces: `occupant_worksheet.promote(candidates_path, occupants_path, today: str) -> int`, returning rows appended. Raises `occupants.OccupantError` on a verified row that lacks a reviewer, a candidate name or an http(s) source.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_occupant_worksheet.py`:

```python
from shave import occupants


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ow.FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in ow.FIELDS})


def _occupants(tmp_path):
    path = tmp_path / "occupants.csv"
    path.write_text("loc_id,occupant,occupant_source,verified_on,note\n"
                    "OLD,Old Co,https://old.example/,2026-09-11,\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clean_occupant_cache():
    occupants.load.cache_clear()
    yield
    occupants.load.cache_clear()


def test_only_verified_initialled_sourced_rows_are_promoted(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [
        {"loc_id": "A", "candidate_occupant": "Acme Mills", "candidate_source": "https://acme.example/",
         "evidence": "Site lists the address.", "status": "verified", "reviewer": "PJ"},
        {"loc_id": "B", "candidate_occupant": "Beta Co", "candidate_source": "https://beta.example/",
         "status": "pending"},
        {"loc_id": "C", "candidate_occupant": "Gamma", "candidate_source": "https://g.example/",
         "status": "rejected", "reviewer": "PJ"},
        {"loc_id": "OLD", "candidate_occupant": "Old Co", "candidate_source": "https://old.example/",
         "status": "verified", "reviewer": "PJ"},
    ])
    occ = _occupants(tmp_path)

    added = ow.promote(cands, occ, today="2026-09-20")

    assert added == 1
    table = occupants.load(occ)
    assert set(table) == {"OLD", "A"}
    assert table["A"].occupant == "Acme Mills"
    assert table["A"].verified_on == "2026-09-20"
    assert "PJ" in table["A"].note and "Site lists the address." in table["A"].note


def test_a_verified_row_without_a_reviewer_is_refused(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [{"loc_id": "A", "candidate_occupant": "Acme", "candidate_source": "https://a.example/",
                    "status": "verified"}])
    occ = _occupants(tmp_path)
    before = occ.read_text(encoding="utf-8")

    with pytest.raises(occupants.OccupantError, match="reviewer"):
        ow.promote(cands, occ, today="2026-09-20")
    assert occ.read_text(encoding="utf-8") == before


def test_a_verified_row_without_a_web_source_is_refused(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [{"loc_id": "A", "candidate_occupant": "Acme", "candidate_source": "Google",
                    "status": "verified", "reviewer": "PJ"}])
    with pytest.raises(occupants.OccupantError, match="source"):
        ow.promote(cands, _occupants(tmp_path), today="2026-09-20")
```

Run: `uv run pytest tests/test_occupant_worksheet.py`
Expected: FAIL — `AttributeError: module 'shave.occupant_worksheet' has no attribute 'promote'`.

- [ ] **Step 2: Implement**

Append to `src/shave/occupant_worksheet.py`:

```python
def promote(
    candidates_path: Path | str, occupants_path: Path | str, today: str
) -> int:
    """Append every verified, initialled, sourced worksheet row to the occupant
    table. Validates everything first and writes nothing if any verified row is
    incomplete. Rows already in the table are skipped."""
    dt.date.fromisoformat(today)
    occupants_path = Path(occupants_path)
    existing = set(occupants.load(occupants_path))
    occupants.load.cache_clear()

    new_rows = []
    for row in _read(Path(candidates_path)).values():
        if row.get("status", "").strip() != "verified" or row["loc_id"] in existing:
            continue
        where = f"worksheet row {row['loc_id']}"
        if not row.get("reviewer", "").strip():
            raise occupants.OccupantError(f"{where} is verified but has no reviewer")
        if not row.get("candidate_occupant", "").strip():
            raise occupants.OccupantError(f"{where} is verified but has no candidate_occupant")
        source = row.get("candidate_source", "").strip()
        if not source.startswith(("http://", "https://")):
            raise occupants.OccupantError(f"{where} is verified but its source is not a web address: {source!r}")
        note = f"Verified by {row['reviewer'].strip()}. Evidence: {row.get('evidence', '').strip()}"
        if row.get("reviewer_note", "").strip():
            note += f" {row['reviewer_note'].strip()}"
        new_rows.append({
            "loc_id": row["loc_id"], "occupant": row["candidate_occupant"].strip(),
            "occupant_source": source, "verified_on": today, "note": note,
        })

    if new_rows:
        with occupants_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(occupants.FIELDS))
            writer.writerows(new_rows)
    occupants.load.cache_clear()
    occupants.load(occupants_path)  # the loader's own validation, on the result
    return len(new_rows)
```

Create `scripts/promote_occupants.py`:

```python
"""Move verified worksheet rows into data/occupants.csv.

    uv run python scripts/promote_occupants.py

Only rows a person marked `verified`, with a reviewer and a web source.
"""

from __future__ import annotations

import datetime as dt
import sys

from shave import occupant_worksheet, occupants


def main() -> int:
    added = occupant_worksheet.promote(
        occupant_worksheet.CANDIDATES_PATH, occupants.OCCUPANTS_PATH, today=dt.date.today().isoformat()
    )
    print(f"promoted {added} verified row(s) into {occupants.OCCUPANTS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run and commit**

```bash
uv run pytest
git add src/shave/occupant_worksheet.py scripts/promote_occupants.py tests/test_occupant_worksheet.py
git commit -m "feat: promote only rows a person verified

A worksheet row reaches data/occupants.csv only when a person has marked it
verified and initialled it, and its source is a web address. One incomplete
verified row stops the whole promotion before anything is written, and the
occupant loader's own validation runs on the result.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

Expected: **B + 6 passed**.

---

## Task 3: Draft candidates, and stop for the person

This task is research, not code. It runs in batches of 10 rows and **ends by handing the worksheet to the user**.

**Files:**
- Modify: `data/occupant_candidates.csv` (research columns only)

- [ ] **Step 1: The research protocol, for each `pending` row with an empty `candidate_occupant`**

1. **Search the address first**, with WebSearch: `"<site_addr>" <town> MA`. Look for a business whose own website, or a listing, gives **that street address**.
2. **If the owner is an LLC, trust or holding company**, also search `"<owner>" <town> MA`, and check the Massachusetts Secretary of the Commonwealth corporations search for the entity's officers or principal office.
3. **Open the strongest hit with WebFetch and confirm the address.** A name without the matching street number is not a match.
4. **Acceptable `candidate_source`**, one URL, in order of preference:
   1. the business's own page listing that address;
   2. a Secretary of the Commonwealth filing that ties the owner entity to a named operating business at the address;
   3. a commercial real-estate listing or property page naming the tenant at the address;
   4. a municipal or state record naming the occupant;
   5. a dated news article naming the occupant at the address.

   **Not acceptable:** search result pages, map pins without a page, aggregator directories that do not show the address, or anything requiring a login.
5. **Fill:**
   - `candidate_occupant`: the operating business as it trades. If the parcel is an anchor-led multi-tenant centre, name the anchor, as the committed RK Worcester Crossing row does.
   - `candidate_source`: the one URL.
   - `evidence`: one sentence saying what the page says and how it matches the address, e.g. *"Contact page gives 440 Lincoln St, Worcester; owner of record is 440 LINCOLN STREET HOLDING."*
6. **No confident match:** leave `candidate_occupant` and `candidate_source` blank, and write `evidence` as `No confident match: <what was checked>`.
7. **Owner-occupied** (the owner name is itself the operating business): fill `candidate_occupant` with the trading name and cite the business's own page, noting `owner-occupied` in `evidence`.
8. **Never touch** `status`, `reviewer` or `reviewer_note`.

- [ ] **Step 2: Work in batches, committing each**

After every 10 rows:

```bash
uv run python -c "
import csv; rows = list(csv.DictReader(open('data/occupant_candidates.csv')))
drafted = sum(1 for r in rows if r['candidate_occupant']); blank = sum(1 for r in rows if r['evidence'].startswith('No confident match'))
print(f'{drafted} drafted, {blank} no match, {len(rows) - drafted - blank} not yet researched')
bad = [r['loc_id'] for r in rows if r['status'] != 'pending']
print('rows with a status other than pending (must be empty):', bad)"
git add data/occupant_candidates.csv
git commit -m "data: occupant candidates, batch <n>

<drafted> drafted with a source, <no match> with no confident match. All pending review.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
```

The `<n>`, `<drafted>` and `<no match>` slots are filled from the printed line. The "must be empty" list must print `[]`.

- [ ] **Step 3: Hand off**

When every row is researched, stop and tell the user:
- how many rows have a candidate, and how many have no confident match;
- that `data/occupant_candidates.csv` is ready for review;
- what to do: for each row, open `candidate_source`, confirm the business trades at `site_addr`, then set `status` to `verified` or `rejected` and put their initials in `reviewer`, optionally adding a `reviewer_note`;
- that nothing reaches the site until they have done so.

**Do not continue to Task 4 until the user says the review is done.**

---

## Task 4: After review — promote, raise the ratchet, ship

**Files:**
- Modify: `data/occupants.csv` (via the promote script only)
- Modify: `tests/test_occupants.py` (`RESOLVED_TOP_50_TODAY`)
- Modify: `docs/spec-coverage.md`

- [ ] **Step 1: Promote and measure**

```bash
uv run python scripts/promote_occupants.py
uv run python -c "
import pandas as pd
from shave import ingest, occupants, pipeline, siting, towns
scored = pd.concat([pipeline.score_parcels(ingest.load_municipality(t.l3_dir, t.town_id,
          structures_path=siting.structures_path(t.town_id))) for t in towns.TOWNS], ignore_index=True)
occupants.load.cache_clear(); print(occupants.coverage(scored, top_n=50))"
```

Record `top_n_resolved`, call it **N**.

- [ ] **Step 2: Raise the ratchet to what was achieved**

In `tests/test_occupants.py`, set `RESOLVED_TOP_50_TODAY = N`.

The ratchet test uses `worcester_scored`, which covers Worcester only. It still holds because N counted across all towns is never lower than the Worcester-only count of the same table. If the test fails, it has measured the Worcester count; set the constant to that Worcester figure instead and note both in the commit message.

```bash
uv run pytest
```

- [ ] **Step 3: Update the review, commit, rebuild, deploy**

In `docs/spec-coverage.md`:
- **Stage 1 row 7:** `⚠️ **N of 50**`, or `✅` if N ≥ 40, the spec's target.
- **The pending occupants row:** remaining count `50 − N`.

```bash
git add data/occupants.csv tests/test_occupants.py docs/spec-coverage.md
git commit -m "data: N of the top 50 occupants verified and published

Promoted from data/occupant_candidates.csv: only rows a person marked verified,
initialled, with a web source. The coverage ratchet rises to N.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git checkout main && git pull --ff-only origin main
git merge --no-ff feat/occupant-worksheet -m "merge: the occupant worksheet

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01V9g2hMCXsPBJr3UQCdMCqR"
git push origin main
uv run python scripts/build_site.py
NB="$HOME/.nvm/versions/node/v22.18.0/bin"; "$NB/npx" wrangler deploy
curl -s "https://shave.pjayav.workers.dev/data/method.json?v=$(date +%s)" | uv run python -c "import json,sys; print(json.load(sys.stdin)['occupants'])"
```

Replace `N` in the commit message with the measured figure. Expected: the live `occupants` block shows `top_n_resolved` equal to N.

---

## Self-Review

**Spec coverage.**
- *"Occupant resolution for the top 50 rows"* → Tasks 1 and 3, across all covered towns, with each town's list heads added so criterion 2 holds for every list the page shows.
- *"a real, named … operating business at a verifiable address, with a checkable reason"* → the research protocol's address-match rule, one source per row, and the evidence sentence.
- *"Manual lookup is fine"* → research is assisted, and verification is manual and mandatory.

**Placeholder scan.** The `<n>`, `<drafted>`, `<no match>` and `N` slots are filled from printed output in the same step. Every code step carries its code.

**Type consistency.**
- `FIELDS` and `RESEARCH_FIELDS` are shared by `select_rows`, `write_worksheet`, `promote` and the tests.
- `promote` writes `occupants.FIELDS` columns and re-validates with `occupants.load`.
- `select_rows` needs `parcels.town_id`, from the towns plan's ingest change.

**Count arithmetic.** B → T1 +3 → T2 +3 = **B + 6**. Tasks 3–4 add no tests.

**Risk.** Agent research can be confidently wrong. The address-match rule, the single citable source and the mandatory human verification are the three defences; nothing bypasses the third.
