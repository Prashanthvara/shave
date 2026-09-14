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

#: Smallest span, in SVG units, at which a parcel is legible and clickable.
#: Parcel AREA is an accidental third encoding that DESIGN.md never specified,
#: and on Worcester it correlates with floor area: the map said "big is good"
#: twice over, since large parcels were both darker (more dollars, more fill
#: opacity) and physically larger. Measured before this was added: the median
#: parcel spanned 6.3 units of 620, sweet-spot parcels 4.3 against 7.8 for
#: everything else, and 74 of the 172 sweet-spot sites rendered under 4 units.
#: Growing the small ones about their own centroid stops area encoding
#: anything, so only the two designed channels speak. The legend discloses it.
MIN_SPAN_UNITS = 9.0

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


def _ring(coords, frame: MapFrame, min_span: float) -> str:
    projected = [project(lon, lat, frame) for lon, lat in coords]
    projected = _grown(projected, min_span)
    points = [f"{round(x, COORD_DECIMALS)},{round(y, COORD_DECIMALS)}" for x, y in projected]
    if not points:
        return ""
    return "M" + points[0] + "".join("L" + p for p in points[1:]) + "Z"


def _growth(points: list[tuple[float, float]], min_span: float) -> tuple[float, float, float]:
    """The centre and scale that grow a projected ring up to `min_span`.

    Scale is 1.0 when the ring is already large enough. Split out from
    `_grown` so a wall on the parcel can use exactly the same transform.
    """
    if min_span <= 0 or not points:
        return 0.0, 0.0, 1.0
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span >= min_span or span <= 0:
        return 0.0, 0.0, 1.0
    return (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0, min_span / span


def _grown(points: list[tuple[float, float]], min_span: float) -> list[tuple[float, float]]:
    """Scale a projected ring about its own centre up to `min_span`.

    Position is preserved exactly -- a parcel moved to make it visible would
    be a lie about where it is. Only its drawn size changes.
    """
    cx, cy, scale = _growth(points, min_span)
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points]


def path_for(geom, frame: MapFrame, min_span: float = MIN_SPAN_UNITS) -> str:
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
    return "".join(
        _ring(p.exterior.coords, frame, min_span) for p in parts if not p.is_empty
    )


def paths_for(gdf, frame: MapFrame) -> dict[str, str]:
    """`loc_id` to path string, for every row with usable geometry."""
    wgs = gdf.to_crs(4326)
    out: dict[str, str] = {}
    for loc_id, geom in zip(wgs["loc_id"], wgs.geometry):
        d = path_for(geom, frame)
        if d:
            out[str(loc_id)] = d
    return out


def wall_path_for(parcel, segment, frame: MapFrame, min_span: float = MIN_SPAN_UNITS) -> str:
    """The clear wall run as an open SVG path, in the parcel's drawn space.

    Both arguments are EPSG:4326. The parcel is simplified exactly as
    `path_for` simplifies it, and the wall takes the growth of whichever part
    of the parcel it lies on, so a small parcel's wall stays on its building.
    """
    if parcel is None or segment is None or parcel.is_empty or segment.is_empty:
        return ""
    simple = parcel.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
    if simple.is_empty:
        simple = parcel
    parts = [simple] if simple.geom_type == "Polygon" else list(getattr(simple, "geoms", []))
    if not parts:
        return ""
    middle = segment.interpolate(0.5, normalized=True)
    part = min(parts, key=lambda p: p.distance(middle))
    ring = [project(lon, lat, frame) for lon, lat in part.exterior.coords]
    cx, cy, scale = _growth(ring, min_span)
    points = []
    for lon, lat in segment.coords:
        x, y = project(lon, lat, frame)
        gx, gy = cx + (x - cx) * scale, cy + (y - cy) * scale
        points.append(f"{round(gx, COORD_DECIMALS)},{round(gy, COORD_DECIMALS)}")
    return "M" + points[0] + "".join("L" + p for p in points[1:])


def walls_for(gdf, frame: MapFrame) -> dict[str, str]:
    """`loc_id` to wall path, for every parcel whose siting screen found a run."""
    if "wall_segment" not in gdf.columns:
        return {}
    has = gdf[gdf["wall_segment"].notna() & gdf.geometry.notna()]
    if has.empty:
        return {}
    import geopandas as gpd  # local: mapgeo otherwise needs only shapely objects

    parcels = has.geometry.to_crs(4326)
    segments = gpd.GeoSeries(list(has["wall_segment"]), crs=has.crs).to_crs(4326)
    out: dict[str, str] = {}
    for loc_id, parcel, segment in zip(has["loc_id"], parcels, segments):
        d = wall_path_for(parcel, segment, frame)
        if d:
            out[str(loc_id)] = d
    return out
