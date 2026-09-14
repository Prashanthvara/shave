"""The siting screen: a screen-out, not a green light."""

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

from shave import siting
from shave.assumptions import MIN_WALL_RUN_FT

FT_PER_M = 1 / 0.3048


def _parcels(**geoms) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"loc_id": list(geoms)}, geometry=list(geoms.values()), crs="EPSG:26986"
    )


def _structures(*geoms) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"STRUCT_ID": [f"S{i}" for i in range(len(geoms))]},
        geometry=list(geoms), crs="EPSG:26986",
    )


# --- the spec's three cases ------------------------------------------------


def test_a_zero_lot_line_building_has_no_clear_wall():
    """Spec test plan: zero-lot-line -> 0 ft."""
    parcel = box(0, 0, 30, 30)
    roof = box(0, 0, 30, 30)

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft == 0.0
    assert result.segment is None
    assert result.bearing_deg is None


def test_a_footprint_that_fills_the_parcel_has_no_clear_wall():
    """Spec test plan: footprint ~= parcel. Half a metre of side yard is not
    ten feet of working space."""
    parcel = box(0, 0, 30, 30)
    roof = box(0.5, 0.5, 29.5, 29.5)

    assert siting.wall_run(parcel, [roof], [roof]).run_ft == 0.0


def test_near_collinear_vertices_are_merged_before_measuring():
    """Spec test plan: collinear merge on a noisy roofprint. Imagery-derived
    walls zig-zag by tens of centimetres every metre; unmerged, a 30 m wall is
    thirty 1 m walls and the longest run would be 1 m."""
    bottom = [(float(x), 20.0 + (0.2 if x % 2 else 0.0)) for x in range(31)]
    roof = Polygon(bottom + [(30.0, 40.0), (0.0, 40.0)])
    parcel = box(0, 0, 30, 40)

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft > 90.0
    assert result.bearing_deg == 180


# --- the measurement itself ------------------------------------------------


def test_a_clear_south_yard_gives_the_full_wall_and_its_bearing():
    parcel = box(0, 0, 30, 40)
    roof = box(0, 20, 30, 40)  # flush to three lot lines, 20 m yard to the south

    result = siting.wall_run(parcel, [roof], [roof])

    assert result.run_ft == pytest.approx(30 * FT_PER_M, abs=0.1)
    assert result.bearing_deg == 180
    (x1, y1), (x2, y2) = result.segment.coords
    assert (y1, y2) == (pytest.approx(20.0), pytest.approx(20.0))
    assert abs(x2 - x1) == pytest.approx(30.0)


def test_a_shed_in_the_yard_breaks_the_run():
    """An obstruction is anything with a roof, including the site's own
    outbuildings."""
    parcel = box(0, 0, 30, 40)
    roof = box(0, 20, 30, 40)
    shed = box(12.5, 17.0, 17.5, 19.5)

    result = siting.wall_run(parcel, [roof], [roof, shed])

    # cells 12..17 touch the shed, leaving two 12 m runs either side
    assert result.run_ft == pytest.approx(12 * FT_PER_M, abs=0.1)


def test_screen_gives_every_parcel_a_status_and_never_a_green_light():
    parcels = _parcels(
        A=box(0, 0, 30, 40),        # clear south yard
        B=box(100, 0, 130, 30),     # zero lot line
        C=box(200, 0, 230, 30),     # empty lot
        D=None,                     # no polygon
    )
    structures = _structures(box(0, 20, 30, 40), box(100, 0, 130, 30))

    out = siting.screen(parcels, structures).set_index("loc_id")

    assert list(out.reset_index().columns) == list(siting.SCREEN_COLUMNS)
    assert out.loc["A", "siting"] == "clear"
    assert out.loc["A", "roofprint_count"] == 1
    assert out.loc["A", "roofprint_sqft"] == pytest.approx(600 * siting.SQFT_PER_SQM, abs=1)
    assert out.loc["B", "siting"] == "screened_out"
    assert out.loc["B", "wall_run_ft"] == 0.0
    assert out.loc["C", "siting"] == "no_roofprint"
    assert out["wall_run_ft"].isna()["C"], "no roof means no measurement, not 0 ft"
    assert out.loc["D", "siting"] == "no_geometry"
    assert set(out["siting"]) <= set(siting.SITING_STATUSES)
    assert MIN_WALL_RUN_FT > 0


def test_a_roof_straddling_a_lot_line_is_counted_once():
    """Assigned to the parcel holding its representative point, never to both."""
    parcels = _parcels(L=box(0, 0, 10, 10), R=box(10, 0, 20, 10))
    structures = _structures(box(3, 2, 13, 8))  # 70% of it on L

    assigned = siting.assign_roofprints(parcels, structures)

    assert list(assigned.get("L", [])) == [0]
    assert "R" not in assigned.index


def test_the_download_address_and_local_path_follow_the_massgis_pattern():
    assert siting.structures_url(348) == (
        "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
        "shapefiles/structures/structures_poly_348.zip"
    )
    assert str(siting.structures_path(348)) == (
        "data/raw/M348_STRUCTURES/structures_poly_348.shp"
    )


def test_a_layer_in_the_wrong_crs_is_refused(tmp_path):
    wrong = _structures(box(0, 0, 1, 1)).set_crs(4326, allow_override=True)
    path = tmp_path / "wrong.shp"
    wrong.to_file(path)

    with pytest.raises(ValueError, match="EPSG:26986"):
        siting.load_structures(path)


# --- real data -------------------------------------------------------------


def test_the_top_ranked_worcester_sites_measure_as_the_prototype_did(
    worcester_parcels, worcester_structures
):
    """RK Worcester Crossing and UMass Chan, measured 2026-09-13."""
    wanted = worcester_parcels[
        worcester_parcels["loc_id"].isin(["F_577265_2910122", "F_585218_2926290"])
    ][["loc_id", "geometry"]]

    out = siting.screen(wanted, worcester_structures).set_index("loc_id")

    one_cell_ft = 1.0 * FT_PER_M
    assert out.loc["F_577265_2910122", "wall_run_ft"] == pytest.approx(288.7, abs=one_cell_ft)
    assert out.loc["F_577265_2910122", "wall_bearing_deg"] == 228
    assert out.loc["F_585218_2926290", "wall_run_ft"] == pytest.approx(426.5, abs=one_cell_ft)
    assert out.loc["F_585218_2926290", "wall_bearing_deg"] == 100
    assert set(out["siting"]) == {"clear"}
