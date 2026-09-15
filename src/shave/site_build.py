"""What the build writes: one ranked payload per town, and an index of towns.

Towns are never merged into one ranked list, for the same reason the two
source lists are not: each town's payload ranks within itself, draws its own
map frame, and loads only when a reader asks for that town.
"""

from __future__ import annotations

from pathlib import Path

from shave import export, mapgeo, site_data, towns


def town_data_path(out: Path | str, slug: str) -> Path:
    return Path(out) / "towns" / slug / "ranked.json"


def town_payload(town: towns.Town, parcels, scored) -> dict:
    """One town's enriched export, in that town's own map frame."""
    parcels = parcels.copy()
    # representative_point, not centroid: a centroid of an L-shaped or ring
    # parcel can land outside it, which puts a marker in someone else's yard.
    points = parcels.geometry.to_crs(4326).representative_point()
    parcels["lon"] = points.x
    parcels["lat"] = points.y
    fy = parcels["assess_fy"].dropna()
    meta = {
        "town_id": town.town_id,
        "name": town.name,
        "slug": town.slug,
        "assess_fy": int(fy.iloc[0]) if len(fy) else None,
    }
    raw = export.build_export(scored, parcels, town=meta)
    frame = mapgeo.frame_for(parcels)
    enriched = site_data.enrich(
        raw, scored,
        paths=mapgeo.paths_for(parcels, frame),
        view_box=frame.view_box,
        walls=mapgeo.walls_for(parcels, frame),
    )
    return {k: v for k, v in enriched.items() if k != "method"}


def index_payload(payloads: list[dict]) -> dict:
    """The towns the page can show, in order; the first is the default."""
    return {
        "site_schema_version": site_data.SITE_SCHEMA_VERSION,
        "default": payloads[0]["town"]["slug"],
        "towns": [{**p["town"], "counts": p["counts"]} for p in payloads],
    }
