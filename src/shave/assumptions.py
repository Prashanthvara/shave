"""Every number the scorer uses, in one place, with its source.

This module is the single source of truth for the model's constants. The scorer
imports it; the published method page renders from it. That is deliberate: the
project's claim is that it shows its work, and a method page transcribed by hand
would eventually disagree with the code. Here it cannot.

Two kinds of number live here and they are labelled differently:

  FILED    a value read off a filed tariff or a published dataset. Citable.
  ASSUMED  a value we chose. Defensible, but ours. Every one of these is a place
           a domain expert is entitled to push back on.

Nothing else in the codebase should hard-code a physical or tariff constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provenance = Literal["FILED", "ASSUMED", "DERIVED"]


@dataclass(frozen=True)
class Assumption:
    """One constant, with everything needed to publish it."""

    key: str
    value: float | str
    unit: str
    provenance: Provenance
    source: str
    note: str

    def render(self) -> str:
        return f"{self.value} {self.unit}".strip()


# --------------------------------------------------------------------------
# Tariff: National Grid / Massachusetts Electric (MECO)
# Rate summary: nationalgridus.com/media/pdfs/billing-payments/bill-inserts/
#               mae/cm4394_mae_ratesummary.pdf
# Rate G-3 tariff: M.D.P.U. No. 1591, effective 2025-03-31
# --------------------------------------------------------------------------

G2_DEMAND_CHARGE_PER_KW = 15.06
G3_DEMAND_CHARGE_PER_KW = 10.48

# G-3 is mandatory once the 12-month AVERAGE of monthly billed demand reaches
# this, for three consecutive months. Note: the AVERAGE, not the peak. Scoring
# by peak was a real bug caught in review; it pushed spiky mid-size sites (the
# sweet spot) onto the cheaper rate and cut their score by ~30%.
G3_THRESHOLD_KW = 200.0

# A customer may transfer off G-3 below this for three consecutive months.
G3_EXIT_KW = 180.0

# Peak hours, from the filed tariff: "Peak hours will be from 8:00 a.m. to
# 9:00 p.m. daily on Monday through Friday, excluding holidays."
PEAK_HOUR_START = 8
PEAK_HOUR_END = 21

# "The Demand for each month ... shall be the greater of: a) The greatest
# fifteen-minute peak occurring during the Peak hours period within such a
# month as measured in kilowatts, or b) 90% of the greatest fifteen-minute
# peak ... as measured in kilovolt-amperes."
INTERVAL_MINUTES = 15
KVA_CLAUSE_FACTOR = 0.90  # not modelled; recorded so the omission is visible

# --------------------------------------------------------------------------
# Hardware: the Powerblock
# Powertown's spec page headlines "250 kW energy storage" and notes a typical
# deployment of two cabinets in parallel, so the SYSTEM is read as 250 kW /
# 522 kWh. This is unconfirmed and it scales every figure on the page. Ask.
# --------------------------------------------------------------------------

RATED_POWER_KW = 250.0
NAMEPLATE_ENERGY_KWH = 522.0

DEPTH_OF_DISCHARGE = 0.90
ROUND_TRIP_EFFICIENCY = 0.88

# Charging is assumed to happen off-peak at the same rated power.
CHARGER_KW = RATED_POWER_KW


def usable_energy_kwh() -> float:
    """Energy actually available to shave a peak.

    Round-trip loss is charged against discharge, which is the conservative
    convention: it understates delivered energy by ~6% versus splitting the
    loss across charge and discharge. Stated so the choice is visible.
    """
    return NAMEPLATE_ENERGY_KWH * DEPTH_OF_DISCHARGE * ROUND_TRIP_EFFICIENCY


USABLE_ENERGY_KWH = usable_energy_kwh()  # ~413.4 kWh

# --------------------------------------------------------------------------
# Screening bands
# --------------------------------------------------------------------------

# Below this 12-month average there is not enough demand charge to be worth a
# conversation, regardless of shape.
MIN_AVG_DEMAND_KW = 50.0

# A site is "spiky" enough to be interesting when its peak runs this far above
# its own average. Combined with rate_class == G-2 this defines the sweet-spot
# view. Both halves fall out of the tariff rather than being invented windows.
SWEET_SPOT_PEAK_TO_AVG = 1.4

# Single-metering proxy. Demand accrues to a service account, not a building,
# so large multi-tenant buildings are systematically overstated. Known
# conservatism: single-tenant distribution centres routinely exceed this and
# are capped at MED confidence as a result.
LIKELY_SINGLE_METERED_MAX_SQFT = 100_000

# --------------------------------------------------------------------------
# Siting
# --------------------------------------------------------------------------

# Cabinet footprint. 96.5 in is the height, not a plan dimension.
CABINET_WIDTH_IN = 39.4
CABINET_DEPTH_IN = 55.3
CABINET_HEIGHT_IN = 96.5
CABINETS_PER_SYSTEM = 2

# Working-space allowance from the building wall to the parcel line. NFPA 855
# exposure separation for outdoor ESS is on the order of 3 ft; 10 ft is a
# deliberately conservative allowance, not a code citation.
MIN_WALL_CLEARANCE_FT = 10.0

# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------

COMSTOCK_RELEASE = "2024/comstock_amy2018_release_2"
COMSTOCK_UPGRADE = 0
COMSTOCK_STATE = "MA"
COMSTOCK_S3_BASE = (
    "s3://oedi-data-lake/nrel-pds-building-stock/"
    "end-use-load-profiles-for-us-building-stock"
)


def comstock_glob() -> str:
    """S3 glob for MA individual-building timeseries, partition-pruned.

    Verified 2026-09-10: 3,595 MA parquet files reachable anonymously via
    DuckDB httpfs. Pruning on both upgrade= and state= is not optional; without
    it the query scans the national dataset over HTTP.
    """
    return (
        f"{COMSTOCK_S3_BASE}/{COMSTOCK_RELEASE}/timeseries_individual_buildings"
        f"/by_state/upgrade={COMSTOCK_UPGRADE}/state={COMSTOCK_STATE}/*.parquet"
    )


# --------------------------------------------------------------------------
# The published table. Ordering here is the ordering on the method page.
# --------------------------------------------------------------------------

PUBLISHED: tuple[Assumption, ...] = (
    Assumption(
        "g2_demand_charge", G2_DEMAND_CHARGE_PER_KW, "$/kW", "FILED",
        "MECO summary of rates",
        "Rate G-2 distribution demand charge. 44% higher per kW than G-3, "
        "which is why the target band is mid-size rather than large.",
    ),
    Assumption(
        "g3_demand_charge", G3_DEMAND_CHARGE_PER_KW, "$/kW", "FILED",
        "MECO summary of rates",
        "Rate G-3 distribution demand charge.",
    ),
    Assumption(
        "g3_threshold", G3_THRESHOLD_KW, "kW", "FILED",
        "M.D.P.U. No. 1591",
        "G-3 becomes mandatory at this 12-month AVERAGE monthly demand for "
        "three consecutive months. The test is the average, not the peak.",
    ),
    Assumption(
        "peak_window", f"{PEAK_HOUR_START:02d}:00-{PEAK_HOUR_END:02d}:00", "",
        "FILED", "M.D.P.U. No. 1591",
        "Weekdays only, excluding nine observed holidays. Demand outside this "
        "window is not billed, so a 3 a.m. spike is free.",
    ),
    Assumption(
        "interval", INTERVAL_MINUTES, "minutes", "FILED",
        "M.D.P.U. No. 1591",
        "Billing determinant is the greatest fifteen-minute peak.",
    ),
    Assumption(
        "rated_power", RATED_POWER_KW, "kW", "ASSUMED",
        "Powertown spec page",
        "Read as the system rating for two cabinets in parallel. UNCONFIRMED.",
    ),
    Assumption(
        "nameplate_energy", NAMEPLATE_ENERGY_KWH, "kWh", "ASSUMED",
        "Powertown spec page",
        "Read as the system rating. UNCONFIRMED. If it is per-cabinet, every "
        "figure doubles.",
    ),
    Assumption(
        "depth_of_discharge", DEPTH_OF_DISCHARGE, "fraction", "ASSUMED",
        "LFP typical",
        "Not published by Powertown.",
    ),
    Assumption(
        "round_trip_efficiency", ROUND_TRIP_EFFICIENCY, "fraction", "ASSUMED",
        "AC-AC typical",
        "Charged wholly against discharge, which understates delivered energy "
        "by roughly 6% versus splitting the loss.",
    ),
    Assumption(
        "usable_energy", round(USABLE_ENERGY_KWH, 1), "kWh", "DERIVED",
        "nameplate x DoD x efficiency",
        "The real constraint. A six-hour plateau needs far more than this, "
        "which is why large flat loads score badly.",
    ),
    Assumption(
        "min_avg_demand", MIN_AVG_DEMAND_KW, "kW", "ASSUMED",
        "screening floor",
        "Below this there is not enough demand charge to be worth a call.",
    ),
    Assumption(
        "sweet_spot_peak_to_avg", SWEET_SPOT_PEAK_TO_AVG, "ratio", "ASSUMED",
        "screening band",
        "Spikiness floor for the sweet-spot view, applied alongside the "
        "tariff's own G-2 test.",
    ),
    Assumption(
        "wall_clearance", MIN_WALL_CLEARANCE_FT, "ft", "ASSUMED",
        "conservative working space",
        "NFPA 855 exposure separation is on the order of 3 ft. This is a "
        "working-space allowance, not a code citation.",
    ),
    Assumption(
        "comstock_release", COMSTOCK_RELEASE, "", "FILED",
        "NREL OEDI",
        "AMY2018 weather. Pinned: release and weather year change which day "
        "is the peak day, which changes every score.",
    ),
)


def published_rows() -> list[dict[str, str]]:
    """The method-page table, ready to serialise."""
    return [
        {
            "key": a.key,
            "value": a.render(),
            "provenance": a.provenance,
            "source": a.source,
            "note": a.note,
        }
        for a in PUBLISHED
    ]
