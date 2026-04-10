"""
Automated glacial lake detection and classification.

Identifies proglacial lakes from NDWI rasters, classifies dam types,
and flags newly appeared lakes.
"""

import numpy as np
from scipy import ndimage


def detect_glacial_lakes(ndwi_array, glacier_mask, buffer_pixels=67,
                         ndwi_threshold=0.3, min_area_km2=0.001,
                         pixel_size_m=30):
    """Identify glacial lakes near glacier termini.

    Parameters
    ----------
    ndwi_array : numpy.ndarray
        NDWI values.
    glacier_mask : numpy.ndarray
        Boolean glacier mask (same shape).
    buffer_pixels : int
        Max distance from glacier edge in pixels (67 px = ~2 km at 30m).
    ndwi_threshold : float
        NDWI threshold for water classification.
    min_area_km2 : float
        Minimum lake area to keep.
    pixel_size_m : float
        Pixel resolution.

    Returns
    -------
    list of dict
        Each dict: label, area_km2, centroid_row, centroid_col, n_pixels,
        distance_to_glacier_pixels.
    """
    # Water mask
    water = np.where(np.isnan(ndwi_array), False, ndwi_array > ndwi_threshold)

    # Distance from glacier
    glacier_distance = ndimage.distance_transform_edt(~glacier_mask)

    # Label connected components
    labeled, n_features = ndimage.label(water)
    pixel_area_km2 = (pixel_size_m ** 2) / 1e6
    min_pixels = min_area_km2 / pixel_area_km2

    lakes = []
    for i in range(1, n_features + 1):
        component = labeled == i
        n_pixels = int(np.sum(component))

        if n_pixels < min_pixels:
            continue

        # Check proximity to glacier
        min_dist = glacier_distance[component].min()
        if min_dist > buffer_pixels:
            continue

        centroid = ndimage.center_of_mass(component)
        lakes.append({
            "label": i,
            "area_km2": n_pixels * pixel_area_km2,
            "centroid_row": centroid[0],
            "centroid_col": centroid[1],
            "n_pixels": n_pixels,
            "distance_to_glacier_pixels": float(min_dist),
            "distance_to_glacier_m": float(min_dist * pixel_size_m),
        })

    return sorted(lakes, key=lambda x: x["area_km2"], reverse=True)


def classify_lake_dam_type(lake, glacier_mask, dem=None):
    """Classify the dam type of a glacial lake.

    Dam types (following Emmer & Vilimek 2013):
      - "moraine": lake is behind a moraine dam (most dangerous for GLOFs)
      - "ice": lake is dammed by glacier ice
      - "bedrock": lake sits in a bedrock basin

    Parameters
    ----------
    lake : dict
        Lake record from detect_glacial_lakes().
    glacier_mask : numpy.ndarray
    dem : numpy.ndarray, optional
        Digital elevation model for terrain analysis.

    Returns
    -------
    str
        Dam type: "moraine", "ice", or "bedrock".
    """
    dist = lake["distance_to_glacier_m"]

    # Simple heuristic classification
    # Ice-dammed: lake directly touches glacier
    if dist < 60:  # < 2 pixels at 30m
        return "ice"

    # Moraine-dammed: lake is near glacier but not touching
    # (moraine deposits between glacier and lake)
    if dist < 2000:
        return "moraine"

    # Bedrock: far from glacier, in carved basin
    return "bedrock"


def flag_new_lakes(current_lakes, historical_lakes, match_tolerance_pixels=10):
    """Identify lakes that appear in current data but not in historical data.

    Parameters
    ----------
    current_lakes : list of dict
        Lakes detected in recent imagery.
    historical_lakes : list of dict
        Lakes detected in older imagery.
    match_tolerance_pixels : int
        Centroid distance tolerance for matching.

    Returns
    -------
    list of dict
        Lakes from current_lakes that have no historical match.
    """
    new_lakes = []

    for curr in current_lakes:
        is_new = True
        for hist in historical_lakes:
            dist = np.sqrt(
                (curr["centroid_row"] - hist["centroid_row"]) ** 2 +
                (curr["centroid_col"] - hist["centroid_col"]) ** 2
            )
            if dist < match_tolerance_pixels:
                is_new = False
                break
        if is_new:
            curr["is_new"] = True
            new_lakes.append(curr)

    return new_lakes
