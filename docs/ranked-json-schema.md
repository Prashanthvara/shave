# `ranked.json` — the written contract

This document and `export.SCHEMA_VERSION` change together. It is the only interface between
the Python pipeline and anything that renders it.

**Current version: `1.2.0`**

## Versioning rule

- **MINOR** for an added field. A consumer that ignores unknown fields keeps working.
- **MAJOR** for a removed field or a changed type. A consumer must refuse to render a payload
  whose major version it does not recognise, rather than drawing wrong numbers from a shape it
  half-understands.

A stale deploy is the failure this exists to prevent: the page checks the major version before
it draws anything.

**1.2.0** — row *selection* widened. Each list now carries the top `TOP_N` rows
by dollars plus up to `SWEET_SPOT_N` sweet-spot rows, de-duplicated and still
ordered by dollars. No field was added, removed or retyped, so a 1.1.0 consumer
keeps working; the list is simply longer and complete for the sweet-spot view.

## Why there are two lists and not one

`lists` has exactly two keys, `comstock` and `modeled`, each ranked on dollars **within itself**.
They are never merged and their ranks restart from 1.

A ComStock magnitude comes from a measured 15-minute timeseries for a real building. A modelled
magnitude comes from a published electricity intensity divided by a load factor derived from a
declared shape — two modelling steps deeper. Ranking the two against each other in dollars would
claim a comparability the second one does not have. The spec states this twice; `test_export.py`
asserts it.

## Top-level keys

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | string | Semver of this contract. |
| `generated_at` | string | UTC ISO-8601 timestamp, seconds precision, of the build. |
| `town` | object | `{name, town_id, assess_fy}`. `assess_fy` is the assessor fiscal year of the extract, which differs by municipality and is the vintage of every floor area in the payload. |
| `counts` | object | See below. |
| `assumptions` | array | Every row of `assumptions.PUBLISHED`, as `{key, value, provenance, source, note}`. Travels with the payload so the published assumptions are provably the computed ones. |
| `lists` | object | `{comstock: [row], modeled: [row]}`. |
| `regression` | object | *Added in 1.1.0.* `{ceiling, by_source}` — the two R-squared figures per list and the verdict against the threshold declared in advance. See `docs/regression.md`. |

### `counts`

| Key | Type | Meaning |
|---|---|---|
| `parcels_in` | int | Rows the pipeline was given. Every one is accounted for. |
| `scored` | int | Rows that produced a score. |
| `unscored` | object | Reason → count. A parcel that cannot be scored is carried with a named reason, never dropped. |
| `kept` | int | Rows above the demand floor. |
| `sweet_spot` | int | Rows on the expensive G-2 rate with a spiky shape. |
| `exported` | object | List name → rows actually written, after `TOP_N`. |

## Row fields

Every row carries the fields of `pipeline.ScoredRow`, the parcel fields lifted from the assessor
record, and two added by the export.

### Identity and provenance

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `loc_id` | string | — | MassGIS standardised parcel identifier. Stable across assessor vintages. |
| `prop_id` | string | — | The town's own parcel id. |
| `rank` | int | — | Position within this list. Restarts at 1 per list. |
| `site_addr`, `city`, `zip` | string | — | Street address from the assessor record. |
| `owner` | string | — | **Owner of record, not the operating business.** For leased commercial property this is a realty trust or an LLC. |
| `use_code`, `use_desc` | string | — | Massachusetts assessor use code and its description. |
| `icp_sector` | string | — | Which published ICP sector this use code maps to, blank if none. |
| `assess_fy` | int | year | Fiscal year of the assessor extract. |
| `archetype` | string | — | The load-shape archetype the crosswalk resolved. |
| `source` | string | — | `comstock` (measured) or `modeled` (synthesised). |
| `reason` | string | — | The templated one-sentence argument. Every quantity in it appears elsewhere on the row, which is what makes it checkable. |

### Load and money

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `sqft` | float | sq ft | Building floor area. The entire scale factor. |
| `monthly_billed_demand_kw` | float[12] | kW | Billed demand per month — the greatest fifteen-minute peak inside 08:00–21:00 on weekdays. |
| `monthly_shaveable_kw` | float[12] | kW | kW the battery removes from that month's billed demand. |
| `avg_12mo_kw` | float | kW | Mean of `monthly_billed_demand_kw`. **This is the tariff's rate-class test**, not the peak. |
| `peak_kw` | float | kW | Highest monthly billed demand. |
| `peak_to_avg` | float | ratio | Spikiness. Above 1.4 with rate G-2 is the sweet spot. |
| `offpeak_max_kw` | float | kW | Highest load in the 21:00–08:00 window. Carried as evidence, not as a constraint: overnight demand is not billed under this tariff. |
| `rate_class` | string | — | `G-2` or `G-3`, assigned from `avg_12mo_kw` against the 200 kW threshold. |
| `demand_charge_per_kw` | float | $/kW | Distribution demand charge for that rate class. **G-2 is the more expensive rate.** |
| `annual_savings_usd` | float | $/yr | The ranking key. Distribution demand charge only. |
| `shaved_fraction` | float | 0–1 | Mean fraction of billed demand removed. A large site with a small fraction can still rank high on dollars. |
| `months_at_power_cap` | int | — | Months the battery hits its 250 kW rating. |
| `recharge_feasible` | bool | — | Whether the required overnight charge rate is within the charger's capability. |

### Screening and confidence

| Field | Type | Meaning |
|---|---|---|
| `keep` | bool | Above the demand floor. Only `true` rows are exported. |
| `sweet_spot` | bool | G-2 and spiky. |
| `band_reason` | string \| null | Why a row was dropped, when it was. |
| `confidence` | string | `HIGH`, `MED` or `LOW` from six predicates. |
| `confidence_reasons` | string[] | Which predicates failed, by name. |
| `flags` | string[] | `power_limited`, `scale_extrapolation`, `recharge_constrained`, `thin_cohort`. |
| `unscored_reason` | string \| null | Why a parcel could not be scored. Null on every exported row. |

### Geography

| Field | Type | Meaning |
|---|---|---|
| `lon`, `lat` | float | WGS84 representative point of the parcel. A representative point, not a centroid: the centroid of an L-shaped or ring parcel can fall outside it. |

## What is deliberately absent

- **Parcel geometry.** Only a point. Polygon geometry is a MINOR addition when the map lands.
- **The occupant.** Owner of record is in the payload; the hand-resolved operating business is
  added downstream by `site_data.enrich`, because it is a separate, manually maintained table.
