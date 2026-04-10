"""
Digital Elevation Model (DEM) acquisition.

Downloads Copernicus DEM GLO-30 tiles (global, free, 30m resolution)
from AWS open data for slope masking and hypsometric analysis.

Data source: https://registry.opendata.aws/copernicus-dem/
"""

import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from ..config import DEM_DIR


# Copernicus DEM GLO-30 on AWS S3 (public, no auth required)
COP_DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def _tile_name(lat, lon):
    """Compute the Copernicus DEM tile name for a given coordinate.

    Tiles are 1°×1°, named by their SW corner.
    """
    lat_int = int(np.floor(lat))
    lon_int = int(np.floor(lon))

    lat_str = f"N{abs(lat_int):02d}" if lat_int >= 0 else f"S{abs(lat_int):02d}"
    lon_str = f"E{abs(lon_int):03d}" if lon_int >= 0 else f"W{abs(lon_int):03d}"

    return f"Copernicus_DSM_COG_10_{lat_str}_00_{lon_str}_00_DEM"


def download_dem_tile(lat, lon, output_dir=None):
    """Download a single 1°×1° Copernicus DEM tile.

    Parameters
    ----------
    lat, lon : float
        Any coordinate within the tile.
    output_dir : Path, optional

    Returns
    -------
    Path
        Path to the downloaded GeoTIFF.
    """
    if output_dir is None:
        output_dir = DEM_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tile = _tile_name(lat, lon)
    out_path = output_dir / f"{tile}.tif"

    if out_path.exists():
        print(f"  Using cached DEM tile: {out_path.name}")
        return out_path

    url = f"{COP_DEM_BASE}/{tile}/{tile}.tif"
    print(f"  Downloading DEM tile: {tile} ...")

    req = Request(url, headers={"User-Agent": "glacier-toolkit/1.0"})
    try:
        with urlopen(req, timeout=120) as resp, open(out_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        print(f"  Saved: {out_path.name}")
    except Exception as exc:
        print(f"  Warning: DEM tile not available for ({lat}, {lon}): {exc}")
        return None

    return out_path


def download_dem_for_bbox(bbox, output_dir=None):
    """Download all DEM tiles covering a bounding box.

    Parameters
    ----------
    bbox : tuple
        (west, south, east, north) in degrees.
    output_dir : Path, optional

    Returns
    -------
    list of Path
        Downloaded tile paths (None entries for missing tiles).
    """
    w, s, e, n = bbox

    tiles = []
    for lat in range(int(np.floor(s)), int(np.ceil(n))):
        for lon in range(int(np.floor(w)), int(np.ceil(e))):
            path = download_dem_tile(lat, lon, output_dir)
            if path is not None:
                tiles.append(path)

    print(f"  Downloaded {len(tiles)} DEM tiles for bbox")
    return tiles


def load_dem(tile_path):
    """Load a DEM GeoTIFF as an xarray DataArray.

    Parameters
    ----------
    tile_path : str or Path

    Returns
    -------
    xarray.DataArray
        Elevation in meters with spatial coordinates.
    """
    import rioxarray  # noqa: F401

    da = rioxarray.open_rasterio(tile_path)
    if "band" in da.dims and da.sizes["band"] == 1:
        da = da.squeeze("band", drop=True)
    da.name = "elevation"
    return da


def compute_slope(dem_array, pixel_size_m=30):
    """Compute slope in degrees from a DEM array.

    Parameters
    ----------
    dem_array : numpy.ndarray
        2D elevation array in meters.
    pixel_size_m : float
        Pixel size in meters.

    Returns
    -------
    numpy.ndarray
        Slope in degrees.
    """
    dy, dx = np.gradient(dem_array, pixel_size_m)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.degrees(slope_rad)


def compute_aspect(dem_array, pixel_size_m=30):
    """Compute aspect (compass direction of slope) from a DEM array.

    Parameters
    ----------
    dem_array : numpy.ndarray
    pixel_size_m : float

    Returns
    -------
    numpy.ndarray
        Aspect in degrees (0=N, 90=E, 180=S, 270=W).
    """
    dy, dx = np.gradient(dem_array, pixel_size_m)
    aspect = np.degrees(np.arctan2(-dx, dy))
    aspect = np.where(aspect < 0, aspect + 360, aspect)
    return aspect


def hypsometric_bins(dem_array, glacier_mask, n_bins=10):
    """Create elevation bins for hypsometric analysis.

    Answers: which elevation zones are losing ice fastest?

    Parameters
    ----------
    dem_array : numpy.ndarray
        DEM values.
    glacier_mask : numpy.ndarray
        Boolean glacier mask (same shape).
    n_bins : int
        Number of elevation bins.

    Returns
    -------
    list of dict
        Each dict: elev_min, elev_max, elev_mid, area_km2, fraction.
    """
    glacier_elevations = dem_array[glacier_mask]

    if len(glacier_elevations) == 0:
        return []

    elev_min = glacier_elevations.min()
    elev_max = glacier_elevations.max()
    bin_edges = np.linspace(elev_min, elev_max, n_bins + 1)

    total_pixels = np.sum(glacier_mask)
    bins = []

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = glacier_mask & (dem_array >= lo) & (dem_array < hi)
        n_pixels = np.sum(in_bin)

        bins.append({
            "elev_min": float(lo),
            "elev_max": float(hi),
            "elev_mid": float((lo + hi) / 2),
            "n_pixels": int(n_pixels),
            "fraction": float(n_pixels / total_pixels) if total_pixels > 0 else 0,
        })

    return bins
