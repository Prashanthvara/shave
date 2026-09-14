"""The siting screen: a screen-out, not a green light.

Two cabinets side by side need roughly four metres of wall, and nearly every
commercial building in Massachusetts has that. A yes/no "sitable" flag would be
true almost everywhere and would claim a viability a domain expert can refute
from one aerial photo. So this module outputs the continuous fact instead --
the longest wall run with MIN_WALL_CLEARANCE_FT of unobstructed parcel-side
clearance, and the direction it faces -- and uses it only to screen out the
impossible: zero-lot-line buildings, footprints that fill the parcel, no side
yard.

The source is MassGIS Building Structures (2-D), STRUCTURES_POLY: roof outlines
digitised from aerial imagery. A roofprint includes overhangs, so the wall
below sits a little inside it and the clearance measured here is a slight
underestimate. That is the safe direction for a screen-out.

Measured on Worcester, 2026-09-13: 50,241 roofprints. A representative-point
join puts exactly one on 1,541 of 2,098 mapped parcels, several on 370 and
none on 187. The screen runs over every parcel in about five seconds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import LineString

from shave.assumptions import MIN_WALL_CLEARANCE_FT, MIN_WALL_RUN_FT

#: MassGIS publishes one shapefile per municipality at this address.
STRUCTURES_URL = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/"
    "shapefiles/structures/structures_poly_{town_id}.zip"
)

#: Massachusetts State Plane, metres: the CRS of TaxPar and STRUCTURES_POLY.
CRS_EPSG = 26986

M_PER_FT = 0.3048
FT_PER_M = 1.0 / M_PER_FT
SQFT_PER_SQM = FT_PER_M * FT_PER_M

#: Deviation below which a wall is treated as straight. Imagery-derived
#: roofprints carry dozens of spurious vertices; unmerged, a 30 m wall is thirty
#: 1 m walls and the longest run comes out as 1 m.
SIMPLIFY_M = 0.5

#: Length of each clearance cell tested along a wall.
STEP_M = 1.0

#: Gap between a wall and its cells, so a cell never touches the roof it is
#: measured from.
WALL_GAP_M = 0.05

SITING_STATUSES: tuple[str, ...] = ("clear", "screened_out", "no_roofprint", "no_geometry")

SCREEN_COLUMNS: tuple[str, ...] = (
    "loc_id", "roofprint_count", "roofprint_sqft", "wall_run_ft",
    "wall_bearing_deg", "wall_segment", "siting",
)


def structures_url(town_id: int) -> str:
    return STRUCTURES_URL.format(town_id=int(town_id))


def structures_path(town_id: int, root: str | Path = "data/raw") -> Path:
    tid = int(town_id)
    return Path(root) / f"M{tid}_STRUCTURES" / f"structures_poly_{tid}.shp"


def load_structures(path: str | Path) -> gpd.GeoDataFrame:
    """`STRUCT_ID` and geometry, in EPSG:26986. Refuses any other CRS: a
    metre-based clearance test on degrees would pass everything."""
    gdf = pyogrio.read_dataframe(path, columns=["STRUCT_ID"])
    epsg = gdf.crs.to_epsg() if gdf.crs is not None else None
    if epsg != CRS_EPSG:
        raise ValueError(f"{path}: expected EPSG:{CRS_EPSG}, got {gdf.crs}")
    keep = gdf.geometry.notna() & ~gdf.geometry.is_empty
    return gdf.loc[keep].reset_index(drop=True)


def assign_roofprints(parcels: gpd.GeoDataFrame, structures: gpd.GeoDataFrame) -> pd.Series:
    """Row positions in `structures`, grouped by the parcel that holds each
    roof's representative point.

    A roof straddling a lot line is counted once, never on both parcels.
    Measured on Worcester this leaves fewer parcels roofless (187) than
    assigning by majority overlap (214). Parcels with no roof are absent from
    the result.
    """
    mapped = parcels.loc[
        parcels.geometry.notna() & ~parcels.geometry.is_empty, ["loc_id", "geometry"]
    ]
    points = gpd.GeoDataFrame(
        {"row": np.arange(len(structures))},
        geometry=structures.geometry.representative_point(),
        crs=structures.crs,
    )
    joined = gpd.sjoin(points, mapped, predicate="within", how="inner")
    return joined.groupby("loc_id")["row"].apply(list)


@dataclass(frozen=True)
class WallRun:
    #: Longest unbroken wall with full clearance, in feet. 0.0 when none.
    run_ft: float
    #: The direction that wall faces, degrees clockwise from grid north.
    bearing_deg: int | None
    #: The run itself, along the wall, in EPSG:26986.
    segment: LineString | None


def _longest_true_run(ok: np.ndarray) -> tuple[int, int]:
    """(length, start index) of the longest run of consecutive True values."""
    best_len = best_start = current = 0
    for i, passed in enumerate(ok):
        current = current + 1 if passed else 0
        if current > best_len:
            best_len, best_start = current, i - current + 1
    return best_len, best_start


def wall_run(parcel, roofs, obstacles) -> WallRun:
    """The longest wall on `roofs` with clearance to the parcel line.

    Each exterior edge of each simplified roof is cut into STEP_M cells. A cell
    is the rectangle from just off the wall out to MIN_WALL_CLEARANCE_FT; it
    passes when it lies inside the parcel and touches no obstacle. The answer
    is the longest unbroken chain of passing cells on any one edge.

    `obstacles` is every roofprint touching the parcel, including `roofs`
    themselves: an L-shaped building's own wing blocks the wall in its corner,
    and a neighbour's garage across the lot line blocks just as well.
    """
    clearance = MIN_WALL_CLEARANCE_FT * M_PER_FT
    shapely.prepare(parcel)
    blocking = shapely.union_all(list(obstacles)) if len(obstacles) else None
    if blocking is not None:
        shapely.prepare(blocking)

    best = WallRun(0.0, None, None)
    for roof in roofs:
        simple = shapely.simplify(roof, SIMPLIFY_M, preserve_topology=True)
        for poly in shapely.get_parts(simple):
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
            coords = np.asarray(poly.exterior.coords)
            if not poly.exterior.is_ccw:
                coords = coords[::-1]
            for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
                length = math.hypot(x2 - x1, y2 - y1)
                n = int(length // STEP_M)
                if n == 0:
                    continue
                ux, uy = (x2 - x1) / length, (y2 - y1) / length
                nx, ny = uy, -ux  # the outward normal of a counter-clockwise ring
                k = np.arange(n)
                ax, ay = x1 + ux * k * STEP_M, y1 + uy * k * STEP_M
                bx, by = ax + ux * STEP_M, ay + uy * STEP_M
                rings = np.stack(
                    [
                        np.c_[ax + nx * WALL_GAP_M, ay + ny * WALL_GAP_M],
                        np.c_[bx + nx * WALL_GAP_M, by + ny * WALL_GAP_M],
                        np.c_[bx + nx * clearance, by + ny * clearance],
                        np.c_[ax + nx * clearance, ay + ny * clearance],
                        np.c_[ax + nx * WALL_GAP_M, ay + ny * WALL_GAP_M],
                    ],
                    axis=1,
                )
                cells = shapely.polygons(rings)
                ok = shapely.contains(parcel, cells)
                if blocking is not None:
                    ok &= ~shapely.intersects(blocking, cells)
                cell_count, start = _longest_true_run(ok)
                run_m = cell_count * STEP_M
                run_ft = round(run_m * FT_PER_M, 1)
                if run_ft > best.run_ft:
                    sx, sy = x1 + ux * start * STEP_M, y1 + uy * start * STEP_M
                    best = WallRun(
                        run_ft=run_ft,
                        bearing_deg=int(round(math.degrees(math.atan2(nx, ny)))) % 360,
                        segment=LineString([(sx, sy), (sx + ux * run_m, sy + uy * run_m)]),
                    )
    return best


def screen(parcels: gpd.GeoDataFrame, structures: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per parcel, in input order, with exactly SCREEN_COLUMNS.

    `clear` means only "not screened out". Nothing here can see loading docks,
    fire lanes, egress, wall openings, setbacks or the service entrance.
    """
    epsg = parcels.crs.to_epsg() if parcels.crs is not None else None
    if epsg != CRS_EPSG:
        raise ValueError(f"parcels: expected EPSG:{CRS_EPSG}, got {parcels.crs}")

    assigned = assign_roofprints(parcels, structures)
    geoms = list(structures.geometry)
    index = structures.sindex

    rows = []
    for loc_id, parcel in zip(parcels["loc_id"], parcels.geometry):
        if parcel is None or parcel.is_empty:
            rows.append((loc_id, 0, 0.0, None, None, None, "no_geometry"))
            continue
        own = list(assigned.get(loc_id, []))
        if not own:
            rows.append((loc_id, 0, 0.0, None, None, None, "no_roofprint"))
            continue
        area_sqft = round(sum(geoms[i].area for i in own) * SQFT_PER_SQM, 0)
        touching = index.query(parcel, predicate="intersects")
        result = wall_run(parcel, [geoms[i] for i in own], [geoms[i] for i in touching])
        status = "clear" if result.run_ft >= MIN_WALL_RUN_FT else "screened_out"
        rows.append((
            loc_id, len(own), area_sqft, result.run_ft,
            result.bearing_deg, result.segment, status,
        ))
    return pd.DataFrame(rows, columns=list(SCREEN_COLUMNS))
