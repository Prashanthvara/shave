# Shave

**https://shave.pjayav.workers.dev**


Ranks commercial and industrial buildings in Worcester, Fall River and Lowell
by how much of their monthly billed electrical demand a 250 kW / 522 kWh
battery could actually absorb, and what that saves at the filed tariff rate.

All three are National Grid (Massachusetts Electric) territory, which the
G-2/G-3 tariff requires. `data/town_utilities.csv` is the checkable record.
4,179 parcels screened, 1,450 with enough demand charge to be worth a call.

It scores sites **before** anyone picks up the phone. The industry sequence is
talk, then ask for a utility bill, then decide. This inverts that.

## What it is, and what it is not

This tool has never seen a meter. It is a **structured prior** over three public
assessor fields plus a modelled load-shape library. Its value is that the prior
is non-obvious and cheap, not that it is a measurement.

Use it to order a call list. Do not use it to underwrite a project.

## Why the small building often wins

Two numbers from National Grid's Massachusetts tariff:

| Rate | Eligibility | Distribution demand charge |
|---|---|---|
| G-2 | max demand under 200 kW | **$15.06 / kW** |
| G-3 | 12-month *average* at or above 200 kW | **$10.48 / kW** |

G-2 costs 44% more per kW than G-3. A 180 kW site on G-2 pays more in demand
charges than a 250 kW site on G-3.

Then stack the energy budget. The battery holds 522 kWh nameplate, about 413 kWh
usable, which is roughly two hours at full power. A hospital's monthly peak is a
six-hour plateau and the battery runs flat before it ends. A machine shop's peak
is a twenty-minute inrush at shift start and the battery barely notices.

So the target is a mid-size site with a spiky weekday load, not the biggest
building on the block. That falls out of the tariff and the physics rather than
being asserted.

## Billing determinant

From the filed tariff, M.D.P.U. No. 1591:

> The Demand for each month shall be the greater of: a) The greatest
> fifteen-minute peak occurring during the Peak hours period within such a month
> as measured in kilowatts, or b) 90% of the greatest fifteen-minute peak
> occurring during the Peak hours period, of such month as measured in
> kilovolt-amperes.

Peak hours are 8:00 a.m. to 9:00 p.m., Monday to Friday, excluding nine observed
holidays. A three-in-the-morning spike is free, so every calculation here runs
inside that window and nowhere else.

## Layout

```
src/shave/
  assumptions.py     every constant, with source and provenance. The method
                     page renders from this file, so published values cannot
                     drift from computed ones.
  billing_window.py  the tariff calendar. Nine holidays, observed-day shifts,
                     vectorised interval mask.
  scorer.py          root-find for the shave threshold, monthly-max loop,
                     rate class, recharge feasibility, annual saving.
  archetype.py       one interface over two load-shape sources: measured
                     (NREL ComStock) and modelled (industrial synthesis).
```

## Data sources

- **MassGIS L3 Standardized Assessors' Parcels** and **STRUCTURES_POLY** roofprints
- **NREL ComStock** end-use load profiles, queried in place from `s3://oedi-data-lake`
- **National Grid MECO** filed tariff and published class average load shapes

The code here is MIT licensed. The data is not mine to license: each source
above keeps its own terms, and the assessor extracts and the ComStock cache
are downloaded at build time rather than redistributed from this repository.

## Known limits

- Multi-tenant buildings are overstated. Demand accrues to a service account, not
  a building.
- Industrial load shapes are modelled, not measured. ComStock covers 14 commercial
  building types and explicitly excludes laboratories, data centers and ice rinks.
  That is the weakest link and it is not close.
- The siting screen rules out the impossible. It cannot see loading docks, fire
  lanes or egress.
- Assessor vintage differs by municipality. Two towns in the same ranking are not
  necessarily measured in the same year.
- Only the distribution demand charge is counted. Transmission is billed per kWh,
  and the ISO-NE capacity tag sits outside this model.

## Development

```sh
uv sync
uv run pytest
```

### Rebuilding the published page

    uv run python scripts/build_site.py     # every covered town, about 60 s
    NB="$HOME/.nvm/versions/node/v22.18.0/bin"
    "$NB/npx" wrangler dev                  # serve it locally on :8787
    "$NB/npx" wrangler deploy               # publish

It writes, under `public/data`:

    index.json                   the towns, their counts, and the default
    towns/<slug>/ranked.json     one enriched export per town, in its own map frame
    method.json                  one method payload over all towns
    addresses.json               one address index over all towns

The page loads `index.json` first, then one town at a time. Towns are never
merged into a single ranked list, for the same reason the two source lists are
not: each town ranks within itself and draws its own map frame.

`data/raw/` holds the MassGIS L3 extract and is gitignored, so a fresh clone
must download it before the pipeline will run. `data/interim/comstock/` is the
cached ComStock profile per archetype; delete it and
`scripts/warm_comstock_cache.py` refetches from S3, about six minutes.

`node`, `npm` and `npx` are nvm shell functions here, so `export PATH` does not
reach them, because a shell function takes precedence over a PATH lookup. Call the
binaries by absolute path, as above.

The full test suite takes about 75 seconds: several integration tests re-run
the whole 4,179-parcel pipeline end to end rather than working from fixtures.
Each town is scored once per session and shared (`tests/conftest.py`).
