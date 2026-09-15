"""Parcels in, scored rows out.

Every component this calls is already tested in isolation. What lives here is
only the joining: which archetype a parcel gets, the monthly loop over it, and
the flags that say how far to trust the answer.

The monthly loop is a deliberate approximation and it is stated on the method
page. The tariff bills the monthly maximum, and the threshold that matters is
the one holdable on EVERY billed day of the month. The Archetype protocol
exposes one day per month -- that month's worst -- so `T_month` here is the
threshold for the peak day alone. It is the right day to pick if you may pick
only one, because it carries the month's highest peak and therefore, for these
shapes, its highest threshold. It is not a proof.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from shave import comstock, crosswalk, modeled, scorer, towns
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
    offpeak_max_kw: float
    months_at_power_cap: int
    #: The month the battery works hardest, 1-12, and that month's worst billed
    #: day inside the peak window. This is the day the drawer draws. 0 and ()
    #: on an unscored row: there is no day to draw, and inventing one is worse.
    peak_day_month: int
    peak_day_kw: tuple[float, ...]
    #: The level the battery holds that day's billed peak to.
    peak_day_held_kw: float
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
        e_used_kwh=e_used, offpeak_hours=OFFPEAK_HOURS
    )
    # Carried as evidence, not as a constraint. Overnight load is unbilled
    # under this tariff, so it cannot veto a recharge -- but it is the number
    # a reader needs to check that claim, and it is what a service-capacity
    # question would start from.
    offpeak_max_kw = float(archetype.offpeak_max(worst + 1))

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
        offpeak_max_kw=offpeak_max_kw,
        months_at_power_cap=months_at_cap,
        peak_day_month=worst + 1,
        peak_day_kw=tuple(
            round(float(v), 1) for v in archetype.peak_day_window(worst + 1)
        ),
        peak_day_held_kw=round(float(peaks[worst] - shaveable[worst]), 1),
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
        offpeak_max_kw=0.0,
        months_at_power_cap=0,
        peak_day_month=0,
        peak_day_kw=(),
        peak_day_held_kw=0.0,
        unscored_reason=reason,
    )


def default_archetype_factory(parcel: Mapping) -> Archetype:
    """The archetype for one parcel. Raises for anything unscoreable."""
    name = str(parcel["archetype"])
    sqft = float(parcel["sqft"])
    if str(parcel["source"]) == "comstock":
        if name == "office":
            # Defensive. `ingest._resolve_office_bands` already resolves the
            # office family before a parcel reaches here -- Worcester's output
            # contains small_office, medium_office and large_office and no bare
            # "office" -- but resolving it in one place only means a future
            # caller that skips ingest gets a ComStockError instead of a band.
            name = crosswalk.resolve_office_band(sqft)
        return comstock.build_archetype(
            name, sqft, county_gisjoin=towns.county_for(parcel.get("town_id"))
        )
    return modeled.build_modeled_archetype(name, str(parcel["loc_id"]), sqft)


def score_parcels(
    gdf: pd.DataFrame,
    archetype_factory: Callable[[Mapping], Archetype] | None = None,
) -> pd.DataFrame:
    """Score every parcel. One row out per row in, scored or named unscored.

    The archetype cache means one S3 round trip per archetype, not per parcel,
    so this is a loop over ~2,100 parcels that completes in seconds. Measured
    at 2.1 s for Worcester's 1,446 ComStock rows.

    No caching layer here on purpose: `comstock.build_archetype` already caches
    to local parquet and `modeled.build_modeled_archetype` is pure computation.
    A second cache would only be a second thing to invalidate.
    """
    build = archetype_factory or default_archetype_factory
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

    return pd.DataFrame([asdict(r) for r in rows])
