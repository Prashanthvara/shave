# Spec coverage — what is built, what is pending

**Reviewed 2026-09-13** against the design doc produced by `/office-hours`:
`~/.gstack/projects/powertown/pjay-unknown-design-20260910-091501.md`

Live: **https://shave.pjayav.workers.dev** · Repo: **https://github.com/Prashanthvara/shave**

| | |
|---|---|
| Commits | 40 |
| Source | 5,045 lines across 11 modules, plus `app.js` / `app.css` |
| Tests | **1033 Python** (4 network-marked, deselected) + **60 render** |
| Live response | index + `ranked.json` in **0.21 s** |
| Coverage of spec stages | **9 of 12 numbered steps complete**, 1 partial |
| Success criteria | **7 of 7** |

> The Python suite scores Worcester once per session (`tests/conftest.py`). It used to re-run the 2,099-parcel pipeline in seven separate tests.

---

## Stage 0 — complete

| Step | State | Evidence |
|---|---|---|
| 0. Pull real `USE_CODE` counts; build `crosswalk.csv` (~40 rows); 900-series as its own branch | ✅ | **95 rows** in `src/shave/crosswalk.csv`, `source` visible per row (50 comstock / 16 modeled / 29 excluded), 900-series present, 2 collapse points flagged |

The spec calls this file *"the domain judgment the role is hiring for — show it."* It is committed
and browsable, which is success criterion 5.

---

## Stage 1 — 8 of 9 complete, 1 partial

| # | Spec step | State | Notes |
|---|---|---|---|
| 1 | MassGIS L3, `TaxPar`+`Assess` joined on `LOC_ID` one-to-many, collapse rule | ✅ | 2,099 scoreable Worcester parcels from 47,675 assessor records. **1 town of 3.** |
| 2 | `BLDG_AREA` null/zero handling; fall back to roofprint × stories; drop to LOW | ✅ | Missing floor area falls back to roofprint area × recorded stories (one when none is recorded) and drops to LOW with reason floor_area_from_roofprint. No Worcester parcel with a polygon needs it today; the test pins that at zero. |
| 3 | `STRUCTURES_POLY` join: roofprint count, footprint area, siting geometry | ✅ | MassGIS STRUCTURES_POLY joined by representative point: 1,541 of 2,098 mapped parcels hold one roofprint, 370 several, 187 none. Feeds the single_roofprint predicate (exported HIGH 121 → 87) and the siting screen. |
| 4 | Archetype library; pin release, upgrade, weather year; individual buildings not aggregates | ✅ | `comstock_amy2018_release_2`, `upgrade=0`, `timeseries_individual_buildings`. 13 archetypes cached. ComStock `sqft` vs `BLDG_AREA` mismatch documented in `comstock.py`. |
| 5 | Scoring: monthly loop, root-find, band filter, confidence tiers | ✅ | 737 kept, 172 sweet spot. Seven confidence predicates. |
| 6 | MECOLS calibration check vs published G-2/G-3 class shapes | ✅ | Ran against MECOLS.xlsx (2025) with the criterion committed in 8d1e979 before the first run. G-2 does not pass, G-3 does not pass; figures on the method page. |
| 7 | **Occupant resolution, top 50** — *"this is the demo; it does not get cut"* | ⚠️ **4 of 50** | Both ranked-list heads are resolved, so criterion 2 holds. The method page reports the real figure, not the target. |
| 8 | The regression | ✅ | See criterion 3 below. |
| 9 | Static site: ranked table → detail drawer → method page | ✅ | Ranked table → drawer (24-hour worst billed day with the billed window shaded, source label, confidence tier and failed predicates, lineage) → method page. Siting line: longest clear wall and bearing, or a stated screen-out. |

**Additionally shipped, from the design review rather than the numbered list:**

| | State |
|---|---|
| **D2 — the encoding map** (fill opacity = saving, outline = rate class, cross-linked both ways) | ✅ merged and live, with the hatched wall run on the selected parcel |
| **D4 — the reason is inline, never behind a click** | ✅ rank 1 selected on load, reason in the first frame |

---

## Stage 2 — 1 of 3, and one of the other two is correctly unbuilt

| # | Spec step | State |
|---|---|---|
| 10 | Address box, promoted to Stage 1 by D5 as "the verification moment" | ✅ static index over every screened parcel, no database. Loaded on first search. |
| 11 | Agent enrichment over the top 50 | ❌ |
| 12 | Supabase/PostGIS + Worker API **"only if something actually needs it"** | ❌ — **correctly.** Nothing needs it, and an outside review of the spec argued to cut the whole stack. The site is assets-only with no Worker script at all. |

---

## Success criteria — 7 of 7

| | Criterion | State | Evidence |
|---|---|---|---|
| 1 | Public URL, ranked list under 3 s, no signup | ✅ | **0.21 s** measured (index 0.08 + `ranked.json` 0.13). No credential on any route. |
| 2 | Top-ranked site is a real, named MA operating business with a checkable reason | ✅ | ComStock list: RK Worcester Crossing (Walmart Supercenter anchor). Modelled list: UMass Chan Medical School. Both sourced and dated. |
| 3 | Both R² figures, published with the explanation, 0.90 threshold declared in advance | ✅ | comstock **0.614 → 0.878** (n=528), modeled **0.493 → 0.749** (n=209). Both under the ceiling, so the archetype layer earns its place. |
| 4 | MECOLS normalized-shape sanity check | ✅ | Ran against MECOLS.xlsx (2025) with the criterion committed in 8d1e979 before the first run. G-2 does not pass, G-3 does not pass; figures on the method page. |
| 5 | Crosswalk CSV browsable, `modeled` vs `comstock` visible per row | ✅ | |
| 6 | Method page states what the tool cannot do | ✅ | Limitations including the spec's six verbatim and the siting screen's blind spots, plus 3 named gaps. |
| 7 | Stage 2: paste an address in a covered town, get a dossier | ✅ | Worcester. Exact, approximate and uncovered-town answers; every exported row is found by its own address (`test_addresses.py`). |

### A note on criterion 3

The spec predicted the second R² would be **≈1.000 by construction**. It is **0.878**. The rendered
page originally asserted the predicted figure above a table showing the real one; that was corrected.
The gap is arithmetic, not hidden information: the fit is linear in floor area within an archetype
and the scorer is not, because shaveable kilowatts come from a root-find against a fixed energy
budget and a 250 kW power cap. A site large enough to saturate the cap stops scaling with its floor
area, and a straight line cannot follow that kink.

---

## The spec's test plan — 8 of 9 areas covered

| Area | State |
|---|---|
| `billing_window` — weekday, weekend, 9 holidays, observed-day shift | ✅ 33 tests |
| `archetype` — both impls satisfy the interface; modelled varies by day-type, season, jitter | ✅ 35 + 17 tests |
| `scorer.shave_threshold` — flat load, energy bound, power bound, **property test on monotonicity**, `shaveable_kw >= 0` | ✅ within 41 scorer tests |
| `scorer.monthly_billed_demand` — month with zero billed days | ✅ |
| `scorer.assign_rate_class` — 200 kW boundary **and the spec's mandatory regression** | ✅ `test_REGRESSION_rate_class_uses_12mo_average_not_annual_peak` |
| `scorer.recharge_feasible` — "both predicates independently" | ⚠️ **deliberately superseded** — see divergences |
| `siting` | ✅ zero-lot-line, footprint ≈ parcel, collinear merge, obstruction, straddling roof, real top-ranked sites (test_siting.py) |
| `export` — schema version present, payload under the cap | ✅ 11 tests |
| Worker E2E — cold load < 3 s; Supabase paused → static fallback; address outside covered towns; malformed export | ⚠️ cold load verified by hand, not automated. One path is moot (no Supabase). The address box's outside-covered-towns path is tested in render.test.js. The malformed-export path exists in `app.js` as a major-version refusal but has no test. |

Per-file test counts: `ingest` 62, `crosswalk` 46, `scorer` 41, `comstock` 35, `billing_window` 33,
`render.test.js` 31, `modeled` 17, `export` 11, `method` 11, `occupants` 11, `mapgeo` 10,
`site_data` 10, `pipeline` 9, `regression` 8, `assumptions` 6.

---

## Pending, in recommended order

| # | Item | Est. | Why this order |
|---|---|---|---|
| 1 | **Occupant resolution, 46 remaining** | 3h, human | Spec calls it non-deferrable. `/tmp/worksheet.csv` carries them with addresses and dollar values; the ratchet in `tests/test_occupants.py` rises as they land. |
| 2 | **New Bedford and Chicopee** | 2.5h | Each needs an L3 download, a crosswalk pass, its own `county_gisjoin` (Bristol, Hampden), and `scripts/fetch_structures.py --town-id`. The municipality control is built for them. |

---

## Deliberate divergences from the spec

Each was measured, recorded in an SDD ledger, and is stated on the method page where a reader
would otherwise be misled.

**1. The recharge headroom predicate was removed.** The spec specifies
`L_offpeak_max + charger_kW < T_month`. That compares an **unbilled** quantity against a **billed**
threshold: the tariff bills the greatest fifteen-minute peak during 08:00–21:00 on weekdays, so
overnight load is never billed at any magnitude and charging cannot create a billed peak. Measured,
it failed **661 of 737** kept rows, and 300 of 300 sampled failed on it alone — not because the
recharge was large (37.6 kW against a 250 kW charger) but because most commercial buildings draw
more overnight than the daytime level they shave to. The flag now fires on 0 rows and the ranking is
unchanged either side of the change.

**2. Representative selection is by median peak intensity, not median annual load factor.** Load
factor needs every building's timeseries — 3,595 reads for MA. A 15-building spread sample per
archetype preserves the intent (a cohort-typical building, citable by id) at 195 reads. The original
median-floor-area rule had picked a SmallOffice at 12.3 W/sqft against a cohort median near 3.9,
inflating 231 parcels roughly threefold; the corrected pick is 4.9.

**3. No load-duration tabulation.** The spec specifies it for performance against an estimate of
~70M bisections. Measured, the whole of Worcester scores in ~2 s, because the `Archetype` seam hands
the scorer 52 points per month rather than 35,040 per year. An outside review independently found
the tabulation would introduce a directional bias, which corroborates not building it.

**4. `peak_kw` means the true 24-hour annual peak, not the billed peak.** Scaling the billed window
against a window-only maximum treated an unbilled peak as billed and inflated billed demand 1.55×
for machine shops (06:30 shift start) and 1.22× for cold storage (06:00) — 227 parcels, the core of
the published ICP.

**5. The two ranked lists are never merged, and the approved mockup is wrong on this point.** The
spec forbids it twice; the mockup defaults to a merged "All sources" view. The spec wins, and the
page states on screen why the two dollar figures are not comparable.

**6. The map's fill encodes saving as designed, but parcel area was neutralised.** Area was acting
as an unspecified third channel correlated with floor area, so the picture said "big is good" twice.
Sweet-spot parcels spanned a median 4.3 SVG units against 7.8 for everything else, and 74 of 172
rendered under 4 units — effectively invisible. Parcels below 9 units are now grown about their own
centroid (position exact, only drawn size changes) and the legend discloses it.

**7. The drawer's day chart is twenty-four hours wide but only thirteen hours deep.** The spec
asks for a 24-hour load sparkline. The measured half's cache keeps the 52 billed intervals and
the month's overnight maximum, not the overnight shape, and re-reading 13 timeseries from S3
for a line the tariff never bills was not worth a network dependency in the build. The chart
draws the billed intervals as a line, the overnight maximum as a dashed line labelled unbilled,
and the method page says so.

**8. The wall run is drawn for the selected parcel only.** D2 lists a hatched wall segment
as a map channel. At 620 SVG units across Worcester one unit is about 17 m, so the median
exported clear run of 138 ft draws about 2.4 units long; hatching every parcel's wall at
once is noise, not a channel. The mark appears on the selected parcel, grown with it when
the parcel is drawn at its minimum size, and the legend says so.

**9. `clear` is named for what it is.** The spec asks for the continuous fact rather than a
boolean. The status field has four values — `clear`, `screened_out`, `no_roofprint`,
`no_geometry` — and `clear` is defined everywhere it appears as "not screened out", never
as suitable.

**10. The class-shape check does not pass for G-2 and G-3.** Hour of peak matched in 0 of 12 months and load
factor in 0 of 12 for G-2, and 7 of 12 and 0 of 12 for G-3, against a criterion declared before the first run. It is published as a finding: the
aggregate sums each archetype's worst billed day, which a diversified class average does not, and the
criterion was not loosened after the result was seen.

---

## Correctly out of scope throughout

Statewide coverage · electrical permits (no statewide MA database) · FEMA flood zones · Clean Peak
and ConnectedSolutions revenue numbers (the coincident/non-coincident tension is named, never
quantified) · interconnection feasibility · per-feeder constraints · underwriting · the Transmission
Coincident Peak Demand Charge and ISO-NE ICAP tag (both named as omissions) · municipal light plants
· Supabase/PostGIS on the request path.
