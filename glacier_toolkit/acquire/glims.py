"""
GLIMS glacier boundary acquisition from NSIDC.

Downloads and manages glacier outlines from the Global Land Ice Measurements
from Space (GLIMS) database — a NASA-backed archive covering 200,000+ glaciers.

Data source: https://www.glims.org / https://nsidc.org/data/glims
"""

import zipfile
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np

from ..config import GLIMS_DIR


# NSIDC GLIMS bulk download (entire database as a shapefile)
GLIMS_URL = (
    "https://www.glims.org/download/glims_db_20230517.zip"
)
GLIMS_SHAPEFILE = GLIMS_DIR / "glims_polygons.shp"


def download_glims(force=False):
    """Download the full GLIMS glacier outline database.

    The database is ~500 MB compressed. Downloads once and caches locally.

    Parameters
    ----------
    force : bool
        Re-download even if cached.

    Returns
    -------
    Path
        Path to the extracted shapefile.
    """
    if GLIMS_SHAPEFILE.exists() and not force:
        print(f"  Using cached GLIMS: {GLIMS_SHAPEFILE.name}")
        return GLIMS_SHAPEFILE

    zip_path = GLIMS_DIR / "glims_db.zip"

    if not zip_path.exists():
        print("  Downloading GLIMS database (~500 MB) ...")
        req = Request(GLIMS_URL, headers={"User-Agent": "glacier-toolkit/1.0"})
        with urlopen(req, timeout=1200) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        print(f"  Downloaded: {zip_path.name}")

    print("  Extracting GLIMS shapefiles ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(GLIMS_DIR)
    print(f"  Ready: {GLIMS_DIR}")

    # Find the actual shapefile (path may vary by version)
    shapefiles = list(GLIMS_DIR.rglob("*.shp"))
    if not shapefiles:
        raise FileNotFoundError("No .shp found in GLIMS download")

    # Use the largest shapefile (the main polygon file)
    main_shp = max(shapefiles, key=lambda p: p.stat().st_size)
    if main_shp != GLIMS_SHAPEFILE:
        # Symlink or copy to our standard name
        for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            src = main_shp.with_suffix(ext)
            dst = GLIMS_SHAPEFILE.with_suffix(ext)
            if src.exists() and src != dst:
                shutil.copy2(src, dst)

    return GLIMS_SHAPEFILE


def load_glims(bbox=None):
    """Load GLIMS glacier outlines, optionally filtered by bounding box.

    Parameters
    ----------
    bbox : tuple, optional
        (west, south, east, north) in degrees. If None, loads all.

    Returns
    -------
    geopandas.GeoDataFrame
        Glacier outline polygons with columns including 'glac_name',
        'anlys_time', 'area', and geometry.
    """
    shp_path = download_glims()
    if bbox is not None:
        gdf = gpd.read_file(shp_path, bbox=bbox)
    else:
        gdf = gpd.read_file(shp_path)
    return gdf


def get_glacier_outlines(glacier_config):
    """Get GLIMS outlines for a glacier from the registry.

    Parameters
    ----------
    glacier_config : dict
        A glacier entry from GLACIER_REGISTRY (must have 'bbox' key).

    Returns
    -------
    geopandas.GeoDataFrame
        All GLIMS outlines intersecting the glacier's bounding box.
    """
    return load_glims(bbox=glacier_config["bbox"])


def get_historical_outlines(gdf, sort_by_date=True):
    """Extract all dated glacier outlines for multi-temporal analysis.

    Parameters
    ----------
    gdf : GeoDataFrame
        GLIMS outlines (from load_glims or get_glacier_outlines).
    sort_by_date : bool
        Sort by analysis date (oldest first).

    Returns
    -------
    geopandas.GeoDataFrame
        Filtered to rows with valid dates, sorted chronologically.
    """
    dated = gdf.dropna(subset=["anlys_time"]).copy()
    dated["anlys_time"] = gpd.pd.to_datetime(dated["anlys_time"], errors="coerce")
    dated = dated.dropna(subset=["anlys_time"])
    if sort_by_date:
        dated = dated.sort_values("anlys_time")
    return dated


def clip_raster_to_glacier(raster_da, glacier_gdf, all_touched=True):
    """Clip an xarray DataArray to a glacier boundary.

    Parameters
    ----------
    raster_da : xarray.DataArray
        Must have a CRS set (via rioxarray).
    glacier_gdf : GeoDataFrame
        Glacier polygon(s) to clip to.
    all_touched : bool
        Include pixels that touch the boundary (not just center-in).

    Returns
    -------
    xarray.DataArray
        Clipped raster.
    """
    return raster_da.rio.clip(
        glacier_gdf.geometry,
        glacier_gdf.crs,
        all_touched=all_touched,
        drop=True,
    )


def compute_outline_area_km2(gdf):
    """Compute glacier areas in km² from polygon geometries.

    Reprojects to an equal-area CRS for accurate area calculation.

    Parameters
    ----------
    gdf : GeoDataFrame
        Glacier outline polygons.

    Returns
    -------
    numpy.ndarray
        Areas in km² for each polygon.
    """
    # Use Mollweide equal-area projection
    gdf_ea = gdf.to_crs("ESRI:54009")
    return gdf_ea.geometry.area.values / 1e6  # m² → km²


def plot_glacier_outlines(gdf, ax, colors=None, linewidths=None, **kwargs):
    """Plot glacier outlines on a matplotlib/cartopy axes.

    Parameters
    ----------
    gdf : GeoDataFrame
        Glacier outlines.
    ax : matplotlib.axes.Axes or cartopy GeoAxes
        Target axes.
    colors : list, optional
        Colors per outline. Defaults to cycling C_ICE.
    linewidths : list, optional
        Line widths per outline.
    """
    from ..config import C_ICE

    if colors is None:
        colors = [C_ICE] * len(gdf)
    if linewidths is None:
        linewidths = [1.5] * len(gdf)

    for i, (_, row) in enumerate(gdf.iterrows()):
        geom = row.geometry
        color = colors[i % len(colors)]
        lw = linewidths[i % len(linewidths)]

        if geom.geom_type == "Polygon":
            xs, ys = geom.exterior.xy
            ax.plot(xs, ys, color=color, linewidth=lw, **kwargs)
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                xs, ys = poly.exterior.xy
                ax.plot(xs, ys, color=color, linewidth=lw, **kwargs)
