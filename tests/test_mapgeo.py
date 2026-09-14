"""Polygons become SVG path strings at build time, never in the browser."""

import pytest
from shapely.geometry import MultiPolygon, Polygon

from shave import mapgeo


def _frame():
    return mapgeo.MapFrame(
        min_lon=-71.9, min_lat=42.2, max_lon=-71.7, max_lat=42.4,
        width=620.0, height=818.0,
    )


def test_projection_puts_the_northwest_corner_at_the_origin():
    """SVG y grows downward and latitude grows upward, so north is y=0."""
    x, y = mapgeo.project(-71.9, 42.4, _frame())
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_projection_puts_the_southeast_corner_at_the_far_edge():
    frame = _frame()
    x, y = mapgeo.project(-71.7, 42.2, frame)
    assert x == pytest.approx(frame.width, abs=1e-6)
    assert y == pytest.approx(frame.height, abs=1e-6)


def test_latitude_is_not_stretched_relative_to_longitude():
    """A degree of longitude is shorter than a degree of latitude at 42 North.
    Without the cosine correction Worcester comes out visibly wide and every
    parcel is the wrong shape."""
    frame = mapgeo.frame_for_bounds(-71.9, 42.2, -71.7, 42.4, width=620.0)
    # 0.2 deg lon x 0.2 deg lat at ~42.3N is taller than it is wide.
    assert frame.height > frame.width
    assert frame.width / frame.height == pytest.approx(0.74, abs=0.02)


def test_a_square_polygon_becomes_a_closed_path():
    square = Polygon([(-71.8, 42.3), (-71.75, 42.3), (-71.75, 42.35), (-71.8, 42.35)])
    d = mapgeo.path_for(square, _frame())

    assert d.startswith("M")
    assert d.endswith("Z")
    assert "L" in d
    assert "nan" not in d.lower()


def test_a_multipolygon_yields_one_subpath_per_part():
    a = Polygon([(-71.8, 42.3), (-71.79, 42.3), (-71.79, 42.31), (-71.8, 42.31)])
    b = Polygon([(-71.75, 42.25), (-71.74, 42.25), (-71.74, 42.26), (-71.75, 42.26)])
    d = mapgeo.path_for(MultiPolygon([a, b]), _frame())

    assert d.count("M") == 2
    assert d.count("Z") == 2


def test_null_and_empty_geometry_return_an_empty_string_not_a_crash():
    """One Worcester parcel has no geometry. It must still reach the table."""
    assert mapgeo.path_for(None, _frame()) == ""
    assert mapgeo.path_for(Polygon(), _frame()) == ""


def test_coordinates_are_rounded_so_the_payload_stays_small():
    """Full float precision would roughly triple the geometry payload for
    sub-millimetre detail nobody can see at city scale."""
    square = Polygon([(-71.8, 42.3), (-71.75, 42.3), (-71.75, 42.35), (-71.8, 42.35)])
    d = mapgeo.path_for(square, _frame())

    for token in d.replace("M", " ").replace("L", " ").replace("Z", " ").split():
        for part in token.split(","):
            _, _, decimals = part.partition(".")
            assert len(decimals) <= 1, f"{part} carries more precision than 0.1 units"


def test_a_tiny_parcel_is_grown_to_a_legible_minimum():
    """Parcel area is an accidental third encoding. Measured on Worcester it
    correlated with floor area, so the map said 'big is good' twice over --
    large parcels were both darker and physically larger, and 74 of the 172
    sweet-spot sites rendered under 4 units across. Growing the small ones
    about their own centroid stops area encoding anything."""
    tiny = Polygon([(-71.8000, 42.3000), (-71.7999, 42.3000),
                    (-71.7999, 42.3001), (-71.8000, 42.3001)])
    frame = _frame()

    raw = mapgeo.path_for(tiny, frame, min_span=0.0)
    grown = mapgeo.path_for(tiny, frame, min_span=mapgeo.MIN_SPAN_UNITS)

    def span(d):
        import re
        n = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
        xs, ys = n[0::2], n[1::2]
        return max(max(xs) - min(xs), max(ys) - min(ys))

    assert span(raw) < mapgeo.MIN_SPAN_UNITS
    assert span(grown) == pytest.approx(mapgeo.MIN_SPAN_UNITS, rel=0.02)


def test_growing_keeps_the_parcel_where_it_is():
    """A parcel moved to make it visible would be a lie about its location."""
    tiny = Polygon([(-71.8000, 42.3000), (-71.7999, 42.3000),
                    (-71.7999, 42.3001), (-71.8000, 42.3001)])
    frame = _frame()

    def centre(d):
        import re
        n = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
        xs, ys = n[0::2], n[1::2]
        return (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    cx0, cy0 = centre(mapgeo.path_for(tiny, frame, min_span=0.0))
    cx1, cy1 = centre(mapgeo.path_for(tiny, frame, min_span=mapgeo.MIN_SPAN_UNITS))
    assert cx1 == pytest.approx(cx0, abs=0.2)
    assert cy1 == pytest.approx(cy0, abs=0.2)


def test_a_parcel_already_large_enough_is_left_alone():
    big = Polygon([(-71.80, 42.30), (-71.78, 42.30), (-71.78, 42.32), (-71.80, 42.32)])
    frame = _frame()
    assert mapgeo.path_for(big, frame, min_span=mapgeo.MIN_SPAN_UNITS) == \
           mapgeo.path_for(big, frame, min_span=0.0)
