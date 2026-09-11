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

from shave import crosswalk, occupants
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
#: the rest are limits the spec names elsewhere, or that the build measured,
#: and that a domain expert would otherwise find on their own -- which is the
#: worse way to find them.
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
        "fraction of a big peak. Measured on Worcester, the top 60 by dollars "
        "shave a median 18.6% of their peak while the sweet-spot view shaves "
        "71.6%. The two are shown separately rather than blended into a score.",
    ),
    Limitation(
        "recharge_is_unconstrained_service_capacity_is_not_checked",
        "Overnight charging is not modelled as a constraint, because this "
        "tariff does not bill it: demand is the greatest fifteen-minute peak "
        "during 08:00-21:00 on weekdays, so load between 21:00 and 08:00 is "
        "never billed at any magnitude. The real limit is whether a building's "
        "electrical service can carry the extra draw, and service capacity is "
        "not in any public assessor record.",
    ),
    Limitation(
        "peak_day_not_every_billed_day",
        "The tariff bills the monthly maximum, so the threshold that matters "
        "is the one holdable on every billed day of the month. The archetype "
        "layer exposes one day per month -- that month's worst -- so the "
        "threshold here is the peak day's alone. It is the right day to pick "
        "if you may pick only one, because it carries the month's highest "
        "peak. It is not a proof.",
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
    Limitation(
        "occupant_resolution_partial",
        "Only part of the head of the ranking has had its operating business "
        "resolved by hand. The assessor's owner of record is a holding company "
        "for roughly half the top 50, so an unresolved row shows no occupant "
        "rather than showing the owner in its place.",
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
        "The battery could not refill inside the 21:00-08:00 window even at "
        "the charger's full rating. Given the energy the battery holds this "
        "cannot currently occur, so the flag is a guard on the assumptions "
        "rather than a per-site finding, and no published row carries it."
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
    unscored = (
        scored[scored["unscored_reason"].notna()]
        if "unscored_reason" in scored
        else scored.iloc[0:0]
    )

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
            "intensity_anchors": (
                "EIA CBECS 2018 Table C22, EIA MECS 2018 Tables 3.2 and 9.1"
            ),
            "tariff": (
                "National Grid M.D.P.U. No. 1591 and the MECO summary of rates"
            ),
        },
        "coverage": {
            "parcels_total": int(len(scored)),
            "kept": int(len(kept)),
            "sweet_spot": (
                int(kept["sweet_spot"].sum()) if "sweet_spot" in kept else 0
            ),
            "unscored": {
                str(k): int(v)
                for k, v in unscored["unscored_reason"].value_counts().items()
            },
            "crosswalk": {
                str(k): int(v) for k, v in crosswalk.coverage_summary().items()
            },
            "modelled_archetypes_anchored": sorted(
                ELECTRIC_INTENSITY_KWH_PER_SQFT_YR
            ),
            "modelled_archetypes_unanchored": sorted(UNANCHORED_ARCHETYPES),
            "assess_years": (
                [int(y) for y in sorted(scored["assess_fy"].dropna().unique())]
                if "assess_fy" in scored
                else []
            ),
        },
        "occupants": {
            str(k): int(v) for k, v in occupants.coverage(scored, top_n=50).items()
        },
        "regression": regression
        if regression is not None
        else {"status": "not yet run; the figures below are unreported, not zero"},
    }
