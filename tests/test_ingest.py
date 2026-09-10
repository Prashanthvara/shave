"""Ingest tests, in two halves.

The synthetic half builds tiny Assess frames and drives `build_parcels`
directly. That is where the collapse rule and the five confidence predicates are
pinned, because a real municipality happens not to exercise most of them: all of
Worcester has exactly two multi-use parcels and exactly one scoreable record
with no floor area, so relying on the real file would leave four of the five
predicates untested.

The real half runs the whole loader against the Worcester FY2026 L3 extract and
is skipped when that directory is absent, so a clean checkout still passes.

One number needs explaining. The brief's "2,291 scoreable parcels" is a count of
*Assess records*; this loader returns one row per LOC_ID, and Worcester's 2,290
scoreable records collapse into 2,099 parcels. Both are asserted below, the
record count tightly and the parcel count loosely, so a change to the collapse
rule shows up as a failure rather than as a quietly different ranking.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from shave import crosswalk
from shave.assumptions import LIKELY_SINGLE_METERED_MAX_SQFT
from shave.crosswalk import CrosswalkError
from shave.ingest import (
    COARSE_REASON,
    PREDICATES,
    IngestError,
    build_parcels,
    load_municipality,
    summarise,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WORCESTER_DIR = REPO_ROOT / "data/raw/M348_WORCESTER/L3_SHP_M348_Worcester"
WORCESTER_TOWN_ID = 348

needs_worcester = pytest.mark.skipif(
    not (WORCESTER_DIR / "M348TaxPar_CY26_FY26.shp").exists(),
    reason="Worcester L3 extract not present (data/raw is gitignored)",
)

# Codes with useful properties, read off the committed crosswalk.
CODE_HIGH_MAP = "3160"      # warehouse, crosswalk confidence HIGH -> maps 1:1
CODE_LOOSE_MAP = "3260"     # full_service_restaurant, crosswalk confidence MED
CODE_OFFICE = "3400"        # the office family, band resolved from floor area
CODE_COARSE = "4000"        # COLLAPSE POINT: every manufacturer in the state
CODE_EXCLUDED = "3360"      # Parking Garages
CODE_RESIDENTIAL = "1010"   # class 1: never in the universe at all


@pytest.fixture(autouse=True)
def _clean_crosswalk_cache():
    crosswalk.load.cache_clear()
    yield
    crosswalk.load.cache_clear()


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------


def record(**overrides) -> dict:
    base = {
        "PROP_ID": "01_001_0001",
        "LOC_ID": "F_100000_900000",
        "TOTAL_VAL": 1_000_000,
        "FY": 2026,
        "USE_CODE": CODE_HIGH_MAP,
        "SITE_ADDR": "1 MAIN ST",
        "CITY": "TESTVILLE",
        "ZIP": "01610",
        "OWNER1": "ACME HOLDINGS LLC",
        "ZONING": "BG-1",
        "YEAR_BUILT": 1988,
        "BLD_AREA": 10_000,
        "STORIES": "1",
        "TOWN_ID": WORCESTER_TOWN_ID,
    }
    base.update(overrides)
    return base


def assess(*records: dict) -> pd.DataFrame:
    return pd.DataFrame(list(records))


def square(x: float = 0.0, y: float = 0.0, side: float = 10.0) -> Polygon:
    return Polygon([(x, y), (x + side, y), (x + side, y + side), (x, y + side)])


def taxpar(*loc_ids: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "LOC_ID": list(loc_ids),
            "POLY_TYPE": ["FEE"] * len(loc_ids),
            "geometry": [square(i * 20.0) for i in range(len(loc_ids))],
        },
        geometry="geometry",
        crs="EPSG:26986",
    )


def only(gdf: gpd.GeoDataFrame) -> pd.Series:
    assert len(gdf) == 1, f"expected one parcel, got {len(gdf)}"
    return gdf.iloc[0]


# ---------------------------------------------------------------------------
# the collapse rule
# ---------------------------------------------------------------------------


def test_one_record_one_parcel():
    gdf = build_parcels(assess(record()), town_id=WORCESTER_TOWN_ID)
    row = only(gdf)
    assert row.loc_id == "F_100000_900000"
    assert row.sqft == 10_000
    assert row.archetype == "warehouse"
    assert row.source == "comstock"
    assert row.record_count == 1
    assert bool(row.multi_use) is False


def test_matching_use_codes_sum_their_floor_area():
    gdf = build_parcels(
        assess(
            record(PROP_ID="a", BLD_AREA=10_000, TOTAL_VAL=500_000),
            record(PROP_ID="b", BLD_AREA=25_000, TOTAL_VAL=100_000),
            record(PROP_ID="c", BLD_AREA=5_000, TOTAL_VAL=900_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    row = only(gdf)
    assert row.sqft == 40_000
    assert bool(row.multi_use) is False
    assert row.record_count == 3
    # Identity is the dominant record: largest BLD_AREA, not largest value.
    assert row.prop_id == "b"


def test_conflicting_use_codes_keep_the_largest_and_flag_multi_use():
    gdf = build_parcels(
        assess(
            record(PROP_ID="office", USE_CODE=CODE_OFFICE, BLD_AREA=12_000),
            record(PROP_ID="shed", USE_CODE=CODE_HIGH_MAP, BLD_AREA=40_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    row = only(gdf)
    assert bool(row.multi_use) is True
    assert row.prop_id == "shed"
    assert row.use_code == CODE_HIGH_MAP
    assert row.archetype == "warehouse"
    # Area is still the whole parcel: nothing is dropped by the disagreement.
    assert row.sqft == 52_000


def test_the_collapse_is_deterministic_under_input_order():
    records = [
        record(PROP_ID="a", BLD_AREA=10_000),
        record(PROP_ID="b", BLD_AREA=25_000),
        record(PROP_ID="c", BLD_AREA=5_000),
    ]
    forward = only(build_parcels(assess(*records), town_id=WORCESTER_TOWN_ID))
    backward = only(build_parcels(assess(*reversed(records)), town_id=WORCESTER_TOWN_ID))
    assert forward.prop_id == backward.prop_id == "b"
    assert forward.sqft == backward.sqft


def test_ties_on_area_break_on_total_val_then_prop_id():
    gdf = build_parcels(
        assess(
            record(PROP_ID="zzz", BLD_AREA=10_000, TOTAL_VAL=400_000),
            record(PROP_ID="aaa", BLD_AREA=10_000, TOTAL_VAL=400_000),
            record(PROP_ID="mmm", BLD_AREA=10_000, TOTAL_VAL=900_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert only(gdf).prop_id == "mmm"

    gdf = build_parcels(
        assess(
            record(PROP_ID="zzz", BLD_AREA=10_000, TOTAL_VAL=400_000),
            record(PROP_ID="aaa", BLD_AREA=10_000, TOTAL_VAL=400_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert only(gdf).prop_id == "aaa"


def test_separate_loc_ids_stay_separate():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", BLD_AREA=10_000),
            record(LOC_ID="F_2_2", BLD_AREA=20_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert len(gdf) == 2
    assert set(gdf["loc_id"]) == {"F_1_1", "F_2_2"}
    assert sorted(gdf["sqft"].tolist()) == [10_000, 20_000]


def test_no_record_leaves_the_universe_uncounted():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1"),
            record(LOC_ID="F_2_2", USE_CODE=CODE_EXCLUDED),
            record(LOC_ID="F_3_3", USE_CODE=CODE_RESIDENTIAL),
            record(LOC_ID=None),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    attrs = gdf.attrs
    accounted = (
        attrs["blank_loc_id_records"]
        + attrs["out_of_class_records"]
        + attrs["unbuilt_use_code_records"]
        + attrs["excluded_records"]
        + attrs["scoreable_records"]
    )
    assert accounted == attrs["assess_records_total"] == 4


# ---------------------------------------------------------------------------
# scoping and the coverage assertion
# ---------------------------------------------------------------------------


def test_an_invented_building_use_code_fails_loudly():
    frame = assess(record(USE_CODE="3999", BLD_AREA=40_000))
    with pytest.raises(CrosswalkError, match="3999"):
        build_parcels(frame, town_id=WORCESTER_TOWN_ID)


def test_the_coverage_failure_names_every_missing_code():
    frame = assess(
        record(LOC_ID="F_1_1", USE_CODE="3999", BLD_AREA=40_000),
        record(LOC_ID="F_2_2", USE_CODE="4999", BLD_AREA=40_000),
    )
    with pytest.raises(CrosswalkError) as excinfo:
        build_parcels(frame, town_id=WORCESTER_TOWN_ID)
    assert "3999" in str(excinfo.value)
    assert "4999" in str(excinfo.value)


def test_a_use_code_with_no_building_area_anywhere_is_dropped_not_asserted():
    # This is the second scoping filter, and it is what keeps assert_covers
    # honest: `...V` vacant codes and rights of way describe land, not
    # buildings, so they never reach the crosswalk. An invented code with no
    # floor area therefore does NOT raise -- but it is counted.
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", BLD_AREA=10_000),
            record(LOC_ID="F_2_2", USE_CODE="330V", BLD_AREA=0),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert len(gdf) == 1
    assert gdf.attrs["unbuilt_use_code_records"] == 1


def test_residential_classes_never_enter_the_universe():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1"),
            record(LOC_ID="F_2_2", USE_CODE=CODE_RESIDENTIAL, BLD_AREA=900_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert len(gdf) == 1
    assert gdf.attrs["out_of_class_records"] == 1


def test_excluded_codes_are_dropped_and_counted():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1"),
            record(LOC_ID="F_2_2", USE_CODE=CODE_EXCLUDED, BLD_AREA=80_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    assert set(gdf["use_code"]) == {CODE_HIGH_MAP}
    assert gdf.attrs["excluded_records"] == 1
    assert gdf.attrs["excluded_parcels"] == 1


def test_a_blank_loc_id_record_is_dropped_and_counted():
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1"), record(LOC_ID="   ", BLD_AREA=50_000)),
        town_id=WORCESTER_TOWN_ID,
    )
    assert len(gdf) == 1
    assert gdf.attrs["blank_loc_id_records"] == 1
    assert gdf.attrs["blank_loc_id_in_class_records"] == 1
    assert gdf.attrs["blank_loc_id_in_class_sqft"] == 50_000


def test_a_town_with_nothing_scoreable_returns_an_empty_frame_not_an_error():
    # The design copy insists an empty result is a finding, not a failure, so
    # the loader has to be able to produce one with the full schema intact.
    gdf = build_parcels(
        assess(record(USE_CODE=CODE_EXCLUDED, BLD_AREA=5_000)), town_id=WORCESTER_TOWN_ID
    )
    assert len(gdf) == 0
    assert set(gdf.columns) >= {"loc_id", "archetype", "confidence", "geometry"}
    summary = summarise(gdf)
    assert summary["parcels"] == 0
    assert summary["excluded_records"] == 1
    assert summary["total_sqft"] == 0.0


def test_an_empty_assess_frame_is_handled():
    empty = assess(record()).iloc[0:0]
    gdf = build_parcels(empty, town_id=WORCESTER_TOWN_ID)
    assert len(gdf) == 0
    assert gdf.attrs["assess_records_total"] == 0


def test_a_town_id_mismatch_raises():
    with pytest.raises(IngestError, match="TOWN_ID"):
        build_parcels(assess(record(TOWN_ID=35)), town_id=WORCESTER_TOWN_ID)


def test_a_missing_required_column_raises():
    frame = assess(record()).drop(columns=["BLD_AREA"])
    with pytest.raises(IngestError, match="BLD_AREA"):
        build_parcels(frame, town_id=WORCESTER_TOWN_ID)


# ---------------------------------------------------------------------------
# the office band, resolved from collapsed floor area
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sqft, expected",
    [
        (5_000, "small_office"),
        (crosswalk.SMALL_OFFICE_MAX_SQFT, "small_office"),
        (crosswalk.SMALL_OFFICE_MAX_SQFT + 1, "medium_office"),
        (crosswalk.MEDIUM_OFFICE_MAX_SQFT, "medium_office"),
        (crosswalk.MEDIUM_OFFICE_MAX_SQFT + 1, "large_office"),
    ],
)
def test_office_band_agrees_with_resolve_office_band(sqft, expected):
    gdf = build_parcels(
        assess(record(USE_CODE=CODE_OFFICE, BLD_AREA=sqft)), town_id=WORCESTER_TOWN_ID
    )
    assert only(gdf).archetype == expected == crosswalk.resolve_office_band(sqft)


def test_office_band_uses_the_collapsed_area_not_the_dominant_record():
    # Two 15,000 sq ft office records on one parcel are a 30,000 sq ft office,
    # which is medium. Banding on the dominant record alone would say small.
    gdf = build_parcels(
        assess(
            record(PROP_ID="a", USE_CODE=CODE_OFFICE, BLD_AREA=15_000),
            record(PROP_ID="b", USE_CODE=CODE_OFFICE, BLD_AREA=15_000),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    row = only(gdf)
    assert row.sqft == 30_000
    assert row.archetype == "medium_office"


# ---------------------------------------------------------------------------
# confidence, one predicate at a time
# ---------------------------------------------------------------------------


def test_a_clean_parcel_is_high_with_no_reasons():
    row = only(build_parcels(assess(record()), town_id=WORCESTER_TOWN_ID))
    assert row.confidence == "HIGH"
    assert row.confidence_reasons == ()


def test_a_loosely_mapped_use_code_fails_unique_archetype():
    # 3260 is "Eating and Drinking Establishments": the code does not separate
    # full service from quick service, so the crosswalk grades it MED.
    row = only(
        build_parcels(assess(record(USE_CODE=CODE_LOOSE_MAP)), town_id=WORCESTER_TOWN_ID)
    )
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("unique_archetype",)


def test_missing_floor_area_fails_has_floor_area():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", BLD_AREA=None),
            record(LOC_ID="F_2_2", BLD_AREA=10_000),  # keeps 3160 in scope
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    row = gdf.set_index("loc_id").loc["F_1_1"]
    assert pd.isna(row.sqft)
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("has_floor_area",)


def test_zero_floor_area_fails_has_floor_area():
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1", BLD_AREA=0), record(LOC_ID="F_2_2", BLD_AREA=10_000)),
        town_id=WORCESTER_TOWN_ID,
    )
    row = gdf.set_index("loc_id").loc["F_1_1"]
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("has_floor_area",)


def test_floor_area_over_the_single_metering_cap_fails_that_predicate():
    row = only(
        build_parcels(
            assess(record(BLD_AREA=LIKELY_SINGLE_METERED_MAX_SQFT + 1)),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("within_single_meter_cap",)


def test_the_single_metering_cap_boundary_is_inclusive():
    row = only(
        build_parcels(
            assess(record(BLD_AREA=LIKELY_SINGLE_METERED_MAX_SQFT)),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.confidence == "HIGH"


def test_two_records_on_one_parcel_fail_single_record():
    row = only(
        build_parcels(
            assess(
                record(PROP_ID="a", BLD_AREA=5_000),
                record(PROP_ID="b", BLD_AREA=5_000),
            ),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.record_count == 2
    assert row.confidence == "MED"
    assert row.confidence_reasons == ("single_record",)


def test_multi_metering_evidence_counts_records_outside_the_scoreable_set():
    # A shop with three flats over it is not single-metered, even though the
    # flats never reach the crosswalk. The predicate is a property of the
    # parcel, so it is taken before use-code filtering narrows the frame.
    row = only(
        build_parcels(
            assess(
                record(PROP_ID="shop", BLD_AREA=8_000),
                record(PROP_ID="flat1", USE_CODE=CODE_RESIDENTIAL, BLD_AREA=900),
                record(PROP_ID="flat2", USE_CODE=CODE_RESIDENTIAL, BLD_AREA=900),
            ),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.sqft == 8_000            # residential area is not scoreable area
    assert row.record_count == 3
    assert row.confidence_reasons == ("single_record",)


def test_two_owners_fail_single_owner():
    row = only(
        build_parcels(
            assess(
                record(PROP_ID="a", BLD_AREA=5_000, OWNER1="ACME HOLDINGS LLC"),
                record(PROP_ID="b", BLD_AREA=5_000, OWNER1="BETA TRUST"),
            ),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.owner_count == 2
    # Two failures: single_record and single_owner.
    assert row.confidence == "LOW"
    assert set(row.confidence_reasons) == {"single_record", "single_owner"}


def test_two_predicate_failures_are_low():
    row = only(
        build_parcels(
            assess(record(USE_CODE=CODE_LOOSE_MAP, BLD_AREA=250_000)),
            town_id=WORCESTER_TOWN_ID,
        )
    )
    assert row.confidence == "LOW"
    assert set(row.confidence_reasons) == {"unique_archetype", "within_single_meter_cap"}


def test_a_coarse_400_series_code_is_low_however_well_it_scores():
    coarse = only(
        build_parcels(assess(record(USE_CODE=CODE_COARSE, BLD_AREA=50_000)), town_id=WORCESTER_TOWN_ID)
    )
    assert coarse.confidence == "LOW"
    assert COARSE_REASON in coarse.confidence_reasons

    # A code with the same single predicate failure but no collapse point is
    # MED. That contrast is the whole reason the coarse rule exists.
    fine = only(
        build_parcels(assess(record(USE_CODE=CODE_LOOSE_MAP, BLD_AREA=50_000)), town_id=WORCESTER_TOWN_ID)
    )
    assert fine.confidence == "MED"
    assert COARSE_REASON not in fine.confidence_reasons


def test_confidence_reasons_only_ever_name_known_predicates():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1"),
            record(LOC_ID="F_2_2", USE_CODE=CODE_COARSE, BLD_AREA=250_000),
            record(LOC_ID="F_3_3", USE_CODE=CODE_LOOSE_MAP),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    known = set(PREDICATES) | {COARSE_REASON}
    for reasons in gdf["confidence_reasons"]:
        assert set(reasons) <= known


# ---------------------------------------------------------------------------
# vintage, geometry, schema
# ---------------------------------------------------------------------------


def test_assess_fy_is_on_every_row_and_on_the_result():
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1", FY=2026), record(LOC_ID="F_2_2", FY=2026)),
        town_id=WORCESTER_TOWN_ID,
    )
    assert set(gdf["assess_fy"]) == {2026}
    assert gdf.attrs["assess_fy"] == 2026


def test_assess_fy_falls_back_to_the_filename_when_the_column_is_empty():
    frame = assess(record(FY=None))
    gdf = build_parcels(frame, town_id=WORCESTER_TOWN_ID, assess_fy_hint=2019)
    assert only(gdf).assess_fy == 2019
    assert gdf.attrs["assess_fy"] == 2019


def test_geometry_is_joined_on_loc_id_and_keeps_the_crs():
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1"), record(LOC_ID="F_2_2")),
        taxpar("F_1_1", "F_2_2"),
        town_id=WORCESTER_TOWN_ID,
    )
    assert gdf.crs is not None
    assert gdf.geometry.notna().all()
    assert gdf.attrs["missing_geometry"] == 0


def test_a_parcel_with_no_polygon_survives_with_null_geometry():
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1"), record(LOC_ID="F_missing")),
        taxpar("F_1_1"),
        town_id=WORCESTER_TOWN_ID,
    )
    assert len(gdf) == 2
    assert gdf.attrs["missing_geometry"] == 1
    assert gdf.set_index("loc_id").loc["F_missing"].geometry is None


def test_non_fee_polygons_are_not_joined():
    geo = taxpar("F_1_1")
    geo.loc[0, "POLY_TYPE"] = "ROW"
    geo = pd.concat([geo, taxpar("F_2_2")], ignore_index=True)
    geo = gpd.GeoDataFrame(geo, geometry="geometry", crs="EPSG:26986")
    gdf = build_parcels(
        assess(record(LOC_ID="F_1_1"), record(LOC_ID="F_2_2")), geo, town_id=WORCESTER_TOWN_ID
    )
    by_loc = gdf.set_index("loc_id")
    assert by_loc.loc["F_1_1"].geometry is None
    assert by_loc.loc["F_2_2"].geometry is not None


def test_the_output_schema_is_the_documented_one():
    gdf = build_parcels(assess(record()), taxpar("F_100000_900000"), town_id=WORCESTER_TOWN_ID)
    required = {
        "loc_id", "prop_id", "use_code", "use_desc", "archetype", "source",
        "sqft", "stories", "year_built", "owner", "site_addr", "city", "zip",
        "zoning", "assess_fy", "confidence", "confidence_reasons", "multi_use",
        "geometry",
    }
    assert required <= set(gdf.columns)
    assert isinstance(gdf, gpd.GeoDataFrame)


def test_year_built_zero_becomes_null_and_stories_parse_as_numbers():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1", YEAR_BUILT=0, STORIES="2.50"),
            record(LOC_ID="F_2_2", YEAR_BUILT=1971, STORIES="1"),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    by_loc = gdf.set_index("loc_id")
    assert pd.isna(by_loc.loc["F_1_1"].year_built)
    assert by_loc.loc["F_1_1"].stories == 2.5
    assert by_loc.loc["F_2_2"].year_built == 1971


def test_summarise_partitions_the_input():
    gdf = build_parcels(
        assess(
            record(LOC_ID="F_1_1"),
            record(LOC_ID="F_2_2", USE_CODE=CODE_COARSE, BLD_AREA=40_000),
            record(LOC_ID="F_3_3", USE_CODE=CODE_EXCLUDED, BLD_AREA=40_000),
            record(LOC_ID="F_4_4", USE_CODE=CODE_RESIDENTIAL),
        ),
        town_id=WORCESTER_TOWN_ID,
    )
    summary = summarise(gdf)
    assert summary["parcels"] == 2
    assert summary["excluded_records"] == 1
    assert summary["out_of_class_records"] == 1
    assert summary["total_sqft"] == 50_000
    assert summary["source_split"] == {"comstock": 1, "modeled": 1}
    assert sum(summary["confidence"].values()) == summary["parcels"]


# ---------------------------------------------------------------------------
# the real Worcester extract
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def worcester() -> gpd.GeoDataFrame:
    crosswalk.load.cache_clear()
    return load_municipality(WORCESTER_DIR, WORCESTER_TOWN_ID)


@needs_worcester
def test_worcester_scoreable_record_count(worcester):
    # The brief's 2,291 is a count of Assess records, before the one-to-many
    # collapse. Held tight because a change here means the scoping filters
    # moved, which is a change to who is in the market.
    records = worcester.attrs["scoreable_records"]
    assert abs(records - 2_291) / 2_291 < 0.02, records


@needs_worcester
def test_worcester_parcel_count_after_the_collapse(worcester):
    # 2,290 records fold into ~2,099 parcels. Loose, because the collapse rule
    # is a judgment call and a different defensible rule lands nearby.
    assert abs(len(worcester) - 2_291) / 2_291 < 0.12, len(worcester)
    assert len(worcester) <= worcester.attrs["scoreable_records"]


@needs_worcester
def test_worcester_total_floor_area(worcester):
    total = summarise(worcester)["total_sqft"]
    assert abs(total - 53.2e6) / 53.2e6 < 0.02, total


@needs_worcester
def test_worcester_floor_area_survives_the_collapse(worcester):
    # Summing on collapse means the only square footage that can go missing is
    # in records with no LOC_ID at all, and those are counted separately.
    attrs = worcester.attrs
    recovered = summarise(worcester)["total_sqft"] + attrs["blank_loc_id_in_class_sqft"]
    assert abs(recovered - 53.175e6) / 53.175e6 < 0.005, recovered


@needs_worcester
def test_worcester_every_row_is_classified(worcester):
    assert worcester["archetype"].notna().all()
    assert (worcester["archetype"].str.len() > 0).all()
    assert worcester["source"].isin(["comstock", "modeled"]).all()


@needs_worcester
def test_worcester_every_row_has_a_valid_confidence(worcester):
    assert set(worcester["confidence"]) <= {"HIGH", "MED", "LOW"}
    assert worcester["confidence"].notna().all()


@needs_worcester
def test_worcester_high_confidence_rows_have_no_reasons(worcester):
    high = worcester[worcester["confidence"] == "HIGH"]
    assert len(high) > 0
    assert all(len(reasons) == 0 for reasons in high["confidence_reasons"])


@needs_worcester
def test_worcester_low_and_med_rows_always_say_why(worcester):
    not_high = worcester[worcester["confidence"] != "HIGH"]
    assert len(not_high) > 0
    assert all(len(reasons) > 0 for reasons in not_high["confidence_reasons"])


@needs_worcester
def test_worcester_has_no_duplicate_loc_id(worcester):
    assert not worcester["loc_id"].duplicated().any()
    assert worcester["loc_id"].notna().all()


@needs_worcester
def test_worcester_excludes_the_excluded_codes(worcester):
    excluded = {code for code, row in crosswalk.load().items() if row.excluded}
    assert excluded
    assert set(worcester["use_code"]) & excluded == set()


@needs_worcester
def test_worcester_use_codes_are_all_in_the_crosswalk(worcester):
    crosswalk.assert_covers(set(worcester["use_code"]))


@needs_worcester
def test_worcester_archetypes_are_real_types(worcester):
    known = set(crosswalk.COMSTOCK_TYPES | crosswalk.MODELED_TYPES) - {"office"}
    assert set(worcester["archetype"]) <= known


@needs_worcester
def test_worcester_vintage_is_fy2026_on_every_row(worcester):
    assert set(worcester["assess_fy"]) == {2026}
    assert worcester.attrs["assess_fy"] == 2026
    assert worcester.attrs["assess_fy_from_filename"] == 2026
    assert worcester.attrs["assess_fy_agrees_with_filename"]


@needs_worcester
def test_worcester_accounts_for_every_assess_record(worcester):
    attrs = worcester.attrs
    accounted = (
        attrs["blank_loc_id_records"]
        + attrs["out_of_class_records"]
        + attrs["unbuilt_use_code_records"]
        + attrs["excluded_records"]
        + attrs["scoreable_records"]
    )
    assert accounted == attrs["assess_records_total"] == 47_675


@needs_worcester
def test_worcester_geometry_is_mass_state_plane_and_nearly_complete(worcester):
    assert worcester.crs is not None
    assert worcester.crs.to_epsg() == 26986
    assert worcester.attrs["missing_geometry"] <= 5


@needs_worcester
def test_worcester_summary_is_internally_consistent(worcester):
    summary = summarise(worcester)
    assert summary["parcels"] == len(worcester)
    assert sum(summary["confidence"].values()) == summary["parcels"]
    assert sum(summary["source_split"].values()) == summary["parcels"]
    assert summary["use_codes_in_scope"] == 95
    assert summary["town_id"] == WORCESTER_TOWN_ID
    assert summary["total_sqft"] > 0


@needs_worcester
def test_worcester_loads_in_a_few_seconds(worcester):
    assert worcester.attrs["load_seconds"] < 5.0, worcester.attrs["load_seconds"]


@needs_worcester
def test_load_municipality_is_reproducible(worcester):
    again = load_municipality(WORCESTER_DIR, WORCESTER_TOWN_ID)
    pd.testing.assert_frame_equal(
        pd.DataFrame(worcester.drop(columns="geometry")),
        pd.DataFrame(again.drop(columns="geometry")),
    )


@needs_worcester
def test_a_directory_with_no_l3_files_raises(tmp_path):
    with pytest.raises(IngestError, match="TaxPar"):
        load_municipality(tmp_path, WORCESTER_TOWN_ID)


def test_a_missing_directory_raises():
    with pytest.raises(IngestError, match="not a directory"):
        load_municipality("/nonexistent/l3/dir", WORCESTER_TOWN_ID)
