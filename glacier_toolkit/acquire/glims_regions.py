"""
Region-level GLIMS glacier polygon batch loading from Google Earth Engine.

This module supports the Phase 2 (Nature Geoscience) paper analysis by
fetching thousands of glacier polygons at once for a given region. Unlike
``glims_gee.py`` which fetches one glacier at a time, this module is
designed for batch processing of entire RGI regions.

The 19 RGI O1 regions and their approximate glacier counts:

    01  Alaska                            ~27,000
    02  Western Canada and US             ~18,800
    03  Arctic Canada North                ~4,500
    04  Arctic Canada South                ~7,400
    05  Greenland Periphery               ~20,000
    06  Iceland                            ~600
    07  Svalbard                          ~1,600
    08  Scandinavia                       ~3,400
    09  Russian Arctic                    ~1,000
    10  North Asia                        ~5,200
    11  Central Europe                    ~3,900
    12  Caucasus and Middle East          ~1,900
    13  Central Asia                     ~54,400
    14  South Asia West                  ~27,900
    15  South Asia East                  ~13,100
    16  Low Latitudes                     ~2,900
    17  Southern Andes                   ~15,900
    18  New Zealand                       ~3,500
    19  Antarctic and Subantarctic        ~2,750

Total: ~215,547 glaciers (matches Hugonnet 2021's n=217,175 to within 1%).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import GLIMS_DIR

GLIMS_GEE_ASSET = "GLIMS/current"

# RGI O1 region bounding boxes (west, south, east, north). These are
# generous bounding boxes that fully enclose each region. The actual GLIMS
# query will use these to filter the global FeatureCollection.
RGI_REGION_BBOX = {
    1: (-180, 50, -130, 72),  # Alaska
    2: (-140, 32, -103, 60),  # Western Canada/US
    3: (-120, 70, -50, 84),  # Arctic Canada North
    4: (-95, 60, -55, 75),  # Arctic Canada South
    5: (-75, 59, -10, 84),  # Greenland Periphery
    6: (-25, 63, -13, 67),  # Iceland
    7: (10, 74, 35, 81),  # Svalbard
    8: (4, 58, 28, 71),  # Scandinavia
    9: (35, 70, 110, 82),  # Russian Arctic
    10: (78, 45, 180, 78),  # North Asia
    11: (5, 42, 18, 49),  # Central Europe (Alps + Pyrenees)
    12: (35, 30, 60, 45),  # Caucasus + Middle East
    13: (65, 27, 105, 50),  # Central Asia (Pamir, Tien Shan)
    14: (65, 27, 81, 38),  # South Asia West (Hindu Kush, Karakoram)
    15: (74, 25, 105, 33),  # South Asia East (Himalaya)
    16: (-90, -25, -65, 12),  # Low Latitudes (tropical Andes, Africa)
    17: (-78, -56, -65, -16),  # Southern Andes (Patagonia)
    18: (165, -47, 180, -39),  # New Zealand
    19: (-180, -90, 180, -60),  # Antarctica
}

RGI_REGION_NAMES = {
    1: "Alaska",
    2: "Western Canada and US",
    3: "Arctic Canada North",
    4: "Arctic Canada South",
    5: "Greenland Periphery",
    6: "Iceland",
    7: "Svalbard",
    8: "Scandinavia",
    9: "Russian Arctic",
    10: "North Asia",
    11: "Central Europe",
    12: "Caucasus and Middle East",
    13: "Central Asia",
    14: "South Asia West",
    15: "South Asia East",
    16: "Low Latitudes",
    17: "Southern Andes",
    18: "New Zealand",
    19: "Antarctic and Subantarctic",
}


# ── Lazy GEE init ────────────────────────────────────────────────────────────

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


# ── Region-scale fetching ────────────────────────────────────────────────────


def fetch_region_glaciers(
    region_id,
    min_area_km2=1.0,
    max_glaciers=None,
    cache_dir=None,
    force=False,
):
    """Fetch all GLIMS glacier polygons in an RGI region.

    The default `min_area_km2=1.0` filters out tiny snow patches that are
    not real glaciers, dramatically reducing the size of the result while
    keeping all "real" glaciers.

    Parameters
    ----------
    region_id : int
        RGI O1 region ID (1-19). See RGI_REGION_NAMES.
    min_area_km2 : float
        Minimum db_area to include. Default 1.0 km² filters tiny patches.
    max_glaciers : int, optional
        Hard cap on number of glaciers (for testing).
    cache_dir : Path, optional
        Local cache for the resulting GeoJSON. Defaults to GLIMS_DIR.
    force : bool
        Re-fetch even if cached.

    Returns
    -------
    geopandas.GeoDataFrame
        All glaciers in the region with full GLIMS metadata. May contain
        multi-temporal duplicates per glac_id (use de-duplication helpers).
    """
    if region_id not in RGI_REGION_BBOX:
        raise ValueError(f"Unknown RGI region {region_id}. Valid: 1-19")

    if cache_dir is None:
        cache_dir = GLIMS_DIR
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = cache_dir / f"glims_region_{region_id:02d}_min{min_area_km2:g}km2.geojson"

    if cache_path.exists() and not force:
        try:
            gdf = gpd.read_file(cache_path)
            print(f"  Loaded cached region {region_id}: {len(gdf)} polygons")
            return gdf
        except Exception:
            pass

    ee = _get_ee()
    bbox = RGI_REGION_BBOX[region_id]
    region_name = RGI_REGION_NAMES[region_id]

    print(f"  Fetching GLIMS region {region_id} ({region_name}) from GEE...")
    print(f"    bbox = {bbox}, min_area = {min_area_km2} km²")

    aoi = ee.Geometry.Rectangle(list(bbox))
    glims = ee.FeatureCollection(GLIMS_GEE_ASSET).filterBounds(aoi)

    # Filter by db_area to drop tiny patches
    glims = glims.filter(ee.Filter.gte("db_area", min_area_km2))

    if max_glaciers:
        glims = glims.limit(max_glaciers)

    # Pull down as a Python dict (FeatureCollection.getInfo)
    # For very large regions this may need to be split into chunks
    n = glims.size().getInfo()
    print(f"    Found {n} polygons")

    if n == 0:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    if n > 5000:
        print(f"    Warning: large fetch ({n} features). Splitting into chunks...")
        return _fetch_in_chunks(glims, n, bbox, cache_path)

    raw = glims.getInfo()
    gdf = _features_to_gdf(raw["features"])
    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"    Cached: {cache_path.name}")
    return gdf


def _fetch_recursive(glims_full, bbox, min_area_km2, depth=0, max_depth=8):
    """Recursively split a bbox until each subregion has <= 4500 features.

    GEE limits FeatureCollection.getInfo() to 5000 elements per call. We
    use a margin (4500) and recursively quad-split (2x2) any bbox that
    has too many glaciers.

    Parameters
    ----------
    glims_full : ee.FeatureCollection
        Pre-filtered GLIMS collection (with min_area filter applied).
    bbox : tuple
        (w, s, e, n) bounding box.
    min_area_km2 : float
        Used in printout.
    depth : int
        Recursion depth.
    max_depth : int
        Hard cap on recursion.

    Returns
    -------
    list of GeoDataFrame
        Concatenated frames for all sub-bboxes.
    """
    ee = _get_ee()
    w, s, e, n = bbox

    aoi = ee.Geometry.Rectangle([w, s, e, n])
    sub = glims_full.filterBounds(aoi)
    n_sub = sub.size().getInfo()

    indent = "      " + "  " * depth
    if n_sub == 0:
        return []

    if n_sub <= 4500 or depth >= max_depth:
        try:
            raw = sub.limit(5000).getInfo()
            features = raw.get("features", [])
            if len(features) == n_sub or depth >= max_depth:
                print(
                    f"{indent}fetch [{w:.1f},{s:.1f},{e:.1f},{n:.1f}] -> {len(features)} polygons"
                )
                return [_features_to_gdf(features)]
        except Exception as exc:
            print(f"{indent}fetch failed: {exc}")

    # Split into 4 quadrants
    mid_lon = (w + e) / 2
    mid_lat = (s + n) / 2
    print(f"{indent}split [{w:.1f},{s:.1f},{e:.1f},{n:.1f}] ({n_sub} polygons -> 4 quads)")

    quadrants = [
        (w, s, mid_lon, mid_lat),
        (mid_lon, s, e, mid_lat),
        (w, mid_lat, mid_lon, n),
        (mid_lon, mid_lat, e, n),
    ]

    out = []
    for quad in quadrants:
        out.extend(_fetch_recursive(glims_full, quad, min_area_km2, depth + 1, max_depth))
    return out


def _fetch_in_chunks(glims_fc, total, bbox, cache_path, chunk_size=4500):
    """Recursively split a large FeatureCollection fetch into bbox quadrants."""
    chunks = _fetch_recursive(glims_fc, bbox, min_area_km2=0)

    if not chunks:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    gdf = pd.concat(chunks, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")

    # De-duplicate by glac_id keeping largest
    if "glac_id" in gdf.columns and "db_area" in gdf.columns:
        gdf = (
            gdf.sort_values("db_area", ascending=False)
            .drop_duplicates("glac_id", keep="first")
            .reset_index(drop=True)
        )

    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"    Cached: {cache_path.name} ({len(gdf)} unique glaciers)")
    return gdf


def _features_to_gdf(features):
    """Convert a list of GeoJSON features to a GeoDataFrame."""
    from shapely.geometry import shape

    rows = []
    geoms = []
    for feat in features:
        rows.append(feat["properties"])
        geoms.append(shape(feat["geometry"]))

    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    return gdf


def deduplicate_by_largest(gdf):
    """Keep only the largest polygon per glac_id (historical maximum extent)."""
    if "glac_id" not in gdf.columns or "db_area" not in gdf.columns:
        return gdf
    return (
        gdf.sort_values("db_area", ascending=False)
        .drop_duplicates("glac_id", keep="first")
        .reset_index(drop=True)
    )


def stratified_sample(gdf, n_samples, by="db_area", seed=42):
    """Take a stratified sample across glacier size classes.

    Useful for proof-of-concept runs where the full population is too large.

    Parameters
    ----------
    gdf : GeoDataFrame
        Glaciers from a region.
    n_samples : int
        Total number of glaciers to sample.
    by : str
        Column to stratify on. Default 'db_area'.
    seed : int
        Random seed.

    Returns
    -------
    GeoDataFrame
        Stratified sample.
    """
    if len(gdf) <= n_samples:
        return gdf.copy()

    # Quartile bins
    bins = pd.qcut(gdf[by], q=4, duplicates="drop")
    samples_per_bin = n_samples // 4

    sampled = (
        gdf.groupby(bins, observed=True)
        .sample(n=samples_per_bin, random_state=seed, replace=False)
        .reset_index(drop=True)
    )
    return sampled


def get_centroid_lat_lon(gdf):
    """Compute centroid lat/lon for each glacier polygon.

    Parameters
    ----------
    gdf : GeoDataFrame
        Glaciers in EPSG:4326.

    Returns
    -------
    GeoDataFrame
        Same data with added 'centroid_lat' and 'centroid_lon' columns.
    """
    out = gdf.copy()
    centroids = out.geometry.centroid
    out["centroid_lat"] = centroids.y
    out["centroid_lon"] = centroids.x
    return out
