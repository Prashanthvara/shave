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

#: Hours in a non-leap year. The annual-intensity to peak-kW conversion
#: divides by this; using 8784 in a leap year would move every modelled
#: magnitude by 0.3%, which is far inside the error of the intensity itself.
HOURS_PER_YEAR = 8760.0
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
# Every figure below was read out of the source workbook and re-derived on
# 2026-09-11, not quoted from memory:
#
# CBECS 2018 Table C22, "Electricity consumption totals and conditional
#   intensities by building activity subcategories, 2018" (released December
#   2022), column "Site electricity consumption / Per square foot (kWh)":
#   eia.gov/consumption/commercial/data/2018/ce/xls/c22.xlsx
# MECS 2018 Table 3.2 "Fuel Consumption, 2018", column "Net Electricity(b)",
#   trillion Btu (released February 2021), over Table 9.1 "Enclosed
#   Floorspace", million square feet (released September 2021):
#   eia.gov/consumption/manufacturing/data/2018/xls/Table3_2.xlsx
#   eia.gov/consumption/manufacturing/data/2018/xls/Table9_1.xlsx
# --------------------------------------------------------------------------

BTU_PER_KWH = 3412.0

ELECTRIC_INTENSITY_KWH_PER_SQFT_YR: dict[str, float] = {
    # MECS NAICS 332 Fabricated Metal Products: 124 trillion Btu net
    # electricity over 1,530 million sq ft = 23.75. NAICS 333 Machinery:
    # 80 over 1,021 = 22.96. The machine shops and metal fabricators of
    # Worcester are 332/333; the mean of the two, 23.36, is the anchor.
    "industrial_manufacturing": 23.4,
    # CBECS C22 "Refrigerated" (under Warehouse and storage), 29.6 kWh/sq ft.
    # Cold storage is the ICP sector this stands in for. Note the contrast
    # with "Nonrefrigerated" at 5.3 in the same table: refrigeration is about
    # 5.6x the intensity, which is why collapsing both into use code 4010 is
    # a stated weakness rather than a detail.
    "industrial_warehouse_process": 29.6,
    # CBECS C22 "Laboratory", 32.1 kWh/sq ft. The highest anchor here.
    "laboratory": 32.1,
    # CBECS C22 "Recreation", 13.0 kWh/sq ft. A weak proxy: CBECS has no
    # ice-rink category and a sheet of ice is nothing like a gymnasium.
    # Named as the weakest anchor on the method page.
    "ice_rink": 13.0,
    # CBECS C22 "Vehicle service or repair", 6.1 kWh/sq ft.
    "auto_service": 6.1,
    # CBECS C22 "Other retail", 15.2 kWh/sq ft. A dealership is showroom plus
    # service bay; "Other retail" is the closest published activity.
    "auto_dealership": 15.2,
    # CBECS C22 "College or university", 12.6 kWh/sq ft.
    "university": 12.6,
}

#: Modelled archetypes with no defensible published intensity. Rows carrying
#: these are exported UNSCORED with this named reason rather than given an
#: invented number. CBECS has no data-center activity category, and published
#: per-square-foot figures for data halls vary by more than an order of
#: magnitude with rack density, which is not in the assessor record. Six
#: Worcester parcels. Data centers are also absent from the published ICP, so
#: the cost of not scoring them is close to zero.
UNANCHORED_ARCHETYPES: frozenset[str] = frozenset({"data_hall"})


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
    Assumption(
        "charger_rating", CHARGER_KW, "kW", "ASSUMED",
        "Powertown spec page, read as symmetric with the discharge rating",
        "The most the charger can draw, used only to ask whether the "
        "overnight window is long enough. The recharge FOOTPRINT is the rate "
        "the site actually needs -- at most 413.4 kWh over 11 hours, about "
        "37.6 kW -- because the battery draws what it must replace, not what "
        "the hardware could take.",
    ),
    Assumption(
        "intensity_industrial_manufacturing",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_manufacturing"],
        "kWh/sq ft/yr", "DERIVED", "EIA MECS 2018 Tables 3.2 and 9.1",
        'Mean of NAICS 332 Fabricated Metal Products (124 trillion Btu net electricity over 1,530 million sq ft = 23.75) and NAICS 333 Machinery (80 over 1,021 = 22.96), the two subsectors the machine shops and metal fabricators of Worcester sit in. DERIVED rather than FILED: the Btu-to-kWh conversion and the two-subsector mean are both choices.',
    ),
    Assumption(
        "intensity_industrial_warehouse_process",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["industrial_warehouse_process"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'Refrigerated' warehouse. Nonrefrigerated warehouse is 5.3 in the same table, so use code 4010 spans a 5.6x intensity range that the assessor record cannot separate.",
    ),
    Assumption(
        "intensity_laboratory",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["laboratory"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'Laboratory'. ComStock explicitly excludes laboratories, which is why this archetype is modelled at all.",
    ),
    Assumption(
        "intensity_ice_rink",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["ice_rink"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'Recreation'. THE WEAKEST ANCHOR IN THIS TABLE: CBECS has no ice-rink category, and a sheet of ice under continuous refrigeration is nothing like a gymnasium. Rink rankings are indicative only.",
    ),
    Assumption(
        "intensity_auto_service",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["auto_service"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'Vehicle service or repair'.",
    ),
    Assumption(
        "intensity_auto_dealership",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["auto_dealership"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'Other retail'. A dealership is showroom plus service bay; 'Other retail' is the closest published activity.",
    ),
    Assumption(
        "intensity_university",
        ELECTRIC_INTENSITY_KWH_PER_SQFT_YR["university"],
        "kWh/sq ft/yr", "FILED", "EIA CBECS 2018 Table C22",
        "CBECS activity 'College or university'.",
    ),
    Assumption(
        "unanchored_archetypes", ", ".join(sorted(UNANCHORED_ARCHETYPES)), "",
        "ASSUMED", "no published intensity",
        "Modelled archetypes with no defensible published intensity. "
        "Exported UNSCORED with the reason named rather than given an "
        "invented number. CBECS has no data-center category and published "
        "data-hall intensities vary by over an order of magnitude with rack "
        "density, which is not in the assessor record.",
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
