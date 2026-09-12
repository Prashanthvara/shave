"""A parcel polygon, ready for the page to inject.

Simplification, projection and string-building all happen here, at build
time. The page receives a finished `d` attribute and does no geometry, which
is the same rule that keeps the sparkline honest: every figure on screen was
computed by the pipeline, not by a second implementation in JavaScript.

The projection is equirectangular with a cosine correction on longitude. At
city scale over a 0.13 degree span that is indistinguishable from a proper
projection, and it needs no dependency. A degree of longitude at 42 North is
about 0.74 of a degree of latitude on the ground; without that correction
Worcester renders visibly wide and every parcel is the wrong shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: About 2 m on the ground -- finer than a parcel boundary needs at city
#: scale. Measured over Worcester's 562 exported parcels: 22,364 raw exterior
#: vertices become 5,583, roughly 87 KB of path text.
SIMPLIFY_TOLERANCE_DEG = 0.00002

#: SVG user units across. Height follows from the data's own aspect ratio;
#: Worcester comes out portrait at 818.
VIEW_WIDTH = 620

#: Coordinates are rounded to this many decimals. At 620 units across a
#: 0.13 degree span, 0.1 of a unit is under two metres.
COORD_DECIMALS = 1


@dataclass(frozen=True)
class MapFrame:
    """The bounding box and the SVG canvas it maps onto."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    width: float
    height: float

    @property
    def view_box(self) -> str:
        return f"0 0 {self.width:g} {self.height:g}"


def frame_for_bounds(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    width: float = VIEW_WIDTH,
) -> MapFrame:
    """Derive the canvas height from the ground aspect ratio of the bounds."""
    mid_lat = (min_lat + max_lat) / 2.0
    ground_w = (max_lon - min_lon) * math.cos(math.radians(mid_lat))
    ground_h = max_lat - min_lat
    if ground_w <= 0 or ground_h <= 0:
        raise ValueError(f"degenerate bounds: {min_lon},{min_lat},{max_lon},{max_lat}")
    height = width * (ground_h / ground_w)
    return MapFrame(min_lon, min_lat, max_lon, max_lat, float(width), float(height))


def frame_for(gdf, width: float = VIEW_WIDTH) -> MapFrame:
    """The frame covering every usable geometry in `gdf`, in EPSG:4326.

    Null and empty geometries are excluded rather than allowed to poison the
    bounds -- one Worcester parcel has no geometry, and `total_bounds` over a
    frame containing it returns NaN for everything.
    """
    usable = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if usable.empty:
        raise ValueError("no usable geometry to build a map frame from")
    min_lon, min_lat, max_lon, max_lat = usable.to_crs(4326).total_bounds
    return frame_for_bounds(min_lon, min_lat, max_lon, max_lat, width=width)


def project(lon: float, lat: float, frame: MapFrame) -> tuple[float, float]:
    """Longitude/latitude to SVG user units. North is y=0, since SVG y grows
    downward and latitude grows upward."""
    fx = (lon - frame.min_lon) / (frame.max_lon - frame.min_lon)
    fy = (frame.max_lat - lat) / (frame.max_lat - frame.min_lat)
    return fx * frame.width, fy * frame.height


def _ring(coords, frame: MapFrame) -> str:
    points = []
    for lon, lat in coords:
        x, y = project(lon, lat, frame)
        points.append(f"{round(x, COORD_DECIMALS)},{round(y, COORD_DECIMALS)}")
    if not points:
        return ""
    return "M" + points[0] + "".join("L" + p for p in points[1:]) + "Z"


def path_for(geom, frame: MapFrame) -> str:
    """One SVG `d` string for a polygon or multipolygon, exteriors only.

    Returns "" for null or empty geometry rather than raising: a parcel with
    no polygon still belongs in the ranked table, it simply has nothing to
    draw. Interior rings are dropped -- a hole in a parcel is invisible at
    this scale and doubles the vertex count.
    """
    if geom is None or getattr(geom, "is_empty", True):
        return ""
    simple = geom.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
    if simple.is_empty:
        simple = geom
    if simple.geom_type == "Polygon":
        parts = [simple]
    elif simple.geom_type == "MultiPolygon":
        parts = list(simple.geoms)
    else:
        return ""
    return "".join(_ring(p.exterior.coords, frame) for p in parts if not p.is_empty)


def paths_for(gdf, frame: MapFrame) -> dict[str, str]:
    """`loc_id` to path string, for every row with usable geometry."""
    wgs = gdf.to_crs(4326)
    out: dict[str, str] = {}
    for loc_id, geom in zip(wgs["loc_id"], wgs.geometry):
        d = path_for(geom, frame)
        if d:
            out[str(loc_id)] = d
    return out
