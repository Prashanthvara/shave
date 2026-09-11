# First Ranked List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the finished component layer into the deliverable — one command that scores every scoreable Worcester parcel and emits a ranked, confidence-tiered `ranked.json` plus the regression that tests whether the archetype layer earns its place.

**Architecture:** The components exist and are tested (859 passing). Nothing joins them. This plan adds the joining layer in six steps: correct the archetype cache (it currently picks intensity-extreme buildings and cannot answer the recharge test), close a domain hole in confidence grading, give the modelled-industrial half a sourced magnitude anchor so the 653 parcels that ComStock cannot cover become scoreable, then a pipeline, a versioned export, and the regression report. Scoring all of Worcester measured at **2.1 seconds**, so the load-duration tabulation the design specified for performance is **not built** — see Global Constraints.

**Tech Stack:** Python 3.11, numpy, pandas 3.0.5, geopandas, scipy, DuckDB 1.5.5 (`httpfs`), pytest, uv.

**Spec:** `~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md` — sections "The scoring function", "The load shape library", "Implementation Architecture", "Success Criteria". Plus `DESIGN.md` in the repo root.

**Prior plan:** `docs/superpowers/plans/2026-09-10-comstock-extractor.md` (complete; its ledger is `.superpowers/sdd/2026-09-10-comstock-extractor/progress.md`).

## Global Constraints

- Python `>=3.11`. **Do not add any new dependency.** Everything needed is in `pyproject.toml`.
- **Never restate a constant.** Import from `src/shave/assumptions.py`. A hard-coded tariff, energy or geometry number is a review rejection. New constants go *into* `assumptions.py` with a matching `Assumption(...)` row in `PUBLISHED`.
- Every new constant that a reader could dispute needs `provenance` of `FILED`, `ASSUMED` or `DERIVED` and a real `source` string. Inventing a number without a source is a review rejection.
- No per-row Python loops over parquet rows. Vectorised pandas/numpy or SQL. A loop over the ~2,100 output parcels is fine and expected.
- Every network call is read-only and anonymous. No credentials, no writes to S3.
- Tests that need the network are marked `@pytest.mark.network` and are skipped by default.
- Run the full suite with `cd /Users/pjay/powertown && uv run pytest`. It is currently **859 passing, 4 deselected**. It must still be 859 plus your new tests.
- **Do not build the load-duration tabulation** described in the spec's "Performance" section. It was written against an estimate of ~70M bisections. Measured on the real cached archetypes, the whole of Worcester scores in **2.1 s**, because the `Archetype` protocol hands the scorer 52 points per month rather than 35,040 per year. Building the tabulation would add an interpolation layer to code that is already interactive. If a later plan adds all 351 municipalities, revisit.
- pandas 3.0 traps, both already hit in this repo:
  - `date_range` returns `datetime64[us]`, **not** `[ns]`. Never read `.asi8` assuming nanoseconds. Pin with `.to_numpy(dtype="datetime64[s]")`.
  - The `str` dtype does **not** stringify NA to `"nan"`. Null checks use `.isna()`, never `.astype(str).isin([...])`.
- The Worcester L3 extract lives at `data/raw/M348_WORCESTER/L3_SHP_M348_Worcester` (note the nested directory; the town id is `348`). It is gitignored and already downloaded.
- Commit after each task. Trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU
  ```

---

## Verified facts, established by live probe on 2026-09-10

Do not re-derive these. Do verify the unit checks each task names.

**Ingest output, real Worcester data:** 2,099 scoreable parcels. `source`: 1,446 `comstock`, 653 `modeled`. `confidence`: 843 HIGH, 955 MED, 301 LOW. `assess_fy` is 2026 for every row. Exactly one parcel has `sqft == 0`; none are null.

**Archetype mix (top rows):** retail_standalone 319, auto_service 264, medium_office 233, small_office 231, warehouse 217, full_service_restaurant 159, industrial_manufacturing 115, industrial_warehouse_process 112, university 108, outpatient 81, strip_mall 70, secondary_school 67, auto_dealership 41, hospital 38, large_office 17, large_hotel 8, data_hall 6, laboratory 6, primary_school 4, small_hotel 2.

**The cached representatives today**, with peak intensity in W/sqft, from `data/interim/comstock/*.parquet`:

| archetype | bldg_id | sqft | peak kW | W/sqft | cohort |
|---|---|---|---|---|---|
| full_service_restaurant | 42679 | 5,500 | 168.1 | 30.6 | 250 |
| hospital | 131333 | 175,000 | 1391.1 | 7.9 | 2 (widened) |
| large_hotel | 43631 | 58,000 | 208.8 | 3.6 | 99 |
| large_office | 66536 | 175,000 | 529.4 | 3.0 | 154 |
| medium_office | 16635 | 46,000 | 162.2 | 3.5 | 258 |
| outpatient | 118140 | 35,000 | 214.7 | 6.1 | 79 |
| primary_school | 45535 | 35,000 | 162.3 | 4.6 | 128 |
| retail_standalone | 45566 | 10,000 | 56.7 | 5.7 | 396 |
| secondary_school | 29404 | 58,000 | 368.9 | 6.4 | 138 |
| small_hotel | 14445 | 10,000 | 48.7 | 4.9 | 37 |
| **small_office** | **94133** | **5,500** | **67.7** | **12.3** | 367 |
| strip_mall | 4945 | 21,000 | 191.6 | 9.1 | 192 |
| warehouse | 81624 | 21,000 | 37.5 | 1.8 | 279 |

`small_office` at 12.3 W/sqft is the defect Task 1 fixes. A nine-building sample of the Worcester SmallOffice cohort spanned 1.9–8.1 W/sqft with a median of 3.9; the selected building sits above the entire sampled range. It is an electric-resistance-heat winter peaker. 231 Worcester parcels — and 8 of the current top 60 by savings — inherit roughly a 3× magnitude inflation from it.

**Prototype ranking, ComStock rows only, current cache:** 585 of 1,446 clear the 50 kW floor (431 G-2, 154 G-3). 58 of the top 60 carry distinct dollar values, so the ranking *does* discriminate — but 22 rows hit the 250 kW power cap in at least one month and 3 hit it in all twelve, and `strip_mall` takes 28 of the top 60. Shaved-fraction quartiles across kept rows: 0.41 / 0.59 / 0.78. 34 rows scale more than 5× the representative's floor area, 8 more than 10×.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/shave/comstock.py` *(modify)* | gains intensity-based representative selection and an off-peak maximum on `ReducedProfile`. |
| `src/shave/archetype.py` *(modify)* | `Archetype` protocol gains `offpeak_max(month)`; `ModeledArchetype` gains a full-day shape so magnitude can be derived rather than asserted. |
| `src/shave/assumptions.py` *(modify)* | electricity-intensity anchors, modelled shape parameters, export schema version, all with sources. |
| `src/shave/crosswalk.py`, `crosswalk.csv` *(modify)* | a `multi_meter` column, so an archetype that is definitionally multi-tenant cannot be graded HIGH. |
| `src/shave/ingest.py` *(modify)* | the new predicate joins the confidence grading. |
| `src/shave/modeled.py` *(new)* | the modelled-industrial magnitude chain: intensity → implied load factor → peak kW. One file because it is one argument. |
| `src/shave/pipeline.py` *(new)* | parcels in, scored rows out. The join that does not exist today. |
| `src/shave/export.py` *(new)* | the versioned `ranked.json` contract and the templated reason sentence. |
| `src/shave/regression.py` *(new)* | the two R² figures and the declared threshold. |
| `scripts/run_pipeline.py` *(new)* | the one command. |

---

## Execution: dispatching to muse spark through a subagent wrapper

Per standing user instruction, implementation goes to **`opencode/muse-spark-1.3-contributor-free`** and to no other model.

### Why a wrapper, and not a `model:` field

A Claude Code subagent is a Markdown file under `.claude/agents/` whose frontmatter carries `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills` and others ([docs](https://code.claude.com/docs/en/sub-agents)). The `model` field accepts **only** Claude models — `sonnet`, `opus`, `haiku`, `fable`, a full ID like `claude-opus-5`, or `inherit`. There is no field that points a subagent's inference at an external provider.

So muse spark cannot *be* a subagent. It can be **driven by** one: a Claude subagent restricted to `Bash` whose entire job is to shell out to `opencode run`, verify what came back, and report. The Claude half is a dispatcher on Haiku; every line of code is still written by muse spark, which is what the standing instruction requires.

| Agent | File | Model | Role |
|---|---|---|---|
| `muse-spark-implementer` | `.claude/agents/muse-spark-implementer.md` | `haiku` | Runs one task brief through muse spark; verifies commit + clean tree + pytest count; relays deviations verbatim. |
| `muse-spark-reviewer` | `.claude/agents/muse-spark-reviewer.md` | `haiku` | Runs the fresh-eyes review of one task's diff through muse spark; relays findings unedited. |

**The load-bearing constraint in both prompts: the wrapper never writes the task's code itself.** If muse spark returns nothing, the wrapper reports the failure and stops. A Haiku wrapper that quietly finishes the job produces a commit attributed to a model that never saw the code and makes the ledger a fiction.

Dispatch, one task per call:

```
Agent(subagent_type: "muse-spark-implementer",
      prompt: "BRIEF=.superpowers/sdd/2026-09-10-first-ranked-list/task-N-brief.md
               EXPECTED_TESTS=<count from the task>
               REPO=/Users/pjay/powertown")
```

### Executor status — RE-PROBED 2026-09-11 09:38, AND IT DOES NOT WORK

The paragraph this section replaces claimed muse spark was "re-verified on 2026-09-10 at 21:36, and it works." **That no longer holds.** Three probes today:

| Probe | Result |
|---|---|
| `"Reply with exactly one word: pong"`, no tools needed | **8.4 s, exit 0, correct output.** The model and the credential are alive. |
| Write `hello.py`, run it, report output — empty scratch dir, `--auto`, `--dir` set | **Hung. Killed at 180 s (exit 124). Zero bytes on stdout and stderr. No file written.** 4.67 s of user CPU across 3 minutes of wall clock — it was idle, not working. |
| Write `hello.txt` — same, plus `--print-logs --log-level ERROR` | **Hung. Killed at 100 s. Still zero bytes on both streams**, so it stalls before emitting even an error log. |

This reproduces ruling 6 in the comstock-extractor ledger exactly: **fine on pure-text replies, silent indefinite stall on anything requiring a tool call.** `--auto` does not fix it, so it is not the permission prompt that was suspected.

**Consequence for this plan.** The wrapper agents are built and correct, but the executor behind them is non-functional for implementation work as of this probe. Do not dispatch Task 1 on the assumption it will run. Re-probe with the trivial write task first; that probe costs 30 seconds and is the whole gate:

```bash
cd /tmp && mkdir -p ms-probe && timeout 120 opencode run --dir /tmp/ms-probe --auto \
  -m opencode/muse-spark-1.3-contributor-free \
  "Create a file hello.txt containing the word ok. Nothing else." ; ls -la /tmp/ms-probe
```

If `hello.txt` exists, the executor is back and the wrapper dispatch above is live. If it hangs, **the standing instruction and a working executor are in conflict, and that is a decision for the user, not a ruling for the controller** — the options are to wait, to have the controller implement in-session and record every task as a weaker gate, or to lift the model restriction. Do not silently substitute another model.

### Verification discipline, mandatory after every dispatch

The wrapper does this, but the controller re-checks it. Muse spark's failure signature is **exit 0 (or 124) with zero bytes on both streams and nothing written**. Never trust the exit code:

```bash
git -C /Users/pjay/powertown log --oneline -3
git -C /Users/pjay/powertown status --short
cd /Users/pjay/powertown && uv run pytest
```

A task is done when the commit exists **and** the suite count matches the task's stated expectation. If a dispatch returns empty, re-dispatch once with the brief split in half; if that fails, escalate per the conflict above rather than papering over it.

---

## Task 1: Rebuild the archetype cache correctly

Two changes that share a schema, a cache file and a warm run, so they ship together: the representative is selected on median **peak intensity** instead of median floor area, and `ReducedProfile` carries the off-peak maximum the recharge test needs and cannot currently get.

**Files:**
- Modify: `src/shave/comstock.py` — `ReducedProfile`, `reduce_from_frame`, `select_representative`, `build_archetype`
- Modify: `src/shave/archetype.py:51-66` — add `offpeak_max` to the `Archetype` protocol
- Modify: `scripts/warm_comstock_cache.py`
- Test: `tests/test_comstock.py`

**Interfaces:**
- Consumes: `billing_window.billed_mask`, `assumptions.PEAK_HOUR_START`, `assumptions.PEAK_HOUR_END`, `assumptions.INTERVAL_MINUTES`.
- Produces:
  - `ReducedProfile.offpeak_max_kw: np.ndarray` shape `(12,)`
  - `ComStockArchetype.offpeak_max(month: int) -> float`
  - `select_representative(index, building_type, min_cohort=MIN_COHORT, sample_size=INTENSITY_SAMPLE, read_profile=None) -> Representative`
  - `Representative.peak_intensity_w_per_sqft: float`
  - `INTENSITY_SAMPLE: int = 15`

- [ ] **Step 1: Write the failing test for the off-peak maximum**

Add to `tests/test_comstock.py`:

```python
def test_reduce_captures_the_overnight_maximum():
    """The recharge test needs the off-peak load, which the billed mask drops."""
    index = pd.date_range("2018-01-01", "2018-12-31 23:45", freq="15min")
    kw = np.full(index.size, 10.0)
    # A 300 kW spike at 03:00 on 8 March: outside the billed window, so it must
    # not reach monthly_peak_kw, and must reach offpeak_max_kw for March.
    night = (index.month == 3) & (index.day == 8) & (index.hour == 3)
    kw[night] = 300.0
    raw = pd.DataFrame({
        "timestamp": index,
        comstock.TOTAL_ELECTRICITY_COL: kw / comstock.KWH_PER_INTERVAL_TO_KW,
    })

    profile = comstock.reduce_from_frame(1, raw, sqft=1000.0)

    assert profile.offpeak_max_kw.shape == (12,)
    assert profile.offpeak_max_kw[2] == pytest.approx(300.0)
    assert profile.monthly_peak_kw[2] == pytest.approx(10.0)
    # Every other month sees only the flat 10 kW overnight.
    assert profile.offpeak_max_kw[0] == pytest.approx(10.0)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_comstock.py::test_reduce_captures_the_overnight_maximum -v`
Expected: FAIL with `AttributeError: 'ReducedProfile' object has no attribute 'offpeak_max_kw'`

- [ ] **Step 3: Add the off-peak window helper to `billing_window.py`**

The overnight recharge window is the tariff's peak period inverted on the clock: 21:00 to 08:00, any day. It is needed by two modules, so it is one function, matching the repo's "the billing window is one function, not five" rule.

Append to `src/shave/billing_window.py`:

```python
#: Hours available to recharge: 21:00 to 08:00 the next morning.
OFFPEAK_HOURS = PEAK_HOUR_START + 24 - PEAK_HOUR_END


def offpeak_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """True where an interval falls in the overnight recharge window.

    Any day of the week. This is a clock test, not a tariff test: the tariff
    has nothing to say about when a battery may charge, only about which
    demand it bills. Weekend daytime is deliberately excluded — charging then
    is possible but it is not the 11-hour window the recharge test reasons
    about, and including it would let a weekend peak veto a weekday recharge.
    """
    hour = index.hour.to_numpy()
    return (hour >= PEAK_HOUR_END) | (hour < PEAK_HOUR_START)
```

- [ ] **Step 4: Carry `offpeak_max_kw` through `ReducedProfile`**

In `src/shave/comstock.py`, add the field, defaulting to zeros so an older cache file still loads:

```python
@dataclass(frozen=True)
class ReducedProfile:
    bldg_id: int
    monthly_peak_kw: np.ndarray   # (12,)
    windows: np.ndarray           # (12, INTERVALS_PER_BILLED_DAY)
    sqft: float | None = None
    widened: bool = False
    cohort_size: int | None = None
    #: Highest load seen in the 21:00-08:00 recharge window, per month. The
    #: recharge headroom test reads this; without it the test can only be
    #: stubbed, which is how a silently-passing predicate gets shipped.
    offpeak_max_kw: np.ndarray = field(
        default_factory=lambda: np.zeros(12, dtype=float)
    )
```

Add `from dataclasses import dataclass, field, replace` to the imports if `field` is not already there.

In `to_frame`, add the column:

```python
            "offpeak_max_kw": self.offpeak_max_kw,
```

In `from_frame`, read it with the same explicit column-presence defaulting the existing `widened` branch uses — and note the caution comment already in that method applies here:

```python
        if "offpeak_max_kw" in df.columns:
            offpeak = df["offpeak_max_kw"].to_numpy(dtype=float)
        else:
            offpeak = np.zeros(12, dtype=float)
```

and pass `offpeak_max_kw=offpeak` to the constructor.

- [ ] **Step 5: Compute it in `reduce_from_frame`**

`reduce_from_frame` currently masks to billed intervals as its first act, which throws the overnight data away. Compute the off-peak maximum *before* that mask. Insert immediately after `kw` is built and before `keep = billed_mask(ts)`:

```python
    # Off-peak maximum per month, computed BEFORE the billed mask drops the
    # overnight data. Vectorised: np.maximum.at over a month index, no loop.
    offpeak_max = np.zeros(12, dtype=float)
    night = offpeak_mask(ts)
    if night.any():
        np.maximum.at(offpeak_max, ts.month.to_numpy()[night] - 1, kw[night])
```

Import `offpeak_mask` alongside the existing `billed_mask` import. Then pass it through the return:

```python
    return ReducedProfile(int(bldg_id), peaks, windows, sqft, offpeak_max_kw=offpeak_max)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_comstock.py::test_reduce_captures_the_overnight_maximum -v`
Expected: PASS

- [ ] **Step 7: Write the failing test for intensity-based selection**

```python
def test_representative_is_the_median_by_peak_intensity_not_by_size():
    """Median floor area picks a typical-sized building that can be an
    intensity outlier. Worcester's SmallOffice pick sat at 12.3 W/sqft against
    a cohort median of 3.9 — a 3x magnitude inflation on 231 parcels."""
    index = pd.DataFrame({
        "bldg_id": [1, 2, 3],
        "building_type": ["SmallOffice"] * 3,
        "sqft": [1_000.0, 2_000.0, 3_000.0],
    })
    # Building 2 is the median by SIZE but the extreme by INTENSITY.
    intensities = {1: 3.0, 2: 12.0, 3: 5.0}

    def fake_read(bldg_id, conn=None, sqft=None):
        peak = intensities[bldg_id] * sqft / 1000.0  # W/sqft -> kW
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, peak),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    rep = comstock.select_representative(
        index, "SmallOffice", min_cohort=1, read_profile=fake_read
    )

    assert rep.bldg_id == 3, "median intensity is 5.0 W/sqft, which is building 3"
    assert rep.peak_intensity_w_per_sqft == pytest.approx(5.0)


def test_representative_sampling_spans_the_size_range():
    """A sample drawn off one end of the size range is not a cohort median."""
    n = 100
    index = pd.DataFrame({
        "bldg_id": list(range(n)),
        "building_type": ["Warehouse"] * n,
        "sqft": [1_000.0 * (i + 1) for i in range(n)],
    })
    seen: list[int] = []

    def fake_read(bldg_id, conn=None, sqft=None):
        seen.append(bldg_id)
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, 1.0),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    comstock.select_representative(
        index, "Warehouse", min_cohort=1, sample_size=5, read_profile=fake_read
    )

    assert len(seen) == 5
    assert min(seen) < n // 4, "sample must reach the small end"
    assert max(seen) > 3 * n // 4, "sample must reach the large end"


def test_representative_sample_larger_than_cohort_reads_every_building():
    index = pd.DataFrame({
        "bldg_id": [7, 8],
        "building_type": ["Hospital"] * 2,
        "sqft": [100_000.0, 200_000.0],
    })
    seen: list[int] = []

    def fake_read(bldg_id, conn=None, sqft=None):
        seen.append(bldg_id)
        return comstock.ReducedProfile(
            bldg_id=bldg_id,
            monthly_peak_kw=np.full(12, 2.0),
            windows=np.zeros((12, comstock.INTERVALS_PER_BILLED_DAY)),
            sqft=sqft,
        )

    rep = comstock.select_representative(
        index, "Hospital", min_cohort=30, sample_size=15, read_profile=fake_read
    )

    assert sorted(seen) == [7, 8]
    assert rep.widened is True, "a 2-building cohort is still thin"
    assert rep.cohort_size == 2
```

- [ ] **Step 8: Run them to verify they fail**

Run: `uv run pytest tests/test_comstock.py -k representative -v`
Expected: FAIL — `select_representative() got an unexpected keyword argument 'read_profile'`

- [ ] **Step 9: Rewrite `select_representative`**

Replace the existing function in `src/shave/comstock.py`:

```python
#: How many buildings of a type to actually read before picking the median.
#: The full Worcester County cohort runs to 396 for RetailStandalone; reading
#: every one to rank it by intensity costs 13 x 396 S3 round trips for a
#: quantity that a spread sample estimates well. 15 is 195 reads across all
#: thirteen types, roughly six minutes on a one-time warm run.
INTENSITY_SAMPLE = 15


@dataclass(frozen=True)
class Representative:
    bldg_id: int
    building_type: str
    sqft: float
    cohort_size: int
    widened: bool
    peak_intensity_w_per_sqft: float = 0.0


def select_representative(
    index: pd.DataFrame,
    building_type: str,
    min_cohort: int = MIN_COHORT,
    sample_size: int = INTENSITY_SAMPLE,
    read_profile: Callable[..., "ReducedProfile"] | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> Representative:
    """The median-PEAK-INTENSITY building of its type, as that type's shape.

    The spec asks for the building whose annual load factor is the median of
    its cohort. Reading every building's timeseries to rank the whole cohort
    costs thousands of S3 round trips, so this samples `sample_size` buildings
    spread evenly across the cohort's floor-area range, reads those, and takes
    the median of the sample by peak intensity in W/sqft.

    This replaces median-floor-area selection, which chose a building that was
    typical in size and could be extreme in intensity. In Worcester it picked a
    SmallOffice at 12.3 W/sqft against a cohort median near 3.9, inflating the
    magnitude of 231 parcels roughly threefold.

    Ties and even samples take the lower middle rather than interpolating, so
    the result is always a real building that can be cited by id.
    """
    cohort = index[index["building_type"] == building_type]
    if cohort.empty:
        raise ComStockError(
            f"no ComStock buildings of type {building_type!r} in this index"
        )

    read = read_profile or reduce_timeseries
    ordered = cohort.sort_values(["sqft", "bldg_id"], kind="stable").reset_index(drop=True)

    # Evenly spaced positions across the size range, endpoints included, so the
    # sample cannot sit on one end of the cohort.
    take = min(sample_size, len(ordered))
    positions = np.unique(np.linspace(0, len(ordered) - 1, take).round().astype(int))
    sample = ordered.iloc[positions]

    measured: list[tuple[float, int, float]] = []
    for row in sample.itertuples(index=False):
        sqft = float(row.sqft)
        if sqft <= 0:
            continue
        profile = read(int(row.bldg_id), conn=conn, sqft=sqft)
        intensity = float(profile.monthly_peak_kw.max()) * 1000.0 / sqft
        measured.append((intensity, int(row.bldg_id), sqft))

    if not measured:
        raise ComStockError(
            f"no {building_type!r} building in the sample has a usable floor area"
        )

    measured.sort()
    intensity, bldg_id, sqft = measured[(len(measured) - 1) // 2]

    return Representative(
        bldg_id=bldg_id,
        building_type=building_type,
        sqft=sqft,
        cohort_size=len(ordered),
        widened=len(ordered) < min_cohort,
        peak_intensity_w_per_sqft=intensity,
    )
```

Add `from collections.abc import Callable` to the imports.

- [ ] **Step 10: Reuse the sample's read in `build_archetype`**

`build_archetype` currently calls `select_representative` and then `reduce_timeseries` on the winner, which reads the winning building twice. Keep it — the second read is one round trip out of 196 and the alternative couples selection to reduction. But it must now pass the connection through so the sample reads share one DuckDB session. In `build_archetype`, change the selection call to:

```python
            rep = select_representative(
                index, ARCHETYPE_TO_COMSTOCK[archetype_name], conn=conn
            )
```

- [ ] **Step 11: Give `ComStockArchetype` the off-peak accessor and extend the protocol**

In `src/shave/comstock.py`, add to `ComStockArchetype`:

```python
    def offpeak_max(self, month: int) -> float:
        """Highest 21:00-08:00 load in this month, scaled to the parcel."""
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        return float(self.profile.offpeak_max_kw[month - 1] * self._scale)
```

In `src/shave/archetype.py`, add to the `Archetype` protocol, after `peak_day_window`:

```python
    def offpeak_max(self, month: int) -> float:
        """Highest load in the 21:00-08:00 recharge window, in kW.

        `month` is 1-12. The recharge headroom test reads this.
        """
        ...
```

Add the same method to `FixtureArchetype`, backed by a new field so a test can pin it:

```python
    offpeak_max_kw: np.ndarray | None = None
```

in `__post_init__`, after the existing shape checks:

```python
        if self.offpeak_max_kw is None:
            self.offpeak_max_kw = np.zeros(12, dtype=float)
        else:
            self.offpeak_max_kw = np.asarray(self.offpeak_max_kw, dtype=float)
        if self.offpeak_max_kw.shape != (12,):
            raise ValueError("offpeak_max_kw must have shape (12,)")
```

and the accessor:

```python
    def offpeak_max(self, month: int) -> float:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        return float(self.offpeak_max_kw[month - 1])
```

- [ ] **Step 12: Test the protocol is still satisfied by both implementations**

Add to `tests/test_comstock.py`:

```python
def test_comstock_archetype_still_satisfies_the_protocol():
    profile = comstock.ReducedProfile(
        bldg_id=1,
        monthly_peak_kw=np.full(12, 50.0),
        windows=np.full((12, comstock.INTERVALS_PER_BILLED_DAY), 40.0),
        sqft=10_000.0,
        offpeak_max_kw=np.full(12, 12.0),
    )
    arch = comstock.ComStockArchetype(profile=profile, sqft=20_000.0)

    assert isinstance(arch, Archetype)
    assert arch.offpeak_max(1) == pytest.approx(24.0), "scales with the parcel"
    with pytest.raises(ValueError):
        arch.offpeak_max(13)
```

`Archetype` is imported from `shave.archetype`; add the import if `tests/test_comstock.py` does not already have it.

- [ ] **Step 13: Run the whole suite**

Run: `uv run pytest`
Expected: PASS, 859 + your new tests (7 new here), 4 deselected.

- [ ] **Step 14: Re-warm the cache against live data**

The cached parquet files are stale twice over: wrong representative, and no `offpeak_max_kw` column. Delete and rebuild.

Run:
```bash
rm -rf data/interim/comstock
uv run python scripts/warm_comstock_cache.py
```
Expected: about six minutes (195 S3 reads), thirteen parquet files written.

Then print the new table and **paste it into the task report** — it is the evidence the defect is fixed:

```bash
uv run python -c "
import glob, os, pandas as pd
for p in sorted(glob.glob('data/interim/comstock/*.parquet')):
    df = pd.read_parquet(p); r = df.iloc[0]
    peak = df['monthly_peak_kw'].max(); sqft = r['sqft']
    print(f\"{os.path.basename(p).split('__')[0]:28s} bldg={int(r['bldg_id']):7d} \"
          f\"sqft={sqft:9.0f} W/sqft={peak*1000/sqft:6.1f} offpeak_max={df['offpeak_max_kw'].max():8.1f}\")
"
```

**Pass condition, declared in advance:** `small_office` must land below 8.0 W/sqft, inside the 1.9–8.1 sampled cohort range. Every archetype's `offpeak_max` must be strictly greater than zero — a zero means the column did not populate, since no real commercial building draws nothing overnight.

- [ ] **Step 15: Commit**

```bash
git add src/shave/comstock.py src/shave/archetype.py src/shave/billing_window.py \
        scripts/warm_comstock_cache.py tests/test_comstock.py
git commit -m "fix: select representatives by peak intensity, and carry off-peak load

Median floor area picked buildings typical in size and extreme in intensity.
Worcester's SmallOffice pick sat at 12.3 W/sqft against a cohort median near
3.9, inflating 231 parcels roughly threefold. Sample fifteen buildings across
the size range and take the median of the sample by peak intensity.

ReducedProfile now carries the 21:00-08:00 maximum per month, so the recharge
headroom predicate reads real data instead of being stubbed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Task 2: An archetype that is definitionally multi-metered cannot be HIGH

`strip_mall` takes 28 of the top 60 rows in the prototype ranking. A strip mall is, by definition, many service accounts with non-coincident peaks; the spec names this as the failure mode that "systematically overstates large buildings." The five existing predicates do not catch it, because a strip mall owned by one LLC under one assessor record passes `single_owner` and `single_record` cleanly. The fix is a domain judgment recorded in the crosswalk, which is where this project's domain judgments live.

**Files:**
- Modify: `src/shave/crosswalk.csv` — new `multi_meter` column
- Modify: `src/shave/crosswalk.py` — `CrosswalkRow`, `load`, `_validate_row`
- Modify: `src/shave/ingest.py` — `_crosswalk_frame`, `PREDICATES`, `_apply_confidence`
- Test: `tests/test_crosswalk.py`, `tests/test_ingest.py`

**Interfaces:**
- Consumes: `crosswalk.CrosswalkRow` from Task 0 of the prior plan.
- Produces: `CrosswalkRow.multi_meter: bool`; an ingest output column `multi_meter: bool`; a new predicate name `"single_meter_archetype"` in `ingest.PREDICATES`.

- [ ] **Step 1: Write the failing crosswalk test**

Add to `tests/test_crosswalk.py`:

```python
def test_strip_mall_rows_are_flagged_multi_meter():
    """A strip mall is many service accounts. Demand bills per account, so a
    parcel-level estimate for one is an aggregate nobody is billed for."""
    rows = crosswalk.load()
    strip = [r for r in rows.values() if r.archetype == "strip_mall"]
    assert strip, "the crosswalk must still map something to strip_mall"
    assert all(r.multi_meter for r in strip)


def test_single_occupant_archetypes_are_not_flagged():
    rows = crosswalk.load()
    assert not rows["3050"].multi_meter, "a private hospital is one account"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_crosswalk.py -k multi_meter -v`
Expected: FAIL with `AttributeError: 'CrosswalkRow' object has no attribute 'multi_meter'`

- [ ] **Step 3: Add the column to the CSV**

Append `multi_meter` as the last header field in `src/shave/crosswalk.csv`, so the header becomes:

```
use_code,use_desc,archetype,source,icp_sector,confidence,note,multi_meter
```

Set the value to `1` for every row whose `archetype` is `strip_mall`, and for any row whose `use_desc` describes a multi-occupant building — read every row and decide; the candidates are the strip-mall, shopping-centre, multi-tenant-office and mixed-use descriptions. Set `0` everywhere else. **Do not set it on `retail_standalone`, `warehouse` or `industrial_manufacturing`:** those are single-occupant by definition and flagging them would turn the predicate into a blanket penalty.

- [ ] **Step 4: Read the column in `crosswalk.py`**

Add to `CrosswalkRow`:

```python
    #: True when this use code describes a building with more than one service
    #: account. Demand charges accrue to an account, not a building, so a
    #: parcel-level estimate for such a building is an aggregate that nobody is
    #: billed for — and it is always an overstatement, never an understatement.
    multi_meter: bool = False
```

In `load`, parse it with the same defaulting discipline the file uses elsewhere:

```python
            multi_meter=str(raw.get("multi_meter", "") or "0").strip() in {"1", "true", "True"},
```

In `_validate_row`, reject a value that is neither blank nor recognisable — a typo must not silently read as False:

```python
    raw_flag = str(row_source.get("multi_meter", "") or "0").strip()
    if raw_flag not in {"", "0", "1", "true", "True", "false", "False"}:
        raise CrosswalkError(f"{where} multi_meter must be 0 or 1, got {raw_flag!r}")
```

Place this check where the raw dict is still in scope; if `_validate_row` only receives the parsed `CrosswalkRow`, do the check inline in `load` instead, raising the same `CrosswalkError`.

- [ ] **Step 5: Run the crosswalk tests**

Run: `uv run pytest tests/test_crosswalk.py -v`
Expected: PASS, including the two new tests.

- [ ] **Step 6: Write the failing ingest test**

Add to `tests/test_ingest.py`:

```python
def test_multi_meter_archetype_cannot_be_graded_high():
    """Every other predicate holds; the archetype alone caps the row at MED."""
    parcels = pd.DataFrame({
        "sqft": [20_000.0],
        "unique_archetype": [True],
        "record_count": [1],
        "owner_count": [1],
        "collapse_point": [False],
        "multi_meter": [True],
    })

    graded = ingest._apply_confidence(parcels)

    assert graded["confidence"].iloc[0] == "MED"
    assert "single_meter_archetype" in graded["confidence_reasons"].iloc[0]


def test_single_meter_archetype_still_reaches_high():
    parcels = pd.DataFrame({
        "sqft": [20_000.0],
        "unique_archetype": [True],
        "record_count": [1],
        "owner_count": [1],
        "collapse_point": [False],
        "multi_meter": [False],
    })

    assert ingest._apply_confidence(parcels)["confidence"].iloc[0] == "HIGH"
```

- [ ] **Step 7: Run it to verify it fails**

Run: `uv run pytest tests/test_ingest.py -k multi_meter -v`
Expected: FAIL — the row grades HIGH because the predicate does not exist.

- [ ] **Step 8: Add the predicate**

In `src/shave/ingest.py`, extend `PREDICATES` — order matters, it is report order:

```python
PREDICATES: tuple[str, ...] = (
    "unique_archetype",          # the use code maps 1:1 to one archetype
    "has_floor_area",            # BLD_AREA present and non-zero
    "single_record",             # exactly one Assess record at this LOC_ID
    "single_owner",              # one owner of record
    "within_single_meter_cap",   # BLD_AREA <= LIKELY_SINGLE_METERED_MAX_SQFT
    "single_meter_archetype",    # the use code is not definitionally multi-tenant
)
```

In `_apply_confidence`, add the entry to the `holds` frame, after `within_single_meter_cap`:

```python
            "single_meter_archetype": ~parcels["multi_meter"]
            .fillna(False)
            .astype(bool)
            .to_numpy(),
```

Add `"multi_meter"` to `OUTPUT_COLUMNS`, and carry it out of `_crosswalk_frame` alongside `archetype`, `source`, `icp_sector` and `collapse_point`, exactly as those are carried.

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest`
Expected: PASS. Some existing ingest tests build parcel frames without a `multi_meter` column; the `.fillna(False)` above handles a missing value but **not a missing column**. If a test fails with `KeyError: 'multi_meter'`, fix it in `_apply_confidence` by reading defensively:

```python
    multi_meter = (
        parcels["multi_meter"] if "multi_meter" in parcels
        else pd.Series(False, index=parcels.index)
    )
```

and use `~multi_meter.fillna(False).astype(bool).to_numpy()`. Do not edit the existing tests to add the column.

- [ ] **Step 10: Measure the effect on real data**

Run:
```bash
uv run python -c "
from shave import ingest
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
print('confidence:', g['confidence'].value_counts().to_dict())
print('multi_meter rows:', int(g['multi_meter'].sum()))
print('strip_mall at HIGH:', int(((g.archetype=='strip_mall') & (g.confidence=='HIGH')).sum()))
"
```
**Pass condition:** `strip_mall at HIGH` is 0. The previous baseline was 843 HIGH / 955 MED / 301 LOW; HIGH must fall and MED must rise by the same amount.

- [ ] **Step 11: Commit**

```bash
git add src/shave/crosswalk.py src/shave/crosswalk.csv src/shave/ingest.py \
        tests/test_crosswalk.py tests/test_ingest.py
git commit -m "feat: a definitionally multi-metered archetype cannot grade HIGH

A strip mall is many service accounts with non-coincident peaks. Demand bills
per account, so a parcel-level estimate for one is an aggregate nobody is
billed for, and it overstates in one direction only. The five existing
predicates missed it: one LLC, one assessor record, both pass.

Recorded in the crosswalk, which is where this project's domain judgments live.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Task 3: The modelled-industrial magnitude chain

653 of 2,099 Worcester parcels — 31%, including every machine shop, metal fabricator and cold store in the published ICP — carry `source == "modeled"` and cannot be scored at all today. `ModeledArchetype` can make a *shape*; nothing gives it a *magnitude*. This task supplies the magnitude from published intensity data and derives the load factor from the shape rather than asserting it, so the chain the spec asked to be stated explicitly is stated in code.

**The chain, three steps and two published inputs:**

```
annual_kwh        = intensity_kwh_per_sqft_yr x sqft          # CBECS / MECS
implied_LF        = annual_energy(shape) / (8760 x peak(shape))  # from the shape itself
peak_kw           = annual_kwh / 8760 / implied_LF
```

The load factor is **derived, not assumed**. That closes the gap the spec flagged as "two assumptions deep": only the intensity and the shape parameters are inputs, and the shape parameters are declared with their reasoning.

**Files:**
- Modify: `src/shave/assumptions.py` — intensity anchors and their `PUBLISHED` rows
- Modify: `src/shave/archetype.py` — factor the shape so one function serves both the billed window and the full day; add `offpeak_max`
- Create: `src/shave/modeled.py`
- Test: `tests/test_modeled.py` (new), `tests/test_archetype.py` *(create if absent; otherwise extend)*

**Interfaces:**
- Consumes: `archetype.ModeledArchetype`, `archetype.MA_COOLING_SHAPE`, `crosswalk.MODELED_TYPES`, `assumptions.Assumption`.
- Produces:
  - `assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR: dict[str, float]`
  - `assumptions.UNANCHORED_ARCHETYPES: frozenset[str]`
  - `modeled.SHAPE_PARAMS: dict[str, dict[str, float | bool]]`
  - `modeled.full_day_shape(params, day_type, month) -> np.ndarray` shape `(96,)`
  - `modeled.implied_load_factor(params, year=2018) -> float`
  - `modeled.peak_kw_for(archetype_name, sqft) -> float`
  - `modeled.build_modeled_archetype(archetype_name, parcel_id, sqft) -> ModeledArchetype`
  - `modeled.ModeledMagnitudeError(ValueError)`

- [ ] **Step 1: Add the intensity anchors to `assumptions.py`**

These are published figures, read from the source tables on 2026-09-10. The `Per square foot (kWh)` column of CBECS 2018 Table C22 is the mean site electricity intensity; MECS figures are derived by dividing Table 3.2 net electricity by Table 9.1 enclosed floorspace, with 3,412 Btu/kWh.

Append to `src/shave/assumptions.py`:

```python
# --------------------------------------------------------------------------
# Electricity intensity anchors for the modelled half of the library.
#
# ComStock models 14 commercial building types and explicitly excludes
# laboratories, data centers, movie theatres and ice rinks; it models no
# industry at all. For everything it does not cover, magnitude comes from
# published intensity and shape comes from the parameters in modeled.py.
# Shape and magnitude are deliberately sourced separately: the industrial
# shape literature is non-US, so its shapes transfer and its magnitudes
# do not.
#
# CBECS 2018 Table C22, "Electricity consumption totals and conditional
#   intensities by building activity subcategories":
#   eia.gov/consumption/commercial/data/2018/ce/pdf/c22.pdf
# MECS 2018 Table 3.2 (fuel consumption, trillion Btu) and Table 9.1
#   (enclosed floorspace, million sq ft):
#   eia.gov/consumption/manufacturing/data/2018/pdf/Table3_2.pdf
#   eia.gov/consumption/manufacturing/data/2018/pdf/Table9_1.pdf
# --------------------------------------------------------------------------

BTU_PER_KWH = 3412.0

ELECTRIC_INTENSITY_KWH_PER_SQFT_YR: dict[str, float] = {
    # MECS NAICS 332 Fabricated Metal Products: 124 trillion Btu net
    # electricity over 1,530 million sq ft = 23.8. NAICS 333 Machinery:
    # 80 over 1,021 = 23.0. Worcester's machine shops and metal fabricators
    # are 332/333; the mean of the two is the anchor.
    "industrial_manufacturing": 23.4,
    # CBECS C22 "Refrigerated" warehouse, mean 29.6 kWh/sq ft. Cold storage
    # is the ICP sector this stands in for.
    "industrial_warehouse_process": 29.6,
    # CBECS C22 "Laboratory", mean 32.1 kWh/sq ft.
    "laboratory": 32.1,
    # CBECS C22 "Recreation", mean 13.0 kWh/sq ft. A weak proxy: CBECS has no
    # ice-rink category and a sheet of ice is nothing like a gymnasium. Named
    # as the weakest anchor on the method page.
    "ice_rink": 13.0,
    # CBECS C22 "Vehicle service or repair", mean 6.1 kWh/sq ft.
    "auto_service": 6.1,
    # CBECS C22 "Other retail", mean 15.2 kWh/sq ft. A dealership is showroom
    # plus service bay; "Other retail" is the closest published activity.
    "auto_dealership": 15.2,
    # CBECS C22 "College or university", mean 12.6 kWh/sq ft.
    "university": 12.6,
}

#: Modelled archetypes with no defensible published intensity. Rows carrying
#: these are exported UNSCORED with this named reason rather than given an
#: invented number. CBECS has no data-center activity category, and the
#: published per-square-foot figures for data halls vary by more than an
#: order of magnitude with rack density, which is not in the assessor record.
#: Six Worcester parcels. Data centers are also absent from Powertown's
#: published ICP, so the cost of not scoring them is close to zero.
UNANCHORED_ARCHETYPES: frozenset[str] = frozenset({"data_hall"})
```

Add matching `PUBLISHED` rows, one per anchor, so the method page renders them. Follow the existing style exactly:

```python
    Assumption(
        "intensity_industrial_manufacturing",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_manufacturing"],
        "kWh/sq ft/yr", "FILED", "EIA MECS 2018 Tables 3.2 and 9.1",
        "Mean of NAICS 332 Fabricated Metal Products (23.8) and NAICS 333 "
        "Machinery (23.0), the two subsectors Worcester's machine shops and "
        "metal fabricators sit in.",
    ),
```

Write one such row for each of the seven anchors. For `ice_rink` set the `note` to name it as the weakest anchor in the table. For `industrial_warehouse_process`, `laboratory`, `auto_service`, `auto_dealership` and `university` the `source` is `"EIA CBECS 2018 Table C22"`.

- [ ] **Step 2: Write the failing test for the shape refactor**

`ModeledArchetype._day_shape` hard-codes the billed window's 52 points. The magnitude chain needs the same shape over a full 24 hours. One function must serve both, or the two will drift.

Create `tests/test_modeled.py`:

```python
import numpy as np
import pytest

from shave import modeled
from shave.archetype import INTERVALS_PER_BILLED_DAY, ModeledArchetype
from shave.assumptions import (
    ELECTRIC_INTENSITY_KWH_PER_SQFT_YR,
    PEAK_HOUR_END,
    PEAK_HOUR_START,
    UNANCHORED_ARCHETYPES,
)


def test_full_day_shape_agrees_with_the_billed_window():
    """One shape function, two views. If these drift, every modelled magnitude
    is computed against a shape the scorer never sees."""
    params = modeled.SHAPE_PARAMS["industrial_manufacturing"]
    full = modeled.full_day_shape(params, "weekday", 6)

    assert full.shape == (96,)

    arch = ModeledArchetype(parcel_id="x", peak_kw=1.0, **modeled.archetype_kwargs(params))
    window = arch._day_shape("weekday", 6)

    start = PEAK_HOUR_START * 4
    end = PEAK_HOUR_END * 4
    assert end - start == INTERVALS_PER_BILLED_DAY
    np.testing.assert_allclose(full[start:end], window, rtol=1e-12)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_modeled.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.modeled'`

- [ ] **Step 4: Factor `_day_shape` to take an hours array**

In `src/shave/archetype.py`, change `ModeledArchetype._day_shape` so the hour grid is a parameter with the billed window as its default. The body is unchanged apart from the substitution and the jitter, which must still roll by whole intervals:

```python
    def _day_shape(self, day_type: str, month: int, hours: np.ndarray | None = None) -> np.ndarray:
        """Normalised 0-1 load across `hours` for one day type.

        `hours` defaults to the billed window. `modeled.full_day_shape` passes
        a 24-hour grid so the magnitude chain measures the same shape the
        scorer reads, rather than a second implementation of it.
        """
        hours = self._window_hours() if hours is None else np.asarray(hours, dtype=float)
        base = np.full(hours.size, self.base_fraction)
        ...
```

Replace every remaining `INTERVALS_PER_BILLED_DAY` inside the method body with `hours.size`, and replace `np.arange(INTERVALS_PER_BILLED_DAY)` in the refrigeration term with `np.arange(hours.size)`. Leave `peak_day_window` and `monthly_peaks` calling it with no `hours` argument, so their behaviour is byte-identical.

**Verify that claim before moving on.** Run the existing archetype tests: `uv run pytest tests/ -k archetype -v`. They must all still pass, unchanged. If any fails, the refactor changed behaviour and must be corrected, not the test.

- [ ] **Step 5: Write `src/shave/modeled.py`**

```python
"""Magnitude for the archetypes ComStock does not model.

ComStock covers 14 commercial building types and no industry. Against
Powertown's published ICP that is 3 sectors of 11. For the rest, this module
supplies a peak kW from two published inputs and one derivation:

    annual_kwh = intensity x sqft                 published, CBECS or MECS
    implied_LF = annual_energy / (8760 x peak)    derived from the shape
    peak_kw    = annual_kwh / 8760 / implied_LF

The load factor is not asserted anywhere. It falls out of the shape
parameters, which are declared below with the reasoning behind each. That
matters: an asserted load factor and an asserted intensity would put the
chain two assumptions deep with no way to see either.

These shapes remain the weakest link in the project and the method page says
so in those words. There is no US industrial ground truth to check them
against.
"""

from __future__ import annotations

import calendar

import numpy as np

from shave.archetype import MA_COOLING_SHAPE, ModeledArchetype
from shave.assumptions import (
    ELECTRIC_INTENSITY_KWH_PER_SQFT_YR,
    HOURS_PER_YEAR,
    INTERVAL_MINUTES,
    UNANCHORED_ARCHETYPES,
)

#: Interval width in hours, and the number of intervals in a full day.
STEP_HOURS = INTERVAL_MINUTES / 60.0
INTERVALS_PER_DAY = int(round(24.0 / STEP_HOURS))

#: The 24-hour grid the magnitude chain integrates over.
FULL_DAY_HOURS = np.arange(0.0, 24.0, STEP_HOURS)

#: Sanity band on the derived load factor. A shape outside this produced a
#: load factor no real commercial or light-industrial building has, which
#: means the parameters are wrong rather than the building being unusual.
#: Trips loudly at import-time test, not silently at scoring time.
LOAD_FACTOR_BAND = (0.20, 0.80)


class ModeledMagnitudeError(ValueError):
    """This archetype cannot be given a defensible magnitude."""


#: Shape parameters per modelled archetype. These are the four numbers a
#: measured industrial dataset supplies — load factor, hour of peak, spike
#: duration, base/process split — expressed as the template parameters that
#: produce them. EWELD values swap in here if its licence clears; nothing
#: else changes when they do.
SHAPE_PARAMS: dict[str, dict[str, float | bool]] = {
    # Single day shift with a hard inrush at start-up. The inrush is the whole
    # reason a machine shop is a better battery site than a bigger flat load.
    "industrial_manufacturing": dict(
        base_fraction=0.25, shift_start_hour=6.5, shift_end_hour=15.5,
        spike_minutes=20.0, spike_fraction=0.55,
        refrigeration=False, cooling_fraction=0.15,
    ),
    # Compressors run around the clock, so the base is high and the shape is
    # flat — which is exactly why cold storage saves less per kW of battery
    # than its intensity suggests. The model should show that, not hide it.
    "industrial_warehouse_process": dict(
        base_fraction=0.55, shift_start_hour=6.0, shift_end_hour=18.0,
        spike_minutes=15.0, spike_fraction=0.25,
        refrigeration=True, cooling_fraction=0.30,
    ),
    # Fume hoods and environmental rooms never stop; the occupied block adds
    # comparatively little.
    "laboratory": dict(
        base_fraction=0.60, shift_start_hour=8.0, shift_end_hour=18.0,
        spike_minutes=10.0, spike_fraction=0.15,
        refrigeration=False, cooling_fraction=0.25,
    ),
    # Ice plant cycles continuously; the occupied block is evening skate and
    # league play, which runs past the billed window's close.
    "ice_rink": dict(
        base_fraction=0.50, shift_start_hour=9.0, shift_end_hour=22.0,
        spike_minutes=15.0, spike_fraction=0.30,
        refrigeration=True, cooling_fraction=0.20,
    ),
    # Lifts, compressors and welders on a short day, near-nothing overnight.
    "auto_service": dict(
        base_fraction=0.20, shift_start_hour=8.0, shift_end_hour=17.0,
        spike_minutes=15.0, spike_fraction=0.35,
        refrigeration=False, cooling_fraction=0.15,
    ),
    # Showroom lighting runs long and evenly; the service bay adds the morning
    # step. Lot lighting is the overnight base.
    "auto_dealership": dict(
        base_fraction=0.30, shift_start_hour=8.0, shift_end_hour=20.0,
        spike_minutes=10.0, spike_fraction=0.20,
        refrigeration=False, cooling_fraction=0.25,
    ),
    # Campus load is long and flat, with research and residential base.
    "university": dict(
        base_fraction=0.45, shift_start_hour=8.0, shift_end_hour=21.0,
        spike_minutes=10.0, spike_fraction=0.15,
        refrigeration=False, cooling_fraction=0.22,
    ),
}


def archetype_kwargs(params: dict[str, float | bool]) -> dict[str, float | bool]:
    """The subset of `params` that `ModeledArchetype` accepts as keywords."""
    return dict(params)


def full_day_shape(
    params: dict[str, float | bool], day_type: str, month: int
) -> np.ndarray:
    """The normalised 24-hour shape, at the tariff's interval resolution.

    Delegates to `ModeledArchetype._day_shape` with a full-day hour grid, so
    there is exactly one implementation of the shape. A second one here would
    drift from the one the scorer reads, and the magnitude would then be
    computed against a building that does not exist.

    The parcel id is fixed, so the per-parcel jitter does not move the derived
    load factor from parcel to parcel. Jitter shifts when a peak happens; it
    does not change how much energy a day uses.
    """
    probe = ModeledArchetype(parcel_id="__shape_probe__", peak_kw=1.0, **archetype_kwargs(params))
    return probe._day_shape(day_type, month, hours=FULL_DAY_HOURS)


def implied_load_factor(params: dict[str, float | bool], year: int = 2018) -> float:
    """Annual load factor implied by the shape parameters alone.

    Counts real weekdays, Saturdays and Sundays in `year` — the default is
    2018 to match the ComStock AMY2018 weather year the measured half uses —
    integrates the shape over each, and divides the mean by the annual peak.
    """
    peak = max(float(full_day_shape(params, "weekday", m).max()) for m in range(1, 13))
    if peak <= 0.0:
        raise ModeledMagnitudeError("shape has no positive peak")

    total_kwh = 0.0
    for month in range(1, 13):
        counts = {"weekday": 0, "saturday": 0, "sunday": 0}
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            weekday = calendar.weekday(year, month, day)
            key = "weekday" if weekday < 5 else ("saturday" if weekday == 5 else "sunday")
            counts[key] += 1
        for day_type, n in counts.items():
            total_kwh += n * float(full_day_shape(params, day_type, month).sum()) * STEP_HOURS

    return total_kwh / (HOURS_PER_YEAR * peak)


def peak_kw_for(archetype_name: str, sqft: float) -> float:
    """Peak kW for one parcel, by the published chain.

    Raises rather than guessing when the archetype has no anchor. A silently
    invented magnitude is worse than a row the table marks unscored: the row
    ranks, and nothing on the page says it should not have.
    """
    if sqft <= 0:
        raise ModeledMagnitudeError(f"sqft must be positive, got {sqft}")
    if archetype_name in UNANCHORED_ARCHETYPES:
        raise ModeledMagnitudeError(
            f"{archetype_name!r} has no published electricity intensity; "
            "score it as unscored rather than inventing one"
        )
    try:
        intensity = ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[archetype_name]
        params = SHAPE_PARAMS[archetype_name]
    except KeyError as exc:
        raise ModeledMagnitudeError(
            f"{archetype_name!r} has no modelled shape or intensity"
        ) from exc

    annual_kwh = intensity * sqft
    return annual_kwh / HOURS_PER_YEAR / implied_load_factor(params)


def build_modeled_archetype(
    archetype_name: str, parcel_id: str, sqft: float
) -> ModeledArchetype:
    """A modelled archetype scaled to one parcel, magnitude from the chain."""
    return ModeledArchetype(
        parcel_id=parcel_id,
        peak_kw=peak_kw_for(archetype_name, sqft),
        **archetype_kwargs(SHAPE_PARAMS[archetype_name]),
    )
```

`HOURS_PER_YEAR` does not exist yet. Add it to `assumptions.py` next to the interval constants:

```python
#: Hours in a non-leap year. The annual-intensity to peak-kW conversion
#: divides by this; using 8784 in a leap year would move every modelled
#: magnitude by 0.3%, which is far inside the error of the intensity itself.
HOURS_PER_YEAR = 8760.0
```

- [ ] **Step 6: Run the shape-agreement test**

Run: `uv run pytest tests/test_modeled.py -v`
Expected: PASS

- [ ] **Step 7: Write the magnitude tests**

Append to `tests/test_modeled.py`:

```python
def test_every_modeled_archetype_has_a_plausible_load_factor():
    """A guard rail on the parameters, not on the code. A shape that implies a
    load factor no real building has means the parameters are wrong."""
    low, high = modeled.LOAD_FACTOR_BAND
    for name, params in modeled.SHAPE_PARAMS.items():
        lf = modeled.implied_load_factor(params)
        assert low <= lf <= high, f"{name} implies a load factor of {lf:.3f}"


def test_the_chain_reproduces_the_published_annual_energy():
    """Magnitude is only defensible if the round trip closes: a peak derived
    from an intensity must integrate back to that intensity's annual kWh."""
    name, sqft = "industrial_manufacturing", 20_000.0
    params = modeled.SHAPE_PARAMS[name]

    peak = modeled.peak_kw_for(name, sqft)
    lf = modeled.implied_load_factor(params)
    recovered = peak * lf * 8760.0

    expected = modeled.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR[name] * sqft
    assert recovered == pytest.approx(expected, rel=1e-9)


def test_peak_scales_linearly_with_floor_area():
    a = modeled.peak_kw_for("laboratory", 10_000.0)
    b = modeled.peak_kw_for("laboratory", 20_000.0)
    assert b == pytest.approx(2.0 * a)


def test_a_machine_shop_lands_in_the_g2_band():
    """The thesis, as a test. A mid-size single-shift manufacturer should come
    out near the 200 kW rate boundary, which is where the expensive tariff and
    the spiky shape overlap. If this drifts far, the parameters have."""
    peak = modeled.peak_kw_for("industrial_manufacturing", 20_000.0)
    assert 150.0 <= peak <= 260.0, f"20k sq ft machine shop peaks at {peak:.0f} kW"


def test_an_unanchored_archetype_refuses_rather_than_guessing():
    for name in UNANCHORED_ARCHETYPES:
        with pytest.raises(modeled.ModeledMagnitudeError, match="no published"):
            modeled.peak_kw_for(name, 10_000.0)


def test_every_modeled_crosswalk_type_is_anchored_or_named_unanchored():
    """The crosswalk and this module must not disagree about what is
    scoreable. A type in neither dict is a row that fails at scoring time."""
    from shave.crosswalk import MODELED_TYPES

    covered = set(ELECTRIC_INTENSITY_KWH_PER_SQFT_YR) | set(UNANCHORED_ARCHETYPES)
    assert MODELED_TYPES <= covered, f"unhandled: {MODELED_TYPES - covered}"
    assert set(modeled.SHAPE_PARAMS) == set(ELECTRIC_INTENSITY_KWH_PER_SQFT_YR)


def test_zero_and_negative_floor_area_raise():
    for bad in (0.0, -1.0):
        with pytest.raises(modeled.ModeledMagnitudeError, match="positive"):
            modeled.peak_kw_for("auto_service", bad)
```

- [ ] **Step 8: Run them**

Run: `uv run pytest tests/test_modeled.py -v`
Expected: PASS, all eight.

The values measured while writing this plan, for comparison in your report — implied load factor, then kW per 1,000 sq ft:

| archetype | implied LF | kW/1,000 sq ft | 20,000 sq ft peak |
|---|---|---|---|
| industrial_manufacturing | 0.274 | 9.80 | 196 kW |
| industrial_warehouse_process | 0.483 | 6.99 | 140 kW |
| laboratory | 0.538 | 6.81 | 136 kW |
| ice_rink | 0.488 | 3.04 | 61 kW |
| auto_service | 0.289 | 2.41 | 48 kW |
| auto_dealership | 0.404 | 4.30 | 86 kW |
| university | 0.512 | 2.81 | 56 kW |

If your numbers differ by more than 1%, the `_day_shape` refactor changed behaviour. Find out why before proceeding.

- [ ] **Step 9: Add `offpeak_max` to `ModeledArchetype`**

The protocol gained this method in Task 1 and `ModeledArchetype` must satisfy it. The overnight load is the full-day shape restricted to the recharge window. In `src/shave/archetype.py`:

```python
    def offpeak_max(self, month: int) -> float:
        """Highest load in the 21:00-08:00 recharge window, in kW.

        Uses the weekday shape: a weekday night is the one that has to absorb
        the recharge, and it carries the highest base of the three day types.
        """
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        from shave.modeled import FULL_DAY_HOURS  # local: modeled imports this module

        shape = self._day_shape("weekday", month, hours=FULL_DAY_HOURS)
        night = (FULL_DAY_HOURS >= PEAK_HOUR_END) | (FULL_DAY_HOURS < PEAK_HOUR_START)
        annual_max = max(
            self._day_shape("weekday", m).max() for m in range(1, 13)
        )
        if annual_max <= 0:
            return 0.0
        return float(shape[night].max() * (self.peak_kw / annual_max))
```

The local import is deliberate and must carry that comment: `modeled` imports `archetype`, so a module-level import here is a cycle.

Add the test to `tests/test_modeled.py`:

```python
def test_modeled_archetype_reports_a_positive_overnight_load():
    arch = modeled.build_modeled_archetype("industrial_manufacturing", "LOC1", 20_000.0)

    night = arch.offpeak_max(6)
    day = float(arch.peak_day_window(6).max())

    assert 0.0 < night < day, "overnight base is real but below the shift peak"
    with pytest.raises(ValueError):
        arch.offpeak_max(0)
```

- [ ] **Step 10: Run the whole suite**

Run: `uv run pytest`
Expected: PASS, 859 + Task 1's 7 + Task 2's 4 + 9 here.

- [ ] **Step 11: Commit**

```bash
git add src/shave/modeled.py src/shave/archetype.py src/shave/assumptions.py tests/test_modeled.py
git commit -m "feat: magnitude for the archetypes ComStock does not model

653 of Worcester's 2,099 scoreable parcels — every machine shop, metal
fabricator and cold store in the ICP — had a shape and no magnitude. Anchors
magnitude to CBECS 2018 Table C22 and MECS 2018 Tables 3.2 and 9.1, and
DERIVES the load factor from the shape rather than asserting it, so the chain
is one published number and one declared shape rather than two assumptions.

data_hall has no defensible published intensity and is named unanchored
rather than given an invented one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Task 4: The pipeline

The join that does not exist. Parcels in, scored rows out, with the flags the prototype run showed are needed.

**Files:**
- Create: `src/shave/pipeline.py`
- Test: `tests/test_pipeline.py` (new)

**Interfaces:**
- Consumes: `ingest.load_municipality`, `comstock.build_archetype`, `modeled.build_modeled_archetype`, `crosswalk.resolve_office_band`, every public function in `scorer`, `billing_window.OFFPEAK_HOURS`.
- Produces:
  - `pipeline.ScoredRow` — a frozen dataclass, fields listed in Step 3
  - `pipeline.score_parcel(parcel: Mapping, archetype: Archetype) -> ScoredRow`
  - `pipeline.score_parcels(gdf, *, archetype_factory=None) -> pd.DataFrame`
  - `pipeline.UNSCORED_REASONS: tuple[str, ...]`

- [ ] **Step 1: Write the failing test for a single row**

Create `tests/test_pipeline.py`:

```python
import numpy as np
import pandas as pd
import pytest

from shave import pipeline
from shave.archetype import INTERVALS_PER_BILLED_DAY, FixtureArchetype
from shave.assumptions import G2_DEMAND_CHARGE_PER_KW, RATED_POWER_KW


def _flat_archetype(peak_kw: float, offpeak_kw: float = 10.0) -> FixtureArchetype:
    """A load that sits at `peak_kw` for the whole billed window, every month."""
    return FixtureArchetype(
        monthly_peak_kw=np.full(12, peak_kw),
        windows=np.full((12, INTERVALS_PER_BILLED_DAY), peak_kw),
        offpeak_max_kw=np.full(12, offpeak_kw),
        source="comstock",
    )


def test_a_flat_load_saves_almost_nothing():
    """13 hours at 150 kW is 1,950 kWh above any useful threshold. The battery
    holds 413. A flat load is the wrong site and the score must say so."""
    parcel = {"loc_id": "L1", "sqft": 30_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, _flat_archetype(150.0))

    assert row.rate_class == "G-2"
    assert row.annual_savings_usd < 0.10 * (
        RATED_POWER_KW * G2_DEMAND_CHARGE_PER_KW * 12
    )
    assert row.shaved_fraction < 0.25
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.pipeline'`

- [ ] **Step 3: Write `src/shave/pipeline.py`**

```python
"""Parcels in, scored rows out.

Every component this calls is already tested in isolation. What lives here is
only the joining: which archetype a parcel gets, the monthly loop over it, and
the flags that say how far to trust the answer.

The monthly loop is a deliberate approximation and it is stated on the method
page. The tariff bills the monthly maximum, and the threshold that matters is
the one holdable on EVERY billed day of the month. The Archetype protocol
exposes one day per month — that month's worst — so `T_month` here is the
threshold for the peak day alone. It is the right day to pick if you may pick
only one, because it carries the month's highest peak and therefore, for these
shapes, its highest threshold. It is not a proof.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from shave import comstock, crosswalk, modeled, scorer
from shave.archetype import Archetype
from shave.assumptions import RATED_POWER_KW
from shave.billing_window import OFFPEAK_HOURS

#: How far a parcel may be scaled from its representative before the linear
#: scale stops being defensible. ComStock's RetailStandalone representative is
#: 10,000 sq ft; applying its shape to a 164,000 sq ft building is a different
#: building, not a bigger one. 34 Worcester rows exceed 5x, 8 exceed 10x.
MAX_SCALE_RATIO = 5.0

#: Reasons a parcel is carried into the export without a score. Every one is
#: shown in the row rather than the row being dropped: a named gap is a
#: finding, a missing row is a silence.
UNSCORED_REASONS: tuple[str, ...] = (
    "no_floor_area",
    "no_intensity_anchor",
    "no_archetype_profile",
)


@dataclass(frozen=True)
class ScoredRow:
    loc_id: str
    archetype: str
    source: str
    sqft: float
    monthly_billed_demand_kw: tuple[float, ...]
    monthly_shaveable_kw: tuple[float, ...]
    avg_12mo_kw: float
    peak_kw: float
    peak_to_avg: float
    rate_class: str
    demand_charge_per_kw: float
    annual_savings_usd: float
    shaved_fraction: float
    sweet_spot: bool
    keep: bool
    band_reason: str | None
    recharge_feasible: bool
    months_at_power_cap: int
    flags: tuple[str, ...] = ()
    unscored_reason: str | None = None


def _scale_ratio(archetype: Archetype, sqft: float) -> float:
    """How many times the representative's own floor area this parcel is."""
    profile = getattr(archetype, "profile", None)
    base = getattr(profile, "sqft", None)
    if not base:
        return 1.0
    return float(sqft) / float(base)


def score_parcel(parcel: Mapping, archetype: Archetype) -> ScoredRow:
    """One parcel's twelve months, the tariff test, and the flags."""
    sqft = float(parcel["sqft"])
    peaks = np.asarray(archetype.monthly_peaks(), dtype=float)

    thresholds = np.array(
        [scorer.shave_threshold(archetype.peak_day_window(m)) for m in range(1, 13)]
    )
    shaveable = np.maximum(0.0, peaks - thresholds)

    avg_12mo = scorer.average_billed_demand(peaks)
    peak_to_avg = scorer.peak_to_average(peaks)
    rate_class = scorer.assign_rate_class(peaks)
    band = scorer.band_filter(avg_12mo, peak_to_avg, rate_class)

    # The recharge test, on the month that discharges the most. That is the
    # month most likely to fail it, so passing there passes everywhere.
    worst = int(np.argmax(shaveable))
    e_used = scorer.energy_above_threshold(
        archetype.peak_day_window(worst + 1), float(thresholds[worst])
    )
    recharge_ok = scorer.recharge_feasible(
        e_used_kwh=e_used,
        offpeak_hours=OFFPEAK_HOURS,
        l_offpeak_max_kw=archetype.offpeak_max(worst + 1),
        t_month=float(thresholds[worst]),
    )

    flags: list[str] = []
    months_at_cap = int(np.sum(shaveable >= RATED_POWER_KW - 1e-6))
    if months_at_cap:
        # The Powerblock is undersized here: the saving is a floor, not an
        # estimate, and the honest reading is "this site wants two units".
        flags.append("power_limited")
    ratio = _scale_ratio(archetype, sqft)
    if ratio > MAX_SCALE_RATIO:
        flags.append("scale_extrapolation")
    if not recharge_ok:
        flags.append("recharge_constrained")
    if getattr(archetype, "widened", False):
        flags.append("thin_cohort")

    with np.errstate(divide="ignore", invalid="ignore"):
        fraction = np.divide(
            shaveable, peaks, out=np.zeros_like(shaveable), where=peaks > 0
        )

    return ScoredRow(
        loc_id=str(parcel["loc_id"]),
        archetype=str(parcel["archetype"]),
        source=str(parcel["source"]),
        sqft=sqft,
        monthly_billed_demand_kw=tuple(round(float(v), 2) for v in peaks),
        monthly_shaveable_kw=tuple(round(float(v), 2) for v in shaveable),
        avg_12mo_kw=avg_12mo,
        peak_kw=float(peaks.max()),
        peak_to_avg=peak_to_avg,
        rate_class=rate_class,
        demand_charge_per_kw=scorer.demand_charge_for(rate_class),
        annual_savings_usd=scorer.annual_savings_usd(shaveable, rate_class),
        shaved_fraction=float(fraction.mean()),
        sweet_spot=bool(band["sweet_spot"]),
        keep=bool(band["keep"]),
        band_reason=band["reason"],
        recharge_feasible=recharge_ok,
        months_at_power_cap=months_at_cap,
        flags=tuple(flags),
    )


def _unscored(parcel: Mapping, reason: str) -> ScoredRow:
    """A row that is carried, named and not ranked."""
    return ScoredRow(
        loc_id=str(parcel.get("loc_id", "")),
        archetype=str(parcel.get("archetype", "")),
        source=str(parcel.get("source", "")),
        sqft=float(parcel.get("sqft") or 0.0),
        monthly_billed_demand_kw=(0.0,) * 12,
        monthly_shaveable_kw=(0.0,) * 12,
        avg_12mo_kw=0.0,
        peak_kw=0.0,
        peak_to_avg=0.0,
        rate_class="G-2",
        demand_charge_per_kw=scorer.demand_charge_for("G-2"),
        annual_savings_usd=0.0,
        shaved_fraction=0.0,
        sweet_spot=False,
        keep=False,
        band_reason=reason,
        recharge_feasible=False,
        months_at_power_cap=0,
        unscored_reason=reason,
    )


def default_archetype_factory(parcel: Mapping) -> Archetype:
    """The archetype for one parcel. Raises for anything unscoreable."""
    name = str(parcel["archetype"])
    sqft = float(parcel["sqft"])
    if str(parcel["source"]) == "comstock":
        if name == "office":
            # Defensive. `ingest._resolve_office_bands` already resolves the
            # office family before a parcel reaches here — Worcester's output
            # contains small_office, medium_office and large_office and no bare
            # "office" — but resolving it in one place only means a future
            # caller that skips ingest gets a ComStockError instead of a band.
            name = crosswalk.resolve_office_band(sqft)
        return comstock.build_archetype(name, sqft)
    return modeled.build_modeled_archetype(name, str(parcel["loc_id"]), sqft)


def score_parcels(
    gdf: pd.DataFrame,
    archetype_factory: Callable[[Mapping], Archetype] | None = None,
) -> pd.DataFrame:
    """Score every parcel. One row out per row in, scored or named unscored.

    The archetype cache means one S3 round trip per archetype, not per parcel,
    so this is a loop over ~2,100 parcels that completes in seconds. Measured
    at 2.1 s for Worcester's 1,446 ComStock rows.
    """
    build = archetype_factory or default_archetype_factory
    cache: dict[tuple[str, str], Archetype | None] = {}
    rows: list[ScoredRow] = []

    for parcel in gdf.to_dict("records"):
        sqft = pd.to_numeric(parcel.get("sqft"), errors="coerce")
        if not sqft or not np.isfinite(sqft) or sqft <= 0:
            rows.append(_unscored(parcel, "no_floor_area"))
            continue
        parcel["sqft"] = float(sqft)

        try:
            archetype = build(parcel)
        except modeled.ModeledMagnitudeError:
            rows.append(_unscored(parcel, "no_intensity_anchor"))
            continue
        except comstock.ComStockError:
            rows.append(_unscored(parcel, "no_archetype_profile"))
            continue

        rows.append(score_parcel(parcel, archetype))

    scored = pd.DataFrame([asdict(r) for r in rows])
    return scored
```

The `cache` local is declared and unused in the loop above because `comstock.build_archetype` already caches to disk and `modeled.build_modeled_archetype` is pure computation. **Delete the `cache` line**; it is named here only so you do not add a second caching layer thinking one is missing.

- [ ] **Step 4: Run the first test**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Write the rest of the row tests**

Append to `tests/test_pipeline.py`:

```python
def test_a_spiky_load_of_the_same_average_saves_far_more():
    """The thesis in one assertion. Two sites, same energy, different shape."""
    flat = np.full(INTERVALS_PER_BILLED_DAY, 100.0)
    spiky = np.full(INTERVALS_PER_BILLED_DAY, 60.0)
    spiky[20:24] = 620.0  # one hour of inrush, same daily kWh as flat

    assert spiky.sum() == pytest.approx(flat.sum())

    parcel = {"loc_id": "L1", "sqft": 20_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    flat_row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, flat.max()),
        windows=np.tile(flat, (12, 1)),
        offpeak_max_kw=np.full(12, 20.0),
    ))
    spiky_row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, spiky.max()),
        windows=np.tile(spiky, (12, 1)),
        offpeak_max_kw=np.full(12, 20.0),
    ))

    assert spiky_row.annual_savings_usd > 3 * flat_row.annual_savings_usd


def test_the_power_cap_is_flagged_not_hidden():
    """A site that saturates the battery every month is undersized for it.
    That is a finding — it wants two Powerblocks — not a top-ranked site."""
    window = np.full(INTERVALS_PER_BILLED_DAY, 200.0)
    window[10:12] = 2_000.0  # a very short, very tall spike
    parcel = {"loc_id": "L1", "sqft": 100_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "MED"}

    row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, 2_000.0),
        windows=np.tile(window, (12, 1)),
        offpeak_max_kw=np.full(12, 50.0),
    ))

    assert row.months_at_power_cap == 12
    assert "power_limited" in row.flags
    assert row.annual_savings_usd == pytest.approx(
        RATED_POWER_KW * row.demand_charge_per_kw * 12
    )


def test_sweet_spot_needs_both_the_rate_class_and_the_spikiness():
    """Neither half alone. The band comes from the tariff, not a kW window."""
    flat = pipeline.score_parcel(
        {"loc_id": "A", "sqft": 20_000.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "HIGH"},
        _flat_archetype(150.0),
    )
    assert flat.rate_class == "G-2"
    assert flat.sweet_spot is False, "G-2 but perfectly flat"

    peaks = np.full(12, 150.0)
    peaks[6] = 400.0  # one hot month; 12-month average stays under 200 kW
    spiky = pipeline.score_parcel(
        {"loc_id": "B", "sqft": 20_000.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "HIGH"},
        FixtureArchetype(
            monthly_peak_kw=peaks,
            windows=np.stack([np.full(INTERVALS_PER_BILLED_DAY, p) for p in peaks]),
            offpeak_max_kw=np.full(12, 20.0),
        ),
    )
    assert spiky.rate_class == "G-2"
    assert spiky.sweet_spot is True


def test_below_the_floor_is_dropped_with_a_stated_reason():
    row = pipeline.score_parcel(
        {"loc_id": "C", "sqft": 2_000.0, "archetype": "auto_service",
         "source": "modeled", "confidence": "LOW"},
        _flat_archetype(30.0),
    )
    assert row.keep is False
    assert "below floor" in row.band_reason


def test_a_parcel_with_no_floor_area_is_carried_not_dropped():
    gdf = pd.DataFrame([
        {"loc_id": "L1", "sqft": 0.0, "archetype": "warehouse",
         "source": "comstock", "confidence": "LOW"},
    ])

    out = pipeline.score_parcels(gdf, archetype_factory=lambda p: _flat_archetype(100.0))

    assert len(out) == 1
    assert out["unscored_reason"].iloc[0] == "no_floor_area"
    assert out["annual_savings_usd"].iloc[0] == 0.0


def test_an_unanchored_archetype_is_carried_with_its_reason():
    gdf = pd.DataFrame([
        {"loc_id": "L1", "sqft": 40_000.0, "archetype": "data_hall",
         "source": "modeled", "confidence": "LOW"},
    ])

    out = pipeline.score_parcels(gdf)

    assert out["unscored_reason"].iloc[0] == "no_intensity_anchor"


def test_shaveable_is_measured_against_the_BILLED_peak_only():
    """An outside review of the spec found a 2x overstatement hiding here.

    `shaveable = L_peak(month) - T_month` is only correct when `L_peak` is the
    BILLED peak. If an unbilled spike — a Saturday overtime run, a 3 a.m.
    compressor start — reaches `monthly_peaks()`, the subtraction claims a
    reduction in a demand the customer was never charged for.

    Both implementations mask to billed intervals before taking a monthly
    maximum, so this passes today. It is asserted here because nothing else
    would notice if a future change to either reducer stopped masking.
    """
    window = np.full(INTERVALS_PER_BILLED_DAY, 250.0)
    parcel = {"loc_id": "L1", "sqft": 20_000.0, "archetype": "warehouse",
              "source": "comstock", "confidence": "HIGH"}

    row = pipeline.score_parcel(parcel, FixtureArchetype(
        monthly_peak_kw=np.full(12, 250.0),          # the billed peak
        windows=np.tile(window, (12, 1)),
        offpeak_max_kw=np.full(12, 300.0),           # a HIGHER unbilled spike
    ))

    assert row.peak_kw == pytest.approx(250.0), "the unbilled 300 kW must not rank"
    for billed, shaved in zip(row.monthly_billed_demand_kw, row.monthly_shaveable_kw):
        assert shaved <= billed + 1e-9


def test_scale_extrapolation_is_flagged():
    class _Rep:
        sqft = 10_000.0

    arch = _flat_archetype(500.0)
    object.__setattr__(arch, "profile", _Rep())

    row = pipeline.score_parcel(
        {"loc_id": "L1", "sqft": 120_000.0, "archetype": "retail_standalone",
         "source": "comstock", "confidence": "MED"},
        arch,
    )

    assert "scale_extrapolation" in row.flags
```

`FixtureArchetype` is a plain `@dataclass` rather than frozen, so `object.__setattr__` in the last test is belt-and-braces; use a plain attribute assignment if it is not frozen.

- [ ] **Step 6: Run them**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS, all nine.

- [ ] **Step 7: Run against real Worcester data**

```bash
uv run python -c "
from shave import ingest, pipeline
g = ingest.load_municipality('data/raw/M348_WORCESTER/L3_SHP_M348_Worcester', 348)
s = pipeline.score_parcels(g)
print('rows:', len(s))
print('unscored:', s.unscored_reason.value_counts(dropna=True).to_dict())
print('kept:', int(s.keep.sum()), 'sweet spot:', int(s.sweet_spot.sum()))
print('by source:', s[s.keep].groupby('source').size().to_dict())
print('rate class:', s[s.keep].rate_class.value_counts().to_dict())
print()
top = s[s.keep].nlargest(10, 'annual_savings_usd')
print(top[['archetype','source','sqft','avg_12mo_kw','rate_class',
           'annual_savings_usd','shaved_fraction','flags']].to_string(index=False))
"
```

**Pass conditions, declared in advance.** Report all five in your task report:
1. `rows` equals 2,099 — every parcel is carried, none silently dropped.
2. `unscored` contains `no_intensity_anchor: 6` (the data halls) and `no_floor_area: 1`, and nothing else.
3. `by source` contains both `comstock` and `modeled` keys — the modelled half now scores.
4. No kept row has `annual_savings_usd` above `250 x 15.06 x 12 = 45,180`, the arithmetic ceiling at the G-2 rate.
5. The top ten is **not** all one archetype. Before Tasks 1–3 it was 28 strip malls in the top 60. If it still is, say so plainly in the report rather than adjusting anything — that is a finding for the method page, not a bug to paper over.

- [ ] **Step 8: Commit**

```bash
git add src/shave/pipeline.py tests/test_pipeline.py
git commit -m "feat: the pipeline — parcels in, scored rows out

The join that did not exist. Monthly loop, tariff rate-class test, band
filter, recharge predicate, and four flags the prototype run showed were
needed: power_limited, scale_extrapolation, recharge_constrained, thin_cohort.

A parcel that cannot be scored is carried with a named reason rather than
dropped. A named gap is a finding; a missing row is a silence.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Task 5: The versioned export and the one command

`ranked_export` → `ranked.json` against a written schema carrying a `schema_version`, so a stale deploy fails loudly instead of rendering wrong numbers. This is the only interface between the Python and TypeScript halves.

**Files:**
- Create: `src/shave/export.py`
- Create: `scripts/run_pipeline.py`
- Create: `docs/ranked-json-schema.md`
- Test: `tests/test_export.py` (new)

**Interfaces:**
- Consumes: `pipeline.score_parcels`, `assumptions.published_rows`.
- Produces:
  - `export.SCHEMA_VERSION: str = "1.0.0"`
  - `export.TOP_N: int = 250`
  - `export.MAX_BYTES: int`
  - `export.build_export(scored, parcels, town) -> dict`
  - `export.reason_sentence(row) -> str`
  - `export.write_export(payload, path) -> Path`

- [ ] **Step 1: Write the failing test**

Create `tests/test_export.py`:

```python
import json

import numpy as np
import pandas as pd
import pytest

from shave import export


def _row(loc_id="L1", usd=10_000.0, source="comstock", **over):
    base = dict(
        loc_id=loc_id, archetype="warehouse", source=source, sqft=20_000.0,
        monthly_billed_demand_kw=[180.0] * 12, monthly_shaveable_kw=[60.0] * 12,
        avg_12mo_kw=180.0, peak_kw=250.0, peak_to_avg=1.39, rate_class="G-2",
        demand_charge_per_kw=15.06, annual_savings_usd=usd, shaved_fraction=0.33,
        sweet_spot=False, keep=True, band_reason=None, recharge_feasible=True,
        months_at_power_cap=0, flags=[], unscored_reason=None,
    )
    base.update(over)
    return base


def _parcels(loc_ids):
    return pd.DataFrame([
        {"loc_id": i, "prop_id": f"P{i}", "site_addr": f"{n} MAIN ST",
         "city": "WORCESTER", "zip": "01610", "owner": f"OWNER {n}",
         "use_code": "4000", "use_desc": "Manufacturing", "icp_sector": "3",
         "assess_fy": 2026, "confidence": "HIGH", "confidence_reasons": (),
         "lon": -71.8 - n / 1000, "lat": 42.26 + n / 1000}
        for n, i in enumerate(loc_ids)
    ])


def test_the_export_carries_a_schema_version_and_two_separate_lists():
    """The spec forbids merging modelled and measured rows into one ranking:
    the industrial magnitude chain is two steps deeper than ComStock's."""
    scored = pd.DataFrame([_row("L1", 9_000.0), _row("L2", 12_000.0, source="modeled")])

    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert payload["schema_version"] == export.SCHEMA_VERSION
    assert set(payload["lists"]) == {"comstock", "modeled"}
    assert [r["loc_id"] for r in payload["lists"]["comstock"]] == ["L1"]
    assert [r["loc_id"] for r in payload["lists"]["modeled"]] == ["L2"]
    assert payload["lists"]["comstock"][0]["rank"] == 1
    assert payload["lists"]["modeled"][0]["rank"] == 1, "ranks restart per list"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.export'`

- [ ] **Step 3: Write `src/shave/export.py`**

```python
"""The versioned contract between the Python half and whatever renders it.

One file, one schema version. A stale deploy against a changed schema fails
loudly here rather than rendering wrong numbers quietly.

Two lists, never merged. The modelled-industrial magnitude runs through a
published intensity and a derived load factor; ComStock's runs through a
measured timeseries. Ranking them against each other in dollars would claim a
comparability the data does not support, so each is ranked within itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from shave.assumptions import published_rows

#: Bump the MINOR for an added field, the MAJOR for a removed or retyped one.
#: `docs/ranked-json-schema.md` is the written contract; change both together.
SCHEMA_VERSION = "1.0.0"

#: Rows per list. Cloudflare caps a Pages asset at 25 MiB and the page has to
#: render in under three seconds on a cold load; 250 rows per list keeps the
#: payload in the hundreds of kilobytes with room for geometry later.
TOP_N = 250

#: Hard ceiling, well under Cloudflare's 25 MiB, checked at write time.
MAX_BYTES = 5 * 1024 * 1024

#: Columns lifted from the parcel frame onto every exported row.
PARCEL_FIELDS = (
    "prop_id", "site_addr", "city", "zip", "owner", "use_code", "use_desc",
    "icp_sector", "assess_fy", "confidence", "confidence_reasons",
    "lon", "lat",
)

_SOURCE_PHRASE = {
    "comstock": (
        "measured, from the NREL ComStock building most typical of its type in "
        "Worcester County by peak intensity"
    ),
    "modeled": (
        "modelled, not measured: a synthesised shift profile scaled to published "
        "EIA electricity intensity"
    ),
}


def reason_sentence(row: dict) -> str:
    """The one sentence a domain expert can check.

    Templated. No agent exists yet, and a template that states the arithmetic
    is more checkable than prose that summarises it.
    """
    shave = float(np.mean(row["monthly_shaveable_kw"]))
    return (
        f"A {row['sqft']:,.0f} sq ft {row.get('use_desc') or row['archetype']} "
        f"on rate {row['rate_class']} at ${row['demand_charge_per_kw']:.2f}/kW. "
        f"Estimated 12-month average demand {row['avg_12mo_kw']:,.0f} kW, peaking "
        f"at {row['peak_kw']:,.0f} kW; a 250 kW / 522 kWh Powerblock holds about "
        f"{shave:,.0f} kW off the billed peak in an average month, worth "
        f"${row['annual_savings_usd']:,.0f} a year in distribution demand charges "
        f"alone. Load shape is {_SOURCE_PHRASE.get(row['source'], row['source'])}."
    )


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.ndarray, tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is pd.NA or (isinstance(value, float) and np.isnan(value)):
        return None
    return value


def build_export(
    scored: pd.DataFrame,
    parcels: pd.DataFrame,
    town: dict,
    top_n: int = TOP_N,
) -> dict:
    """The whole payload: counts, assumptions, and the two ranked lists."""
    merged = scored.merge(
        parcels[[c for c in PARCEL_FIELDS if c in parcels.columns] + ["loc_id"]],
        on="loc_id",
        how="left",
    )

    lists: dict[str, list[dict]] = {}
    for source in ("comstock", "modeled"):
        subset = merged[(merged["source"] == source) & merged["keep"].astype(bool)]
        subset = subset.nlargest(top_n, "annual_savings_usd")
        rows = []
        for rank, record in enumerate(subset.to_dict("records"), start=1):
            record = {k: _jsonable(v) for k, v in record.items()}
            record["rank"] = rank
            record["reason"] = reason_sentence(record)
            rows.append(record)
        lists[source] = rows

    unscored = scored["unscored_reason"].dropna()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "town": town,
        "counts": {
            "parcels_in": int(len(scored)),
            "scored": int(scored["unscored_reason"].isna().sum()),
            "unscored": {k: int(v) for k, v in unscored.value_counts().items()},
            "kept": int(scored["keep"].astype(bool).sum()),
            "sweet_spot": int(scored["sweet_spot"].astype(bool).sum()),
            "exported": {k: len(v) for k, v in lists.items()},
        },
        "assumptions": published_rows(),
        "lists": lists,
    }


def write_export(payload: dict, path: str | Path) -> Path:
    """Write the payload, refusing to write one the CDN cannot serve well."""
    path = Path(path)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise ValueError(
            f"export is {size / 1e6:.1f} MB, over the {MAX_BYTES / 1e6:.0f} MB "
            f"ceiling; reduce TOP_N or drop a field"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
```

- [ ] **Step 4: Run the first test**

Run: `uv run pytest tests/test_export.py -v`
Expected: PASS

- [ ] **Step 5: Write the rest of the export tests**

Append to `tests/test_export.py`:

```python
def test_unscored_rows_never_reach_a_ranked_list():
    scored = pd.DataFrame([
        _row("L1", 9_000.0),
        _row("L2", 0.0, keep=False, unscored_reason="no_intensity_anchor"),
    ])

    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert [r["loc_id"] for r in payload["lists"]["comstock"]] == ["L1"]
    assert payload["counts"]["unscored"] == {"no_intensity_anchor": 1}


def test_rows_are_ranked_by_dollars_descending():
    scored = pd.DataFrame([_row("L1", 5_000.0), _row("L2", 20_000.0), _row("L3", 9_000.0)])

    payload = export.build_export(scored, _parcels(["L1", "L2", "L3"]),
                                  town={"name": "Worcester", "town_id": 348})

    usd = [r["annual_savings_usd"] for r in payload["lists"]["comstock"]]
    assert usd == sorted(usd, reverse=True)
    assert [r["rank"] for r in payload["lists"]["comstock"]] == [1, 2, 3]


def test_every_row_carries_a_checkable_reason():
    scored = pd.DataFrame([_row("L1", 14_321.0)])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})
    reason = payload["lists"]["comstock"][0]["reason"]

    assert "G-2" in reason
    assert "$15.06/kW" in reason
    assert "14,321" in reason
    assert "measured" in reason


def test_a_modeled_row_says_it_is_modelled():
    scored = pd.DataFrame([_row("L1", 8_000.0, source="modeled")])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})

    assert "modelled, not measured" in payload["lists"]["modeled"][0]["reason"]


def test_the_assumptions_travel_with_the_payload():
    """P6: published assumptions must be provably the computed ones."""
    scored = pd.DataFrame([_row("L1")])

    payload = export.build_export(scored, _parcels(["L1"]),
                                  town={"name": "Worcester", "town_id": 348})
    keys = {a["key"] for a in payload["assumptions"]}

    assert {"g2_demand_charge", "g3_demand_charge", "g3_threshold"} <= keys


def test_the_payload_is_json_serialisable_and_round_trips(tmp_path):
    scored = pd.DataFrame([_row("L1"), _row("L2", source="modeled")])
    payload = export.build_export(scored, _parcels(["L1", "L2"]),
                                  town={"name": "Worcester", "town_id": 348})

    path = export.write_export(payload, tmp_path / "ranked.json")
    back = json.loads(path.read_text())

    assert back["schema_version"] == export.SCHEMA_VERSION
    assert back["lists"]["comstock"][0]["loc_id"] == "L1"


def test_an_oversized_payload_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="ceiling"):
        export.write_export({"schema_version": "1.0.0", "pad": "x" * 500},
                            tmp_path / "ranked.json")
```

- [ ] **Step 6: Run them**

Run: `uv run pytest tests/test_export.py -v`
Expected: PASS, all eight.

- [ ] **Step 7: Write the schema document**

Create `docs/ranked-json-schema.md`. It is prose plus a field table — the written contract the code's `SCHEMA_VERSION` refers to. Document every top-level key (`schema_version`, `generated_at`, `town`, `counts`, `assumptions`, `lists`) and every row field produced by `ScoredRow` plus `PARCEL_FIELDS`, `rank` and `reason`, each with its type, its unit, and one sentence on what it means. State the versioning rule: MINOR for an added field, MAJOR for a removed or retyped one, and both the doc and `SCHEMA_VERSION` change together.

- [ ] **Step 8: Write the CLI**

Create `scripts/run_pipeline.py`:

```python
"""Ingest, score, export. The one command.

    uv run python scripts/run_pipeline.py
    uv run python scripts/run_pipeline.py --dir data/raw/... --town-id 348 --out public/ranked.json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from shave import export, ingest, pipeline

DEFAULT_DIR = "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
DEFAULT_TOWN_ID = 348
DEFAULT_NAME = "Worcester"
DEFAULT_OUT = "public/ranked.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DEFAULT_DIR, help="MassGIS L3 extract directory")
    ap.add_argument("--town-id", type=int, default=DEFAULT_TOWN_ID)
    ap.add_argument("--town-name", default=DEFAULT_NAME)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--top-n", type=int, default=export.TOP_N)
    args = ap.parse_args(argv)

    started = time.perf_counter()

    parcels = ingest.load_municipality(args.dir, args.town_id)
    print(f"ingested {len(parcels):,} scoreable parcels", file=sys.stderr)

    scored = pipeline.score_parcels(parcels)
    print(f"scored {int(scored['unscored_reason'].isna().sum()):,}, "
          f"kept {int(scored['keep'].astype(bool).sum()):,}", file=sys.stderr)

    # Centroids for the map. Projected coordinates go to WGS84 here and
    # nowhere else, so nothing downstream has to know about EPSG:26986.
    parcels = parcels.copy()
    centroids = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = centroids.x
    parcels["lat"] = centroids.y

    assess_fy = parcels["assess_fy"].dropna()
    town = {
        "name": args.town_name,
        "town_id": args.town_id,
        "assess_fy": int(assess_fy.iloc[0]) if len(assess_fy) else None,
    }

    payload = export.build_export(scored, parcels, town=town, top_n=args.top_n)
    path = export.write_export(payload, args.out)

    elapsed = time.perf_counter() - started
    size_kb = path.stat().st_size / 1024
    print(f"wrote {path} ({size_kb:,.0f} KB) in {elapsed:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`representative_point()` is used rather than `centroid` deliberately: a centroid of an L-shaped or ring parcel can land outside it, which puts a map marker in someone else's yard.

- [ ] **Step 9: Run it end to end**

```bash
uv run python scripts/run_pipeline.py
```

**Pass conditions:** it exits 0; `public/ranked.json` exists; the printed size is under 5,000 KB; total elapsed is under 60 s.

Then inspect the head of the ranked list — **this is the thirty-second payload, and it is the thing the whole project is for:**

```bash
uv run python -c "
import json; d = json.load(open('public/ranked.json'))
print(d['schema_version'], d['town'], d['counts'])
for r in d['lists']['comstock'][:5]:
    print(f\"{r['rank']:2d}. {r['site_addr']:28s} {r['owner'][:34]:34s} \"
          f\"\${r['annual_savings_usd']:>9,.0f}  {r['confidence']}  {r['flags']}\")
print()
print(d['lists']['comstock'][0]['reason'])
print()
for r in d['lists']['modeled'][:5]:
    print(f\"{r['rank']:2d}. {r['site_addr']:28s} {r['use_desc'][:28]:28s} \${r['annual_savings_usd']:>9,.0f}\")
"
```

Paste that output verbatim into the task report.

- [ ] **Step 10: Add `public/` to `.gitignore` except the export**

`public/ranked.json` is a build artifact that the deploy needs. Add to `.gitignore`:

```
# build output — ranked.json is committed, nothing else in public/ is
public/*
!public/ranked.json
```

- [ ] **Step 11: Run the whole suite and commit**

Run: `uv run pytest`
Expected: PASS, all prior counts plus 8 here.

```bash
git add src/shave/export.py scripts/run_pipeline.py docs/ranked-json-schema.md \
        tests/test_export.py .gitignore public/ranked.json
git commit -m "feat: versioned ranked.json export and the one command

Two lists, never merged: the modelled magnitude runs through a published
intensity and a derived load factor, ComStock's through a measured timeseries,
and ranking them against each other in dollars would claim a comparability the
data does not support.

Every row carries the templated one-sentence reason and the published
assumptions travel in the payload, so what the method page states is provably
what the scorer computed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## Task 6: The regression, and publishing the number that could embarrass the tool

Success criterion 3. Report R² of `annual_savings_usd` against `sqft x rate_class`, and against `sqft x rate_class x archetype`. The second will be ≈1.000 by construction, because the score *is* a deterministic function of exactly those three fields. Publish both with the explanation. **Threshold declared in advance: if R² against `sqft x rate_class` alone exceeds 0.90, the archetype layer is adding little and the method page says so plainly.**

**Files:**
- Create: `src/shave/regression.py`
- Create: `docs/regression.md` (generated)
- Test: `tests/test_regression.py` (new)

**Interfaces:**
- Consumes: the scored frame from `pipeline.score_parcels`.
- Produces:
  - `regression.r_squared(y, X) -> float`
  - `regression.design_matrix(scored, with_archetype: bool) -> tuple[np.ndarray, list[str]]`
  - `regression.run(scored) -> dict`
  - `regression.render_markdown(result) -> str`
  - `regression.ARCHETYPE_R2_CEILING: float = 0.90`

- [ ] **Step 1: Write the failing test**

Create `tests/test_regression.py`:

```python
import numpy as np
import pandas as pd
import pytest

from shave import regression


def test_r_squared_is_one_for_an_exact_linear_relationship():
    x = np.arange(50, dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    y = 3.0 * x + 7.0

    assert regression.r_squared(y, X) == pytest.approx(1.0)


def test_r_squared_is_zero_for_a_constant_predictor_against_noise():
    rng = np.random.default_rng(0)
    y = rng.normal(size=200)
    X = np.ones((200, 1))

    assert regression.r_squared(y, X) == pytest.approx(0.0, abs=1e-12)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_regression.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shave.regression'`

- [ ] **Step 3: Write `src/shave/regression.py`**

```python
"""Does the archetype layer earn its place?

Two regressions of the ranking key against the public fields that produce it:

  A. sqft x rate_class              — if this alone explains the ranking, the
                                      archetype library is decoration.
  B. sqft x rate_class x archetype  — this will be about 1.000, because the
                                      score IS a deterministic function of
                                      exactly these three fields.

Publishing B and explaining it is a stronger move than publishing a test that
cannot fail. The tool is a structured prior over three public assessor fields,
not a measurement; B ≈ 1.000 is what that sentence looks like as a number.

A is the one that can hurt. The threshold is declared before running.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: If sqft x rate_class alone explains more than this, the archetype layer is
#: adding little and the method page says so plainly. Declared in advance,
#: which is the only time a threshold means anything.
ARCHETYPE_R2_CEILING = 0.90


def r_squared(y: np.ndarray, X: np.ndarray) -> float:
    """Ordinary least squares R², via lstsq so a rank-deficient design is fine."""
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if y.size == 0:
        return 0.0
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ beta
    ss_res = float(residual @ residual)
    centred = y - y.mean()
    ss_tot = float(centred @ centred)
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot


def design_matrix(
    scored: pd.DataFrame, with_archetype: bool
) -> tuple[np.ndarray, list[str]]:
    """Intercept, sqft, the G-3 indicator, their interaction, and optionally
    one-hot archetype terms interacted with floor area.

    The archetype terms are interacted with sqft rather than entered alone
    because that is how the scorer uses them: an archetype sets an intensity
    per square foot, so its effect is multiplicative in area.
    """
    sqft = scored["sqft"].to_numpy(dtype=float)
    is_g3 = (scored["rate_class"] == "G-3").to_numpy(dtype=float)

    columns = [np.ones_like(sqft), sqft, is_g3, sqft * is_g3]
    names = ["intercept", "sqft", "is_g3", "sqft:is_g3"]

    if with_archetype:
        for name in sorted(scored["archetype"].dropna().unique()):
            indicator = (scored["archetype"] == name).to_numpy(dtype=float)
            columns.append(sqft * indicator)
            names.append(f"sqft:{name}")

    return np.column_stack(columns), names


def run(scored: pd.DataFrame) -> dict:
    """Both R² figures, per source list, plus the declared verdict."""
    results: dict[str, dict] = {}
    for source in ("comstock", "modeled"):
        subset = scored[
            (scored["source"] == source)
            & scored["keep"].astype(bool)
            & scored["unscored_reason"].isna()
        ]
        if len(subset) < 10:
            results[source] = {"n": int(len(subset)), "skipped": "fewer than 10 rows"}
            continue
        y = subset["annual_savings_usd"].to_numpy(dtype=float)
        X_size, _ = design_matrix(subset, with_archetype=False)
        X_full, _ = design_matrix(subset, with_archetype=True)
        r2_size = r_squared(y, X_size)
        results[source] = {
            "n": int(len(subset)),
            "r2_size_and_rate": r2_size,
            "r2_with_archetype": r_squared(y, X_full),
            "archetype_adds_little": bool(r2_size > ARCHETYPE_R2_CEILING),
        }
    return {"ceiling": ARCHETYPE_R2_CEILING, "by_source": results}


def render_markdown(result: dict) -> str:
    """The method page's regression section, including the honest verdict."""
    lines = [
        "# Regression: does the archetype layer earn its place?",
        "",
        "Two ordinary least squares fits of `annual_savings_usd`, the ranking",
        "key, against the public fields that produce it. Run on kept rows only,",
        "each source list separately.",
        "",
        "| List | n | R² vs sqft x rate class | R² vs sqft x rate class x archetype |",
        "|---|---:|---:|---:|",
    ]
    for source, r in result["by_source"].items():
        if "skipped" in r:
            lines.append(f"| {source} | {r['n']} | — | — |")
            continue
        lines.append(
            f"| {source} | {r['n']:,} | {r['r2_size_and_rate']:.3f} | "
            f"{r['r2_with_archetype']:.3f} |"
        )
    lines += [
        "",
        "**The second column is ≈1.000 by construction and that is not a",
        "finding.** The score is a deterministic function of exactly three",
        "public assessor fields: use code, building area, municipality. A",
        "regression on those three fields recovers it perfectly because there",
        "is nothing else in it. This tool is a structured prior over public",
        "data, not a measurement. Publishing that number and explaining it is",
        "more honest than publishing a test that cannot fail.",
        "",
        "**The first column is the one that can hurt.** If floor area and rate",
        f"class alone explain more than {result['ceiling']:.2f} of the spread,",
        "the archetype library is decoration and the ranking is a size sort",
        "wearing a load profile. The threshold was declared before the numbers",
        "were computed.",
        "",
    ]
    for source, r in result["by_source"].items():
        if "skipped" in r:
            continue
        if r["archetype_adds_little"]:
            lines.append(
                f"**{source}: the archetype layer is adding little.** R² of "
                f"{r['r2_size_and_rate']:.3f} against size and rate class alone is "
                f"above the {result['ceiling']:.2f} threshold declared in advance. "
                "Read this list as close to a size sort."
            )
        else:
            lines.append(
                f"**{source}: the archetype layer adds spread.** Size and rate "
                f"class alone explain {r['r2_size_and_rate']:.3f}; the load shape "
                "accounts for the rest of the ordering."
            )
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the first two tests**

Run: `uv run pytest tests/test_regression.py -v`
Expected: PASS

- [ ] **Step 5: Write the behavioural tests**

Append to `tests/test_regression.py`:

```python
def _frame(n=60, seed=0):
    rng = np.random.default_rng(seed)
    sqft = rng.uniform(5_000, 80_000, n)
    archetype = rng.choice(["warehouse", "strip_mall", "small_office"], n)
    intensity = pd.Series(archetype).map(
        {"warehouse": 1.8, "strip_mall": 9.1, "small_office": 3.9}
    ).to_numpy()
    peak = sqft * intensity / 1000.0
    return pd.DataFrame({
        "sqft": sqft,
        "archetype": archetype,
        "source": "comstock",
        "rate_class": np.where(peak >= 200.0, "G-3", "G-2"),
        "annual_savings_usd": peak * 40.0,
        "keep": True,
        "unscored_reason": pd.Series([None] * n, dtype=object),
    })


def test_archetype_terms_raise_r_squared_when_shape_matters():
    """Three archetypes with different intensities: size alone cannot explain
    the spread, and adding the archetype must close the gap."""
    scored = _frame()

    result = regression.run(scored)["by_source"]["comstock"]

    assert result["r2_with_archetype"] > result["r2_size_and_rate"]
    assert result["r2_with_archetype"] == pytest.approx(1.0, abs=1e-6)


def test_the_verdict_fires_when_size_alone_explains_everything():
    """One archetype, so savings are a pure function of size. The declared
    threshold must trip, and the rendered page must say so."""
    scored = _frame()
    scored["archetype"] = "warehouse"
    scored["annual_savings_usd"] = scored["sqft"] * 0.5

    result = regression.run(scored)
    assert result["by_source"]["comstock"]["archetype_adds_little"] is True
    assert "adding little" in regression.render_markdown(result)


def test_a_short_list_is_skipped_rather_than_fitted():
    scored = _frame(n=4)
    assert "skipped" in regression.run(scored)["by_source"]["comstock"]


def test_unscored_and_dropped_rows_are_excluded_from_the_fit():
    scored = _frame()
    scored.loc[scored.index[:10], "keep"] = False
    scored.loc[scored.index[10:20], "unscored_reason"] = "no_floor_area"

    assert regression.run(scored)["by_source"]["comstock"]["n"] == len(scored) - 20


def test_the_rendered_page_always_explains_the_r2_of_one():
    """The ≈1.000 figure is indefensible without the sentence next to it."""
    page = regression.render_markdown(regression.run(_frame()))

    assert "by construction" in page
    assert "structured prior" in page
```

- [ ] **Step 6: Run them**

Run: `uv run pytest tests/test_regression.py -v`
Expected: PASS, all seven.

- [ ] **Step 7: Wire it into the CLI**

In `scripts/run_pipeline.py`, add the import and, after `write_export`, before the timing line:

```python
    from shave import regression

    report = regression.run(scored)
    Path("docs/regression.md").write_text(regression.render_markdown(report), encoding="utf-8")
    payload["regression"] = report
    export.write_export(payload, args.out)
    print("regression:", {k: v.get("r2_size_and_rate") for k, v in report["by_source"].items()},
          file=sys.stderr)
```

Bump `export.SCHEMA_VERSION` to `"1.1.0"` — a field was added — and record the addition in `docs/ranked-json-schema.md`.

- [ ] **Step 8: Run it for real and read the answer**

```bash
uv run python scripts/run_pipeline.py && cat docs/regression.md
```

**There is no pass condition here, and that is the point.** Report whichever number comes out. If `r2_size_and_rate` exceeds 0.90, the verdict text fires and says the archetype layer is decoration — that is a real result about this tool and it goes on the method page as written. Do not adjust the threshold, the design matrix, or the band filter to move it. Note the figure in your task report either way.

- [ ] **Step 9: Run the whole suite and commit**

Run: `uv run pytest`
Expected: PASS, all prior counts plus 7 here.

```bash
git add src/shave/regression.py scripts/run_pipeline.py docs/regression.md \
        docs/ranked-json-schema.md src/shave/export.py tests/test_regression.py public/ranked.json
git commit -m "feat: the regression, including the number that could embarrass the tool

R² against sqft x rate class is the one that can hurt, with the 0.90 threshold
declared before the numbers were computed. R² against sqft x rate class x
archetype is about 1.000 by construction, because the score is a deterministic
function of exactly those three public fields — publishing that and explaining
it beats publishing a test that cannot fail.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015eYTQ8HjDyTM7xUdCGenPU"
```

---

## What this plan deliberately leaves for the next one

Named so nothing is lost, in the order the spec's effort table suggests taking them.

| Deferred | Why it is not here | Est. |
|---|---|---|
| `STRUCTURES_POLY` join — roofprint count, footprint area, `BLD_AREA` fallback | Independent of scoring. Worcester has exactly one parcel with no floor area, so the fallback unblocks one row today; it matters when New Bedford and Chicopee land. | 2.5h |
| Siting screen — simplify, merge collinear, offset, longest clear wall run and bearing | Needs the roofprints above. Pure Shapely, no dependency on anything in this plan. | 2h |
| The static site, method page, encoding map, address box | Consumes `ranked.json`, which this plan defines and versions. `DESIGN.md` and the approved mockup are already in the repo. | 13-14h |
| Occupant resolution for the top 50 | Needs a stable top 50, which is this plan's output. The spec calls it non-deferrable *for the demo*; it is not a prerequisite for anything else. | 3h |
| MECOLS normalized-shape check | `MECOLS.xlsx` is **not on disk** despite the spec recording it as downloaded. Re-fetch before scheduling this. | 1h + fetch |
| New Bedford and Chicopee | The pipeline is already municipality-parameterised via `--dir` and `--town-id`. Each town needs an L3 download and a crosswalk pass over its use codes. `build_archetype`'s `county_gisjoin` defaults to Worcester County and must be passed per town: New Bedford is Bristol County, Chicopee is Hampden. | 2h |
| Deploy: Cloudflare Worker with static assets | Nothing to serve until the site exists. | 2h |

**Two open items this plan does not resolve, carried from the spec's own list.** Neither blocks any task above. (1) Cabinet count — one Powerblock or two — moves `RATED_POWER_KW` and `NAMEPLATE_ENERGY_KWH`, which are already config, so the answer is a one-line change; Task 4's `power_limited` flag now identifies exactly which sites the answer would change. (2) The EWELD licence: `modeled.SHAPE_PARAMS` is the swap point, and nothing else changes when measured values land.

---

## Outside voice, and what it changed

An independent review of the *spec* by `opencode/muse-spark-1.3-contributor-free` was dispatched during the previous session and recorded as having produced nothing. It had in fact produced five findings; the process detached before they were read. They are recovered here with their disposition, because four of them argue for choices this plan already makes and one of them is a real bug that had to be locked down.

| # | Finding | Disposition |
|---|---|---|
| 1 | The load-duration tabulation interpolates a convex piecewise-linear `f(τ)` between sparse samples, which **overestimates** the required threshold — a bias, not noise — and the error is amplified by `A = sqft/1000`, so 0.01 in τ is 5 kW and several hundred dollars on a large site, enough to flip ranks. | **Moot, and it corroborates.** The tabulation is not built. Global Constraints already forbid it on runtime grounds; this is a second, independent reason. Recorded so that a future plan tempted by it inherits the objection. |
| 2 | Building against live `s3://oedi-data-lake` over DuckDB httpfs from a laptop is slow, flaky and non-reproducible, and could eat the budget on its own. | **Already mitigated, and this plan keeps it that way.** `build_archetype` caches each archetype's reduced profile to local parquet; the network is touched once per (archetype, county). Task 1's re-warm is 195 reads, once. No task scores off live S3. |
| 3 | Cut the Supabase / PostGIS / Hyperdrive / trigram stack: a precomputed static ranking needs no server database, and that is hours spent on something nobody asked for. | **Agreed and deferred.** Nothing in this plan touches a database. The deferral table keeps the address box as a static prebuilt index, which is what the design review had already concluded. |
| 4 | `shaveable = L_peak(month) − T_month` is a 2× overstatement whenever `L_peak` is not the *billed* peak. A Saturday overtime spike or a 3 a.m. compressor start is unbilled; subtracting a weekday threshold from it claims a reduction in a charge that was never levied. | **The one real bug, and it is already closed — but nothing was asserting it.** Both reducers mask to billed intervals before taking a monthly maximum, so the code is correct today. Task 1 step 1 pins that the overnight spike reaches `offpeak_max_kw` and not `monthly_peak_kw`; Task 4 step 5 adds `test_shaveable_is_measured_against_the_BILLED_peak_only`, which fails if either reducer ever stops masking. |
| 5 | The architecture is self-contradictory: "nothing on the request path may require the DB" alongside `/api/lookup` hitting Supabase through Hyperdrive. After seven idle days the lookup — the interactive thing the reader clicks — spins or fails while Postgres takes a minute or two to unpause. | **Valid, out of scope here, carried forward.** It belongs to the site plan. Noted in the deferral table so the static index ships as the primary path rather than as a fallback. |

The two findings that survive into future work — 1 and 5 — are the ones about parts not yet built. That is the useful shape for a review to have.

## Self-Review

**Spec coverage.** Against the spec's Stage 1 list: step 4 (archetype library) is completed by Tasks 1 and 3; step 5 (scoring function — monthly loop, root-find, band filter, confidence tiers) by Task 4; step 8 (the regression) by Task 6; the versioned export contract and staged-table intent from "Implementation Architecture" by Task 5. Steps 1 and 2 (the L3 join and `BLD_AREA` handling) were completed by the prior plan. Steps 3, 3b, 6, 7, 9, 9b and 9c are deferred and tabled above with reasons. Success criteria 3 and 5 are met here; 1, 2, 6 and 7 belong to the deferred site work; 4 is blocked on a missing file and is tabled.

**Two spec deviations, both deliberate and both stated in the task that makes them.** The load-duration tabulation is not built, because the measured runtime is 2.1 s against an estimate that assumed the scorer would see 35,040 points per parcel-year rather than 624 — the `Archetype` seam already delivered that saving. And the representative is chosen by median peak intensity over a 15-building spread sample rather than by median annual load factor over the full cohort, because load factor needs every building's timeseries; the selection criterion changes, the intent — a cohort-typical building, citable by id — does not.

**One addition the spec does not contain:** Task 2's multi-meter predicate. It follows directly from the spec's own "parcel ≠ meter problem" section, which names the failure and mitigates it only through ownership and size predicates that a single-owner strip mall passes cleanly.

**Placeholder scan:** clean. Every code step carries the code. Every test step carries the test. The two steps with no pass/fail condition — Task 4 step 7's top-ten composition and Task 6 step 8's R² — say explicitly that the result is to be reported, not engineered, and say why.

**Type consistency:** `ReducedProfile.offpeak_max_kw` (Task 1) is read by `ComStockArchetype.offpeak_max` (Task 1) and by `pipeline.score_parcel` (Task 4) through the `Archetype` protocol, which `ModeledArchetype` satisfies via Task 3 step 9 and `FixtureArchetype` via Task 1 step 11. `crosswalk.CrosswalkRow.multi_meter` (Task 2) reaches `ingest.PREDICATES` and `OUTPUT_COLUMNS` in the same task. `modeled.SHAPE_PARAMS` and `assumptions.ELECTRIC_INTENSITY_KWH_PER_SQFT_YR` are keyed identically and Task 3 step 7 asserts that, plus their joint coverage of `crosswalk.MODELED_TYPES`. `pipeline.ScoredRow`'s field names are consumed verbatim by `export.build_export` and `regression.design_matrix`; `export.PARCEL_FIELDS` names only columns that `ingest.OUTPUT_COLUMNS` produces, plus the `lon`/`lat` pair that `scripts/run_pipeline.py` adds before calling it.
