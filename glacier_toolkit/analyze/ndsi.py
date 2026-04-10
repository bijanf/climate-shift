"""
NDSI (Normalized Difference Snow Index) glacier classification.

NDSI = (Green - SWIR1) / (Green + SWIR1)
  - Values > 0.4 indicate snow/ice (Dozier 1989)
  - Combined with slope masking and connected-component filtering
    to produce clean glacier masks.

Works with local GeoTIFF rasters (downloaded via acquire/landsat.py).
"""

import numpy as np
import rioxarray
import xarray as xr
from scipy import ndimage


def compute_ndsi(green, swir1):
    """Compute the Normalized Difference Snow Index.

    Parameters
    ----------
    green : numpy.ndarray or xarray.DataArray
        Green band reflectance.
    swir1 : numpy.ndarray or xarray.DataArray
        Short-wave infrared band 1 reflectance.

    Returns
    -------
    Same type as input
        NDSI values in [-1, 1]. NaN where both bands are zero.
    """
    denom = green + swir1
    if isinstance(green, xr.DataArray):
        ndsi = xr.where(denom != 0, (green - swir1) / denom, np.nan)
        ndsi.name = "ndsi"
        return ndsi
    else:
        with np.errstate(divide="ignore", invalid="ignore"):
            ndsi = np.where(denom != 0, (green - swir1) / denom, np.nan)
        return ndsi


def classify_glacier(ndsi, threshold=0.4, min_area_km2=0.01, pixel_size_m=30):
    """Classify glacier ice from an NDSI raster.

    Parameters
    ----------
    ndsi : numpy.ndarray or xarray.DataArray
        NDSI values.
    threshold : float
        NDSI threshold for ice classification. Default 0.4 (Dozier 1989).
    min_area_km2 : float
        Minimum connected-component area in km² to keep. Removes isolated
        snow patches that are not glacier ice.
    pixel_size_m : float
        Pixel size in meters for area calculation.

    Returns
    -------
    numpy.ndarray
        Boolean glacier mask (True = ice).
    """
    if isinstance(ndsi, xr.DataArray):
        values = ndsi.values
    else:
        values = ndsi

    # Binary classification
    mask = np.where(np.isnan(values), False, values > threshold)

    # Connected component filtering
    min_pixels = min_area_km2 * 1e6 / (pixel_size_m**2)
    labeled, n_features = ndimage.label(mask)

    if n_features > 0:
        component_sizes = ndimage.sum(mask, labeled, range(1, n_features + 1))
        for i, size in enumerate(component_sizes, start=1):
            if size < min_pixels:
                mask[labeled == i] = False

    return mask


def apply_slope_mask(glacier_mask, slope, max_slope_deg=60):
    """Remove steep slopes from glacier mask.

    Slopes > 60° cannot sustain glacier ice.

    Parameters
    ----------
    glacier_mask : numpy.ndarray
        Boolean glacier mask.
    slope : numpy.ndarray
        Slope in degrees (same shape as glacier_mask).
    max_slope_deg : float
        Maximum slope to allow.

    Returns
    -------
    numpy.ndarray
        Updated glacier mask.
    """
    result = glacier_mask.copy()
    result[slope > max_slope_deg] = False
    return result


def compute_glacier_area_km2(glacier_mask, pixel_size_m=30):
    """Compute total glacier area from a binary mask.

    Parameters
    ----------
    glacier_mask : numpy.ndarray
        Boolean mask (True = ice).
    pixel_size_m : float
        Pixel size in meters.

    Returns
    -------
    float
        Glacier area in km².
    """
    pixel_area_km2 = (pixel_size_m**2) / 1e6
    return float(np.sum(glacier_mask) * pixel_area_km2)


def compute_area_uncertainty_km2(glacier_mask, pixel_size_m=30):
    """Estimate classification uncertainty using the boundary-pixel method.

    Uncertainty arises from mixed pixels at the glacier boundary.
    Following Granshaw & Fountain (2006), the uncertainty is ±0.5 pixel
    width times the boundary perimeter length.

    Parameters
    ----------
    glacier_mask : numpy.ndarray
        Boolean glacier mask.
    pixel_size_m : float
        Pixel size in meters.

    Returns
    -------
    float
        Area uncertainty in km² (one-sided).
    """
    # Find boundary pixels (glacier pixels adjacent to non-glacier)
    eroded = ndimage.binary_erosion(glacier_mask)
    boundary = glacier_mask & ~eroded
    n_boundary = np.sum(boundary)

    # Each boundary pixel contributes ±0.5 pixel uncertainty
    uncertainty_m2 = n_boundary * pixel_size_m * pixel_size_m * 0.5
    return uncertainty_m2 / 1e6


def load_ndsi_geotiff(path):
    """Load an NDSI GeoTIFF as an xarray DataArray.

    Parameters
    ----------
    path : str or Path
        Path to the GeoTIFF file.

    Returns
    -------
    xarray.DataArray
        NDSI raster with spatial coordinates and CRS.
    """
    da = rioxarray.open_rasterio(path)
    # Squeeze out the band dimension if single-band
    if "band" in da.dims and da.sizes["band"] == 1:
        da = da.squeeze("band", drop=True)
    da.name = "ndsi"
    return da
