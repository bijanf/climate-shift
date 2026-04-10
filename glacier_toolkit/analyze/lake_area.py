"""
Proglacial lake area time series analysis.

Tracks the growth of glacial lakes over time from NDWI-based water detection,
computes growth rates, and correlates with glacier retreat.
"""

import numpy as np
import pandas as pd
from scipy import stats


def build_lake_timeseries(annual_lake_data):
    """Build a time series of proglacial lake area measurements.

    Parameters
    ----------
    annual_lake_data : dict
        {year: {"lakes": list of lake dicts from ndwi.measure_lake_areas()}}

    Returns
    -------
    pandas.DataFrame
        Columns: year, total_lake_area_km2, n_lakes, largest_lake_km2.
    """
    records = []
    for year in sorted(annual_lake_data.keys()):
        lakes = annual_lake_data[year].get("lakes", [])
        total_area = sum(l["area_km2"] for l in lakes)
        largest = max((l["area_km2"] for l in lakes), default=0)
        records.append({
            "year": year,
            "total_lake_area_km2": total_area,
            "n_lakes": len(lakes),
            "largest_lake_km2": largest,
        })

    return pd.DataFrame(records)


def compute_lake_growth_rate(lake_ts_df, column="total_lake_area_km2"):
    """Compute linear and exponential growth rates for lake area.

    Parameters
    ----------
    lake_ts_df : DataFrame
        From build_lake_timeseries().
    column : str
        Column to analyze.

    Returns
    -------
    dict
        Keys: linear_rate_km2_per_year, linear_r_squared,
        doubling_time_years (from exponential fit, if applicable).
    """
    years = lake_ts_df["year"].values.astype(float)
    areas = lake_ts_df[column].values

    if len(years) < 3 or np.all(areas == 0):
        return {"linear_rate_km2_per_year": 0, "linear_r_squared": 0,
                "doubling_time_years": np.inf}

    # Linear fit
    lin = stats.linregress(years, areas)

    # Exponential fit (only if all values > 0)
    doubling = np.inf
    if np.all(areas > 0):
        log_areas = np.log(areas)
        exp = stats.linregress(years, log_areas)
        if exp.slope > 0:
            doubling = np.log(2) / exp.slope

    return {
        "linear_rate_km2_per_year": lin.slope,
        "linear_r_squared": lin.rvalue ** 2,
        "doubling_time_years": doubling,
    }


def correlate_with_glacier_retreat(glacier_ts_df, lake_ts_df):
    """Compute correlation between glacier area loss and lake area growth.

    Parameters
    ----------
    glacier_ts_df : DataFrame
        Must have 'year' and 'area_km2'.
    lake_ts_df : DataFrame
        Must have 'year' and 'total_lake_area_km2'.

    Returns
    -------
    dict
        Keys: pearson_r, pearson_p, spearman_r, spearman_p.
    """
    merged = pd.merge(glacier_ts_df[["year", "area_km2"]],
                       lake_ts_df[["year", "total_lake_area_km2"]],
                       on="year", how="inner")

    if len(merged) < 5:
        return {"pearson_r": np.nan, "pearson_p": np.nan,
                "spearman_r": np.nan, "spearman_p": np.nan}

    pr, pp = stats.pearsonr(merged["area_km2"],
                             merged["total_lake_area_km2"])
    sr, sp = stats.spearmanr(merged["area_km2"],
                              merged["total_lake_area_km2"])

    return {
        "pearson_r": pr,
        "pearson_p": pp,
        "spearman_r": sr,
        "spearman_p": sp,
    }
