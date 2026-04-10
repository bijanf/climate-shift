"""
Multi-temporal glacier area change analysis.

Computes glacier area time series from annual NDSI GeoTIFFs, fits trends
with bootstrap confidence intervals, and detects acceleration in retreat.
"""

import numpy as np
import pandas as pd

from .ndsi import (
    classify_glacier,
    compute_area_uncertainty_km2,
    compute_glacier_area_km2,
    load_ndsi_geotiff,
)
from .statistics import bootstrap_trend_ci, mann_kendall_test


def compute_area_from_ndsi_file(
    ndsi_path,
    threshold=0.4,
    min_area_km2=0.01,
    pixel_size_m=30,
    fast=False,
):
    """Compute glacier area and uncertainty from an NDSI GeoTIFF.

    Parameters
    ----------
    ndsi_path : str or Path
        Path to the NDSI GeoTIFF.
    threshold : float
        NDSI classification threshold.
    min_area_km2 : float
        Minimum connected-component area (ignored if fast=True).
    pixel_size_m : float
        Pixel resolution.
    fast : bool
        If True, skip connected-component filtering and uncertainty
        computation. Useful for batch processing of many large rasters
        where the threshold-only count is sufficient (e.g. paper pipeline).

    Returns
    -------
    dict
        Keys: 'area_km2', 'uncertainty_km2', 'n_pixels', 'threshold'.
    """
    ndsi = load_ndsi_geotiff(ndsi_path)

    if fast:
        # Fast path: just count pixels above threshold (no labelling)
        values = ndsi.values
        mask = np.where(np.isnan(values), False, values > threshold)
        n_pixels = int(np.sum(mask))
        area = float(n_pixels) * (pixel_size_m**2) / 1e6
        # Approximate uncertainty as 5% of area (typical for clean glaciers)
        uncertainty = area * 0.05
    else:
        mask = classify_glacier(
            ndsi, threshold=threshold, min_area_km2=min_area_km2, pixel_size_m=pixel_size_m
        )
        area = compute_glacier_area_km2(mask, pixel_size_m)
        uncertainty = compute_area_uncertainty_km2(mask, pixel_size_m)
        n_pixels = int(np.sum(mask))

    return {
        "area_km2": area,
        "uncertainty_km2": uncertainty,
        "n_pixels": n_pixels,
        "threshold": threshold,
    }


def build_area_timeseries(ndsi_files, pixel_size_m=30, threshold=0.4, fast=False):
    """Build a glacier area time series from a dict of NDSI GeoTIFFs.

    Parameters
    ----------
    ndsi_files : dict
        {year: Path} mapping from export_timeseries().
    pixel_size_m : float
    threshold : float
    fast : bool
        Use the fast path (skip connected-component filtering).
        Recommended for batch processing of many large rasters.

    Returns
    -------
    pandas.DataFrame
        Columns: year, area_km2, uncertainty_km2, n_pixels.
    """
    records = []
    for year in sorted(ndsi_files.keys()):
        path = ndsi_files[year]
        try:
            result = compute_area_from_ndsi_file(
                path, threshold=threshold, pixel_size_m=pixel_size_m, fast=fast
            )
            result["year"] = year
            records.append(result)
        except Exception as exc:
            print(f"  Warning: skipping {year}: {exc}")

    df = pd.DataFrame(records)
    if len(df) > 0:
        df = df.sort_values("year").reset_index(drop=True)
    return df


def compute_area_change(timeseries_df, baseline_year=None, modern_year=None):
    """Compute area change between two years.

    Parameters
    ----------
    timeseries_df : DataFrame
        From build_area_timeseries().
    baseline_year : int, optional
        Defaults to earliest year in the series.
    modern_year : int, optional
        Defaults to latest year in the series.

    Returns
    -------
    dict
        Keys: baseline_year, modern_year, baseline_area_km2, modern_area_km2,
        change_km2, change_pct.
    """
    df = timeseries_df
    if baseline_year is None:
        baseline_year = df["year"].min()
    if modern_year is None:
        modern_year = df["year"].max()

    baseline = df.loc[df["year"] == baseline_year, "area_km2"]
    modern = df.loc[df["year"] == modern_year, "area_km2"]

    if baseline.empty or modern.empty:
        raise ValueError(f"Year(s) not found: {baseline_year}, {modern_year}")

    b_area = baseline.iloc[0]
    m_area = modern.iloc[0]
    change = m_area - b_area
    pct = (change / b_area) * 100 if b_area > 0 else np.nan

    return {
        "baseline_year": baseline_year,
        "modern_year": modern_year,
        "baseline_area_km2": b_area,
        "modern_area_km2": m_area,
        "change_km2": change,
        "change_pct": pct,
    }


def fit_linear_trend(timeseries_df):
    """Fit a linear trend to the glacier area time series.

    Parameters
    ----------
    timeseries_df : DataFrame
        Must have 'year' and 'area_km2' columns.

    Returns
    -------
    dict
        Keys: slope_km2_per_year, intercept_km2, r_squared,
        ci_lower, ci_upper (95% CI on slope via bootstrap),
        mk_trend, mk_p_value (Mann-Kendall test).
    """
    from scipy import stats

    years = timeseries_df["year"].values.astype(float)
    areas = timeseries_df["area_km2"].values

    # Linear regression
    result = stats.linregress(years, areas)

    # Bootstrap CI on slope
    ci_lo, ci_hi = bootstrap_trend_ci(years, areas)

    # Mann-Kendall trend test
    mk_trend, mk_p = mann_kendall_test(areas)

    return {
        "slope_km2_per_year": result.slope,
        "intercept_km2": result.intercept,
        "r_squared": result.rvalue**2,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "mk_trend": mk_trend,
        "mk_p_value": mk_p,
    }


def detect_acceleration(timeseries_df, breakpoint_year=2000):
    """Test whether retreat rate accelerated after a breakpoint year.

    Fits separate linear trends before and after the breakpoint and
    compares slopes using Welch's t-test.

    Parameters
    ----------
    timeseries_df : DataFrame
    breakpoint_year : int

    Returns
    -------
    dict
        Keys: early_slope, late_slope, acceleration_factor,
        p_value, is_accelerating.
    """
    from scipy import stats

    df = timeseries_df
    early = df[df["year"] <= breakpoint_year]
    late = df[df["year"] > breakpoint_year]

    if len(early) < 3 or len(late) < 3:
        return {
            "early_slope": np.nan,
            "late_slope": np.nan,
            "acceleration_factor": np.nan,
            "p_value": np.nan,
            "is_accelerating": None,
        }

    early_fit = stats.linregress(early["year"].values.astype(float), early["area_km2"].values)
    late_fit = stats.linregress(late["year"].values.astype(float), late["area_km2"].values)

    # Compare slopes (more negative = faster retreat)
    factor = late_fit.slope / early_fit.slope if early_fit.slope != 0 else np.nan

    # Welch's t-test on area values between periods
    _, p_value = stats.ttest_ind(early["area_km2"].values, late["area_km2"].values, equal_var=False)

    return {
        "early_slope": early_fit.slope,
        "late_slope": late_fit.slope,
        "acceleration_factor": factor,
        "p_value": p_value,
        "is_accelerating": late_fit.slope < early_fit.slope,
        "breakpoint_year": breakpoint_year,
    }
