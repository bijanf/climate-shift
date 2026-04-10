"""
GLIMS glacier outline acquisition via Google Earth Engine.

The full GLIMS database (786,000+ glacier outlines worldwide) is available
as `ee.FeatureCollection("GLIMS/current")` in Google Earth Engine. This
module provides convenient functions to fetch glacier polygons by location
and cache them locally as GeoJSON for the paper pipeline.

Why GEE instead of direct download?
  - The GLIMS direct download (~500 MB) is slow and the URL is unstable
  - We already authenticate to GEE for satellite imagery
  - We only need ~20 specific polygons, not the full database
  - GEE returns just what we ask for, in seconds

Notes
-----
- GLIMS contains multi-temporal outlines per glacier (different survey
  dates), so a single glacier can appear N times. We pick the most recent
  outline by analysis date.
- `db_area` is the database-reported area in km² (not the recomputed
  geometric area). Use this for matching, but compute geometry area
  in code for reproducibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

from ..config import GLIMS_DIR

GLIMS_GEE_ASSET = "GLIMS/current"


# ── Lazy GEE init (matches the pattern in acquire/landsat.py) ────────────────
_ee = None


def _get_ee():
    global _ee
    if _ee is not None:
        return _ee
    try:
        import ee
    except ImportError as exc:
        raise ImportError(
            "earthengine-api not installed. Run: pip install earthengine-api"
        ) from exc
    try:
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
    except Exception:
        ee.Authenticate()
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
    _ee = ee
    return ee


# ── Polygon fetching ─────────────────────────────────────────────────────────


def fetch_largest_polygon_in_bbox(bbox, max_features=10):
    """Fetch the GLIMS polygon with the largest area within a bounding box.

    For a registry glacier, the largest polygon at the named location is
    almost always the glacier we want. Multi-temporal outlines from
    different survey dates are de-duplicated by glac_id, keeping the
    most recent.

    Parameters
    ----------
    bbox : tuple
        (west, south, east, north) in degrees.
    max_features : int
        How many candidates to fetch (we then pick the largest by glac_id).

    Returns
    -------
    geopandas.GeoDataFrame
        Single-row GeoDataFrame with the largest polygon, or empty if
        no glaciers were found in the bbox.
    """
    ee = _get_ee()

    w, s, e, n = bbox
    aoi = ee.Geometry.Rectangle([w, s, e, n])
    glims = ee.FeatureCollection(GLIMS_GEE_ASSET).filterBounds(aoi)

    # Sort by db_area descending; this brings the named glacier to the top
    candidates = glims.sort("db_area", False).limit(max_features).getInfo()

    if not candidates.get("features"):
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # De-duplicate by glac_id, keeping the entry with the latest analysis time
    by_id = {}
    for feat in candidates["features"]:
        props = feat["properties"]
        glac_id = props.get("glac_id")
        if not glac_id:
            continue

        anlys = props.get("anlys_time") or ""
        existing = by_id.get(glac_id)
        if existing is None or (anlys > existing[0].get("anlys_time", "")):
            by_id[glac_id] = (props, feat["geometry"])

    if not by_id:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    # Pick the largest of the deduplicated set
    largest_id = max(by_id, key=lambda k: by_id[k][0].get("db_area", 0))
    props, geom = by_id[largest_id]

    # Build GeoDataFrame from the GeoJSON geometry
    from shapely.geometry import shape

    gdf = gpd.GeoDataFrame(
        [props],
        geometry=[shape(geom)],
        crs="EPSG:4326",
    )
    return gdf


def fetch_glims_for_glacier(glacier_config, cache_dir=None):
    """Fetch the GLIMS polygon for a registry glacier, caching the result.

    Parameters
    ----------
    glacier_config : dict
        A glacier entry from GLACIER_REGISTRY (must have 'bbox' and 'name').
    cache_dir : Path, optional
        Where to save the cached GeoJSON. Defaults to GLIMS_DIR.

    Returns
    -------
    geopandas.GeoDataFrame
        Single-row GeoDataFrame for the glacier polygon. May be empty if
        no GLIMS polygons exist at this location.
    """
    if cache_dir is None:
        cache_dir = GLIMS_DIR
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    safe_name = glacier_config["name"].replace(" ", "_").replace("/", "-").lower()
    cache_path = cache_dir / f"glims_{safe_name}.geojson"

    if cache_path.exists():
        try:
            gdf = gpd.read_file(cache_path)
            if len(gdf) > 0:
                return gdf
        except Exception:
            pass

    print(f"  Fetching GLIMS polygon for {glacier_config['name']} from GEE...")
    gdf = fetch_largest_polygon_in_bbox(glacier_config["bbox"])

    if len(gdf) > 0:
        gdf.to_file(cache_path, driver="GeoJSON")
        area_db = gdf.iloc[0].get("db_area", float("nan"))
        glac_name = gdf.iloc[0].get("glac_name", "Unnamed")
        print(f"    Found: {glac_name} (db_area={area_db:.2f} km²)")
    else:
        print(f"    No GLIMS polygons found in bbox {glacier_config['bbox']}")

    return gdf


def fetch_all_registry_glaciers(registry=None, force=False):
    """Fetch GLIMS polygons for every glacier in the registry.

    Parameters
    ----------
    registry : dict, optional
        Override the default GLACIER_REGISTRY.
    force : bool
        If True, ignore cached files and re-fetch.

    Returns
    -------
    dict
        {glacier_key: GeoDataFrame} mapping. Empty GeoDataFrames are kept
        for glaciers that have no GLIMS coverage.
    """
    from ..config import GLACIER_REGISTRY

    if registry is None:
        registry = GLACIER_REGISTRY

    results = {}
    for key, glacier in registry.items():
        if force:
            safe_name = glacier["name"].replace(" ", "_").replace("/", "-").lower()
            cache_path = GLIMS_DIR / f"glims_{safe_name}.geojson"
            if cache_path.exists():
                cache_path.unlink()
        results[key] = fetch_glims_for_glacier(glacier)

    return results


def get_polygon_area_km2(gdf):
    """Compute the geometric area of a polygon in km² (Mollweide equal area).

    Parameters
    ----------
    gdf : GeoDataFrame
        Single-row GeoDataFrame with a polygon geometry.

    Returns
    -------
    float
        Area in km², or nan if empty.
    """
    if len(gdf) == 0:
        return float("nan")
    # Mollweide is an equal-area projection — gives accurate areas globally
    gdf_ea = gdf.to_crs("ESRI:54009")
    return float(gdf_ea.geometry.area.sum() / 1e6)
