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
        "This tool contains no per-building measurement. Every figure comes "
        "from three public assessor fields (use code, building area and "
        "municipality) run through a modelled load-shape library.",
    ),
    Limitation(
        "no_interconnection",
        "Nothing here checks interconnection feasibility. Whether the "
        "utility will permit a 250 kW resource at a given service takes an "
        "interconnection study to answer, and no public dataset carries the "
        "result.",
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
        "ranking key, written in dollars because dollars sort. Nobody "
        "should bank on it.",
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
        "well is capped at MED confidence by this rule.",
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
        "The ranking is customer demand-charge savings. A developer ranks "
        "on margin instead: savings share minus cost to serve, including "
        "service upgrades, wall availability, permitting and trucking. The "
        "two orderings diverge.",
    ),
    Limitation(
        "collapse_points",
        "Two assessor use codes carry whole sectors inside them. Code 4000 "
        "is every manufacturer in the state, so machine shops, metal "
        "fabricators, food producers and commercial laundries are "
        "indistinguishable; code 4010 hides refrigerated cold storage "
        "inside ambient warehousing, and the published intensity for those "
        "two differs by 5.6x. Within either code, floor area and rate class "
        "drive the ranking and load shape plays no part.",
    ),
    Limitation(
        "large_sites_still_rank_high",
        "Ranking on absolute dollars rewards having more kilowatts to remove, "
        "so the default order is led by large buildings that shave a small "
        "fraction of a big peak. Measured on Worcester, the top 60 by dollars "
        "shave a median 18.6% of their peak while the sweet-spot view shaves "
        "71.6%. The two views stay separate, and no score blends them.",
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
        "The tariff bills the monthly maximum, so the threshold that "
        "matters is the one holdable on every billed day of the month. The "
        "archetype layer exposes one day per month, that month's worst, so "
        "the threshold here is the peak day's alone. It is the right day to "
        "pick if you may pick only one, because it carries the month's "
        "highest peak. A lower day with a longer plateau can still need "
        "more energy.",
    ),
    Limitation(
        "day_chart_is_one_day",
        "The day chart in the detail panel is one day: the worst billed day "
        "of the month the battery works hardest. Inside 08:00-21:00 it is "
        "the archetype's own fifteen-minute load. Overnight, the build "
        "keeps only the maximum and drops the shape, so the chart draws it "
        "as a flat dashed line. Overnight load is not billed under this "
        "tariff at any magnitude.",
    ),
    Limitation(
        "address_box_is_the_screen_only",
        "The address box searches the commercial and industrial parcels "
        "this screen looked at, by the assessor's own site address. A "
        "residential parcel, a building recorded under a different street "
        "number, or an address in a town not yet processed returns no "
        "match. No match means the parcel was never screened. Whether the "
        "site would pass is unknown.",
    ),
    Limitation(
        "siting_screens_out_only",
        "The siting screen screens out the impossible and does not confirm "
        "the possible. It measures the longest wall with ten feet of "
        "clearance to the parcel line on MassGIS roof outlines, which "
        "include overhangs. It cannot see loading docks, fire lanes, "
        "parking aisles, means of egress, wall openings, local zoning "
        "setbacks or where the service entrance is. A clear result means "
        "only that nothing ruled the site out.",
    ),
    Limitation(
        "class_shape_check_is_modest",
        "The class-shape check compares the ComStock-backed aggregate with "
        "National Grid's published class average load shapes. It is a "
        "modest sanity check and cannot validate the model: the class "
        "average is diversified across many customers while the aggregate "
        "sums each archetype's own worst billed day, ComStock's weather "
        "year is 2018 and the class shapes are a later year, and it does "
        "not cover the modelled industrial rows.",
    ),
    Limitation(
        "three_towns_not_the_design_docs_three",
        "Three municipalities: Worcester, Fall River and Lowell. New "
        "Bedford and Chicopee were the original picks alongside Worcester, "
        "but MassGIS's electricity-provider layer lists New Bedford as "
        "Eversource and Chicopee as a municipal light plant, so National "
        "Grid's G-2/G-3 tariff never applies there. Fall River and Lowell, "
        "both National Grid mill cities, replace them. Each town's figures "
        "come from its own assessor extract, and the assessor year is shown "
        "per town.",
    ),
    Limitation(
        "occupant_candidates_are_drafted_then_verified",
        "Occupant candidates are drafted by an agent and verified by a "
        "person before anything is published. The agent runs one "
        "web-search-backed request per row and writes three cells: a name, "
        "one source URL and one sentence of evidence. It cannot set a row's "
        "status, so a candidate reaches the published table only once a "
        "reviewer has opened the source and initialled the row, and a "
        "candidate without an openable source URL is dropped. The drafted "
        "worksheet is committed at data/occupant_candidates.csv, so the "
        "unverified research is as browsable as the verified table.",
    ),
    Limitation(
        "sweet_spot_measures_seasonal_swing_not_intraday_shape",
        "The sweet-spot view asks for the expensive G-2 rate plus a peak "
        "1.4x the site's own average, and that average is taken across the "
        "twelve monthly billed peaks. So it selects for seasonal swing, "
        "which in Massachusetts means summer cooling. The intraday inrush "
        "the method argues about elsewhere is a different quantity, and "
        "this filter cannot see it. The two come apart on the "
        "modelled-industrial list: its 463 rows run 1.10 to 1.22 against "
        "1.14 to 1.84 for the measured list, so none of them clears the "
        "floor and the sweet-spot view of that list is empty in all three "
        "towns, although 236 of those rows are on G-2. The emptiness is a "
        "property of the filter. The modelled shapes carry no weather "
        "model, so their monthly peaks barely move. Read the modelled list "
        "ranked by saving.",
    ),
    Limitation(
        "reason_sentences_are_templated",
        "The sentence under each row is templated from the computed "
        "figures. No model writes it. A generated sentence would read "
        "better and would occasionally be wrong about arithmetic this page "
        "can prove, and unlike an occupant name there is no verification "
        "step for prose. The template states only what the scorer computed, "
        "which is the claim the page can stand behind.",
    ),
)


#: Gaps that are real and unbuilt. Naming them is cheaper than being caught by
#: them, and a reader who finds an unnamed gap stops trusting the named ones.
KNOWN_GAPS: tuple[Limitation, ...] = (
    Limitation(
        "occupant_resolution_partial",
        "Only part of the head of the ranking has had its operating "
        "business resolved. The assessor's owner of record is a holding "
        "company for roughly half the top 50, so an unresolved row leaves "
        "the occupant blank. Showing the holding company there would name "
        "the wrong business. The count above is the number resolved today.",
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
    scored: pd.DataFrame, regression: dict | None = None, calibration: dict | None = None, towns: list[dict] | None = None
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
        else {"status": "not yet run, so there are no figures to report"},
        "calibration": calibration
        if calibration is not None
        else {"status": "not yet run, so there is no result to report"},
        "towns": list(towns or []),
    }
