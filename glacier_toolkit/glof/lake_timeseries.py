"""
Glacial lake growth rate analysis and volume estimation.

Tracks individual lake growth over time and estimates lake volume
using empirical area-volume scaling relationships.
"""

import numpy as np
import pandas as pd
from scipy import stats


def compute_lake_growth_timeseries(lake_detections_by_year, lake_id_func=None):
    """Build growth time series for individual lakes across years.

    Parameters
    ----------
    lake_detections_by_year : dict
        {year: list of lake dicts (from lake_detection.detect_glacial_lakes)}.
    lake_id_func : callable, optional
        Function to assign persistent IDs to lakes across years.
        Default: match by nearest centroid.

    Returns
    -------
    dict
        {lake_label: DataFrame with columns year, area_km2}.
    """
    if lake_id_func is None:
        lake_id_func = _match_lakes_by_centroid

    return lake_id_func(lake_detections_by_year)


def _match_lakes_by_centroid(detections_by_year, tolerance=15):
    """Match lakes across years by centroid proximity."""
    years = sorted(detections_by_year.keys())
    if not years:
        return {}

    # Use first year's lakes as reference
    ref_lakes = detections_by_year[years[0]]
    lake_series = {}

    for i, ref in enumerate(ref_lakes):
        label = f"lake_{i + 1}"
        records = [{"year": years[0], "area_km2": ref["area_km2"]}]

        ref_row = ref["centroid_row"]
        ref_col = ref["centroid_col"]

        for year in years[1:]:
            candidates = detections_by_year.get(year, [])
            best_match = None
            best_dist = tolerance + 1

            for cand in candidates:
                dist = np.sqrt(
                    (cand["centroid_row"] - ref_row) ** 2 + (cand["centroid_col"] - ref_col) ** 2
                )
                if dist < best_dist:
                    best_dist = dist
                    best_match = cand

            if best_match is not None and best_dist <= tolerance:
                records.append({"year": year, "area_km2": best_match["area_km2"]})
                # Update reference centroid for tracking drift
                ref_row = best_match["centroid_row"]
                ref_col = best_match["centroid_col"]

        lake_series[label] = pd.DataFrame(records)

    return lake_series


def estimate_lake_volume(area_km2, method="huggel2002"):
    """Estimate lake volume from surface area using empirical scaling.

    Parameters
    ----------
    area_km2 : float
        Lake surface area in km².
    method : str
        Scaling relationship to use:
        - "huggel2002": V = 0.104 * A^1.42 (Huggel et al. 2002)
        - "cook2012": V = 0.0578 * A^1.4683 (Cook & Quincey 2012)

    Returns
    -------
    float
        Estimated lake volume in million m³.
    """
    area_m2 = area_km2 * 1e6

    if method == "huggel2002":
        # Huggel et al. 2002: V (m³) = 0.104 * A (m²) ^ 1.42
        volume_m3 = 0.104 * (area_m2**1.42)
    elif method == "cook2012":
        # Cook & Quincey 2012 (Himalayan lakes)
        volume_m3 = 0.0578 * (area_m2**1.4683)
    else:
        raise ValueError(f"Unknown method: {method}")

    return volume_m3 / 1e6  # Convert to million m³


def detect_rapid_growth(lake_timeseries_df, threshold_pct_per_year=5):
    """Flag lakes with anomalously rapid area growth.

    Parameters
    ----------
    lake_timeseries_df : DataFrame
        Columns: year, area_km2.
    threshold_pct_per_year : float
        Percentage growth rate per year to flag as "rapid."

    Returns
    -------
    dict
        Keys: growth_rate_pct_per_year, is_rapid, trend_slope, years_analyzed.
    """
    df = lake_timeseries_df
    if len(df) < 3:
        return {
            "growth_rate_pct_per_year": np.nan,
            "is_rapid": False,
            "trend_slope": np.nan,
            "years_analyzed": len(df),
        }

    years = df["year"].values.astype(float)
    areas = df["area_km2"].values

    # Linear regression for absolute rate
    result = stats.linregress(years, areas)

    # Average growth rate as % per year relative to initial area
    initial_area = areas[0]
    if initial_area > 0:
        pct_per_year = (result.slope / initial_area) * 100
    else:
        pct_per_year = np.inf if result.slope > 0 else 0

    return {
        "growth_rate_pct_per_year": pct_per_year,
        "is_rapid": abs(pct_per_year) >= threshold_pct_per_year,
        "trend_slope": result.slope,
        "years_analyzed": len(df),
    }
