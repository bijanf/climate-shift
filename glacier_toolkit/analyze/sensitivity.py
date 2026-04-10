"""
Sensitivity analysis for the climate-glacier coupling paper.

A reviewer's first question after seeing the central finding will be:
"How robust is this to your methodology choices?" This module sweeps
across reasonable choices and reports the central statistic for each
variant, demonstrating that the result holds across a wide range of
defensible methodological decisions.

Parameters that get swept
-------------------------
- NDSI threshold: 0.35, 0.40, 0.45 (default 0.40, Dozier 1989)
- Rolling window: 1 (no smoothing), 3 (default), 5 years
- GLIMS prefer: "historical_max" (default), "latest_per_id"
- Time range: full 1985–2024 vs conservative 1990–2020
- Regression: OLS (default) vs Theil-Sen (robust)

The sensitivity sweep loads cached NDSI files and the cached climate
time series, recomputes the area time series with the chosen parameters,
re-runs the cross-glacier regression, and reports the result.

This is fast because we don't re-fetch any external data — only the
local computation is repeated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .climate_link import compute_local_warming_rate, get_glacier_climate
from .correlation import cross_glacier_regression
from .glacier_area import build_area_timeseries, fit_linear_trend


def compute_per_glacier_for_variant(
    glacier,
    ndsi_files,
    glacier_polygon,
    ndsi_threshold,
    rolling_window,
    year_start,
    year_end,
):
    """Compute per-glacier results for one parameter variant.

    This is the inner loop of a sensitivity sweep — runs once per
    (glacier, variant) combination.

    Parameters
    ----------
    glacier : dict
        A registry glacier entry.
    ndsi_files : dict
        {year: Path} mapping of cached NDSI GeoTIFFs.
    glacier_polygon : geopandas.GeoDataFrame
        Glacier outline (from glims_gee).
    ndsi_threshold : float
        NDSI threshold for ice classification.
    rolling_window : int
        Rolling median window in years (1 = no smoothing).
    year_start, year_end : int
        Time range to analyze.

    Returns
    -------
    dict or None
        Per-glacier result with the keys expected by cross_glacier_regression,
        or None if no data is available.
    """
    # Filter to time range
    files_in_range = {y: p for y, p in ndsi_files.items() if year_start <= y <= year_end}
    if not files_in_range:
        return None

    try:
        ts_df = build_area_timeseries(
            files_in_range,
            fast=True,
            threshold=ndsi_threshold,
            glacier_polygon=glacier_polygon,
            rolling_window=rolling_window,
        )
    except Exception:
        return None

    if len(ts_df) < 3:
        return None

    try:
        trend = fit_linear_trend(ts_df)
        retreat_rate = trend["slope_km2_per_year"]
    except Exception:
        return None

    try:
        temp_df = get_glacier_climate(glacier, year_start, year_end)
        warming = compute_local_warming_rate(temp_df, year_start, year_end)
        warming_rate = warming["slope_c_per_decade"]
    except Exception:
        return None

    return {
        "glacier_name": glacier["name"],
        "glacier_region": glacier["region"],
        "terminus_type": glacier.get("terminus_type", "land"),
        "warming_rate_c_per_decade": warming_rate,
        "retreat_rate_km2_per_year": retreat_rate,
    }


def run_one_variant(
    glaciers_with_files,
    polygon_cache,
    ndsi_threshold=0.40,
    rolling_window=3,
    year_start=1985,
    year_end=2024,
    method="ols",
):
    """Run the full per-glacier + cross-glacier analysis for one variant.

    Parameters
    ----------
    glaciers_with_files : list of (glacier_dict, ndsi_files_dict)
        Pre-loaded glacier configs and their cached NDSI files.
    polygon_cache : dict
        {glacier_key: GeoDataFrame} mapping (pre-fetched).
    ndsi_threshold : float
    rolling_window : int
    year_start, year_end : int
    method : str
        "ols" or "theilsen"

    Returns
    -------
    dict
        Cross-glacier regression results for ALL, LAND-only, and CALVING-only.
    """
    per_glacier = []
    for glacier, ndsi_files in glaciers_with_files:
        result = compute_per_glacier_for_variant(
            glacier=glacier,
            ndsi_files=ndsi_files,
            glacier_polygon=polygon_cache.get(glacier.get("key") or glacier["name"]),
            ndsi_threshold=ndsi_threshold,
            rolling_window=rolling_window,
            year_start=year_start,
            year_end=year_end,
        )
        if result is not None:
            per_glacier.append(result)

    return {
        "n_glaciers_analyzed": len(per_glacier),
        "all": cross_glacier_regression(per_glacier, method=method),
        "land": cross_glacier_regression(per_glacier, terminus_filter="land", method=method),
        "calving": cross_glacier_regression(
            per_glacier, terminus_filter=["marine", "lake"], method=method
        ),
    }


def define_sensitivity_grid():
    """Define the standard sensitivity sweep variants.

    Returns a list of dicts, each describing one variant. The first entry
    is the 'default' (matches the central paper finding); the rest perturb
    one parameter at a time so reviewers can see exactly which choices
    affect the result.

    Returns
    -------
    list of dict
        Each variant has: name, ndsi_threshold, rolling_window, year_start,
        year_end, method, and a 'category' label for grouping.
    """
    default = {
        "ndsi_threshold": 0.40,
        "rolling_window": 3,
        "year_start": 1985,
        "year_end": 2024,
        "method": "ols",
    }

    variants = [
        {"name": "Default (paper)", "category": "default", **default},
        # NDSI threshold sweep
        {
            "name": "NDSI threshold = 0.35",
            "category": "ndsi_threshold",
            **{**default, "ndsi_threshold": 0.35},
        },
        {
            "name": "NDSI threshold = 0.45",
            "category": "ndsi_threshold",
            **{**default, "ndsi_threshold": 0.45},
        },
        # Rolling window sweep
        {
            "name": "No smoothing (window=1)",
            "category": "rolling_window",
            **{**default, "rolling_window": 1},
        },
        {
            "name": "5-year smoothing",
            "category": "rolling_window",
            **{**default, "rolling_window": 5},
        },
        # Time range sweep
        {
            "name": "Conservative range 1990-2020",
            "category": "time_range",
            **{**default, "year_start": 1990, "year_end": 2020},
        },
        # Regression method sweep
        {
            "name": "Theil-Sen robust regression",
            "category": "method",
            **{**default, "method": "theilsen"},
        },
    ]
    return variants


def run_sensitivity_sweep(glaciers_with_files, polygon_cache, variants=None):
    """Run a complete sensitivity sweep across all variants.

    Parameters
    ----------
    glaciers_with_files : list of (glacier, ndsi_files)
    polygon_cache : dict
    variants : list of dict, optional
        Defaults to define_sensitivity_grid().

    Returns
    -------
    pandas.DataFrame
        One row per variant, columns:
        - name, category
        - ndsi_threshold, rolling_window, year_start, year_end, method
        - n_land, spearman_rho_land, p_land, slope_land, r_squared_land
        - n_all, spearman_rho_all, p_all
        - n_calving, spearman_rho_calving, p_calving
    """
    if variants is None:
        variants = define_sensitivity_grid()

    rows = []
    for variant in variants:
        print(f"  [{variant['category']}] {variant['name']} ...")

        result = run_one_variant(
            glaciers_with_files=glaciers_with_files,
            polygon_cache=polygon_cache,
            ndsi_threshold=variant["ndsi_threshold"],
            rolling_window=variant["rolling_window"],
            year_start=variant["year_start"],
            year_end=variant["year_end"],
            method=variant["method"],
        )

        land = result["land"]
        all_ = result["all"]
        calving = result["calving"]

        rows.append(
            {
                "name": variant["name"],
                "category": variant["category"],
                "ndsi_threshold": variant["ndsi_threshold"],
                "rolling_window": variant["rolling_window"],
                "year_start": variant["year_start"],
                "year_end": variant["year_end"],
                "method": variant["method"],
                "n_glaciers_analyzed": result["n_glaciers_analyzed"],
                # Land-only (the central finding)
                "n_land": land.get("n_glaciers", 0),
                "spearman_rho_land": land.get("spearman_r", np.nan),
                "spearman_p_land": land.get("spearman_p", np.nan),
                "pearson_r_land": land.get("pearson_r", np.nan),
                "pearson_p_land": land.get("pearson_p", np.nan),
                "slope_land": land.get("regression_slope", np.nan),
                "r_squared_land": land.get("r_squared", np.nan),
                # All glaciers
                "n_all": all_.get("n_glaciers", 0),
                "spearman_rho_all": all_.get("spearman_r", np.nan),
                "spearman_p_all": all_.get("spearman_p", np.nan),
                # Calving only
                "n_calving": calving.get("n_glaciers", 0),
                "spearman_rho_calving": calving.get("spearman_r", np.nan),
                "spearman_p_calving": calving.get("spearman_p", np.nan),
            }
        )

    return pd.DataFrame(rows)


def summarize_robustness(sensitivity_df):
    """Summarize how stable the central finding is across variants.

    Parameters
    ----------
    sensitivity_df : DataFrame
        From run_sensitivity_sweep().

    Returns
    -------
    dict
        Summary statistics on the central land-only Spearman ρ across
        all variants.
    """
    rho = sensitivity_df["spearman_rho_land"].dropna()
    p = sensitivity_df["spearman_p_land"].dropna()

    if len(rho) == 0:
        return {"n_variants": 0}

    return {
        "n_variants": len(rho),
        "n_significant": int((p < 0.05).sum()),
        "rho_mean": float(rho.mean()),
        "rho_min": float(rho.min()),
        "rho_max": float(rho.max()),
        "rho_std": float(rho.std()),
        "p_max": float(p.max()),
        "all_significant": bool((p < 0.05).all()),
        "all_negative": bool((rho < 0).all()),
    }
