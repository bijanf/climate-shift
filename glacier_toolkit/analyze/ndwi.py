"""
NDWI (Normalized Difference Water Index) water body detection.

NDWI = (Green - NIR) / (Green + NIR)
  - Values > 0.3 indicate water (McFeeters 1996)
  - Used for detecting proglacial lakes for GLOF risk assessment.
"""

import numpy as np
import xarray as xr
from scipy import ndimage


def compute_ndwi(green, nir):
    """Compute the Normalized Difference Water Index.

    Parameters
    ----------
    green : numpy.ndarray or xarray.DataArray
        Green band reflectance.
    nir : numpy.ndarray or xarray.DataArray
        Near-infrared band reflectance.

    Returns
    -------
    Same type as input
        NDWI values in [-1, 1].
    """
    denom = green + nir
    if isinstance(green, xr.DataArray):
        ndwi = xr.where(denom != 0, (green - nir) / denom, np.nan)
        ndwi.name = "ndwi"
        return ndwi
    else:
        with np.errstate(divide="ignore", invalid="ignore"):
            ndwi = np.where(denom != 0, (green - nir) / denom, np.nan)
        return ndwi


def detect_water_bodies(ndwi, threshold=0.3, min_area_km2=0.001, pixel_size_m=30):
    """Detect water bodies from an NDWI raster.

    Parameters
    ----------
    ndwi : numpy.ndarray or xarray.DataArray
        NDWI values.
    threshold : float
        NDWI threshold for water classification.
    min_area_km2 : float
        Minimum lake area to keep.
    pixel_size_m : float
        Pixel resolution in meters.

    Returns
    -------
    numpy.ndarray
        Boolean water mask.
    """
    if isinstance(ndwi, xr.DataArray):
        values = ndwi.values
    else:
        values = ndwi

    mask = np.where(np.isnan(values), False, values > threshold)

    # Remove tiny water bodies
    min_pixels = min_area_km2 * 1e6 / (pixel_size_m**2)
    labeled, n_features = ndimage.label(mask)

    if n_features > 0:
        component_sizes = ndimage.sum(mask, labeled, range(1, n_features + 1))
        for i, size in enumerate(component_sizes, start=1):
            if size < min_pixels:
                mask[labeled == i] = False

    return mask


def filter_proglacial_lakes(water_mask, glacier_mask, max_distance_pixels=67):
    """Keep only water bodies near glacier termini.

    Parameters
    ----------
    water_mask : numpy.ndarray
        Boolean water mask.
    glacier_mask : numpy.ndarray
        Boolean glacier mask (same shape).
    max_distance_pixels : int
        Maximum distance from glacier edge in pixels.
        Default 67 pixels = ~2 km at 30m Landsat resolution.

    Returns
    -------
    numpy.ndarray
        Filtered water mask containing only proglacial lakes.
    """
    # Distance transform from glacier edge
    glacier_distance = ndimage.distance_transform_edt(~glacier_mask)

    # Keep water bodies whose centroid is within max_distance of glacier
    labeled, n_features = ndimage.label(water_mask)
    proglacial = np.zeros_like(water_mask)

    for i in range(1, n_features + 1):
        component = labeled == i
        # Check if any pixel of this water body is near the glacier
        min_dist = glacier_distance[component].min()
        if min_dist <= max_distance_pixels:
            proglacial[component] = True

    return proglacial


def measure_lake_areas(water_mask, pixel_size_m=30):
    """Measure the area of each individual water body.

    Parameters
    ----------
    water_mask : numpy.ndarray
        Boolean water mask.
    pixel_size_m : float
        Pixel resolution.

    Returns
    -------
    list of dict
        Each dict has: 'label', 'area_km2', 'centroid_row', 'centroid_col',
        'n_pixels'.
    """
    labeled, n_features = ndimage.label(water_mask)
    pixel_area_km2 = (pixel_size_m**2) / 1e6

    lakes = []
    for i in range(1, n_features + 1):
        component = labeled == i
        n_pixels = int(np.sum(component))
        centroid = ndimage.center_of_mass(component)
        lakes.append(
            {
                "label": i,
                "area_km2": n_pixels * pixel_area_km2,
                "centroid_row": centroid[0],
                "centroid_col": centroid[1],
                "n_pixels": n_pixels,
            }
        )

    return sorted(lakes, key=lambda x: x["area_km2"], reverse=True)
