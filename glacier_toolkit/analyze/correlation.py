"""
Climate-glacier coupling analysis.

Correlates local climate (from analyze.climate_link) with glacier area
time series (from analyze.glacier_area) to compute climate sensitivity:
how many km² of ice are lost per °C of local warming.

This is the core scientific module for the climate-glacier paper.
See PAPER.md for the methodology and target results.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..config import BOOTSTRAP_N, BOOTSTRAP_SEED, CI_LEVEL


def compute_climate_glacier_correlation(area_df, temp_df):
    """Correlate glacier area with local temperature year by year.

    Parameters
    ----------
    area_df : pandas.DataFrame
        Must have 'year' and 'area_km2' columns. From build_area_timeseries().
    temp_df : pandas.DataFrame
        Must have 'year' and 'temp_c' columns. From extract_local_temperature().

    Returns
    -------
    dict
        Keys:
        - n_years: int (years matched between datasets)
        - pearson_r: float
        - pearson_p: float
        - spearman_r: float
        - spearman_p: float
        - merged: DataFrame with year, area_km2, temp_c
    """
    merged = pd.merge(
        area_df[["year", "area_km2"]],
        temp_df[["year", "temp_c"]],
        on="year",
        how="inner",
    )

    if len(merged) < 5:
        return {
            "n_years": len(merged),
            "pearson_r": np.nan,
            "pearson_p": np.nan,
            "spearman_r": np.nan,
            "spearman_p": np.nan,
            "merged": merged,
        }

    pr, pp = stats.pearsonr(merged["area_km2"], merged["temp_c"])
    sr, sp = stats.spearmanr(merged["area_km2"], merged["temp_c"])

    return {
        "n_years": len(merged),
        "pearson_r": float(pr),
        "pearson_p": float(pp),
        "spearman_r": float(sr),
        "spearman_p": float(sp),
        "merged": merged,
    }


def compute_climate_sensitivity(
    area_df,
    temp_df,
    n_boot=BOOTSTRAP_N,
    ci=CI_LEVEL,
    seed=BOOTSTRAP_SEED,
):
    """Fit area = α + β × T_local and report β as climate sensitivity.

    The slope β is in km² per °C. A negative β means warmer years
    correspond to less ice (the expected sign for melting glaciers).

    Parameters
    ----------
    area_df : DataFrame with 'year' and 'area_km2'.
    temp_df : DataFrame with 'year' and 'temp_c'.
    n_boot, ci, seed : bootstrap parameters.

    Returns
    -------
    dict
        Keys:
        - sensitivity_km2_per_c: float (β coefficient)
        - intercept_km2: float (α coefficient)
        - r_squared: float
        - p_value: float
        - ci_lower: float (95% CI on β)
        - ci_upper: float
        - n_years: int
        - is_significant: bool (p < 0.05)
        - sign_correct: bool (β < 0, the expected direction for melting)
    """
    merged = pd.merge(
        area_df[["year", "area_km2"]],
        temp_df[["year", "temp_c"]],
        on="year",
        how="inner",
    )

    if len(merged) < 5:
        return {
            "sensitivity_km2_per_c": np.nan,
            "intercept_km2": np.nan,
            "r_squared": np.nan,
            "p_value": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "n_years": len(merged),
            "is_significant": False,
            "sign_correct": None,
        }

    temps = merged["temp_c"].values
    areas = merged["area_km2"].values

    # OLS regression
    fit = stats.linregress(temps, areas)

    # Bootstrap CI on slope
    rng = np.random.default_rng(seed)
    n = len(merged)
    slopes = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        slopes[i] = stats.linregress(temps[idx], areas[idx]).slope
    ci_lo = float(np.percentile(slopes, (1 - ci) / 2 * 100))
    ci_hi = float(np.percentile(slopes, (1 + ci) / 2 * 100))

    return {
        "sensitivity_km2_per_c": float(fit.slope),
        "intercept_km2": float(fit.intercept),
        "r_squared": float(fit.rvalue**2),
        "p_value": float(fit.pvalue),
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "n_years": int(n),
        "is_significant": bool(fit.pvalue < 0.05),
        "sign_correct": bool(fit.slope < 0),
    }


def cross_glacier_regression(per_glacier_results, terminus_filter=None, method="ols"):
    """Test the across-glacier hypothesis: faster warming → faster retreat.

    Pools per-glacier warming rates and retreat rates, then fits a
    cross-glacier regression.

    method can be "ols" (ordinary least squares) or "theilsen"
    (Theil-Sen median estimator, robust to outliers — recommended for
    sensitivity analysis where reviewers may question the role of
    extreme glaciers).

    Parameters
    ----------
    per_glacier_results : list of dict
        Each dict must have:
        - 'warming_rate_c_per_decade': from compute_local_warming_rate
        - 'retreat_rate_km2_per_year': from fit_linear_trend (negative for retreating)
        - 'glacier_name', 'glacier_region': identifiers
        - 'terminus_type' (optional): "land", "marine", or "lake"
    terminus_filter : str or list, optional
        If provided, only include glaciers with matching terminus_type.
        E.g. terminus_filter="land" or ["land"] to test the hypothesis on
        land-terminating glaciers only (where calving dynamics don't confound).

    Returns
    -------
    dict
        Keys:
        - n_glaciers
        - pearson_r, pearson_p, spearman_r, spearman_p
        - regression_slope (km²/year of retreat per °C/decade of warming)
        - regression_intercept
        - r_squared
        - p_value
        - terminus_filter (echoed)
    """
    # Filter by terminus type
    if terminus_filter:
        if isinstance(terminus_filter, str):
            terminus_filter = [terminus_filter]
        per_glacier_results = [
            r for r in per_glacier_results if r.get("terminus_type") in terminus_filter
        ]

    rows = [
        r
        for r in per_glacier_results
        if not (
            np.isnan(r.get("warming_rate_c_per_decade", np.nan))
            or np.isnan(r.get("retreat_rate_km2_per_year", np.nan))
        )
    ]

    if len(rows) < 3:
        return {
            "n_glaciers": len(rows),
            "pearson_r": np.nan,
            "pearson_p": np.nan,
            "spearman_r": np.nan,
            "spearman_p": np.nan,
            "regression_slope": np.nan,
            "regression_intercept": np.nan,
            "r_squared": np.nan,
            "p_value": np.nan,
            "terminus_filter": terminus_filter,
        }

    warming = np.array([r["warming_rate_c_per_decade"] for r in rows])
    retreat = np.array([r["retreat_rate_km2_per_year"] for r in rows])

    pr, pp = stats.pearsonr(warming, retreat)
    sr, sp = stats.spearmanr(warming, retreat)
    fit = stats.linregress(warming, retreat)

    # Optional Theil-Sen robust estimator (median of pairwise slopes)
    if method == "theilsen":
        ts = stats.theilslopes(retreat, warming, alpha=0.95)
        regression_slope = float(ts.slope)
        regression_intercept = float(ts.intercept)
        ts_lower = float(ts.low_slope)
        ts_upper = float(ts.high_slope)
    else:
        regression_slope = float(fit.slope)
        regression_intercept = float(fit.intercept)
        ts_lower = None
        ts_upper = None

    return {
        "n_glaciers": len(rows),
        "pearson_r": float(pr),
        "pearson_p": float(pp),
        "spearman_r": float(sr),
        "spearman_p": float(sp),
        "regression_slope": regression_slope,
        "regression_intercept": regression_intercept,
        "r_squared": float(fit.rvalue**2),
        "p_value": float(fit.pvalue),
        "method": method,
        "theilsen_ci_lower": ts_lower,
        "theilsen_ci_upper": ts_upper,
        "terminus_filter": terminus_filter,
    }


def per_region_summary(per_glacier_results):
    """Aggregate per-glacier results into per-region statistics.

    Parameters
    ----------
    per_glacier_results : list of dict
        Each dict must have 'glacier_region' and the analysis fields.

    Returns
    -------
    pandas.DataFrame
        One row per region, columns:
        - region
        - n_glaciers
        - mean_warming_rate_c_per_decade
        - mean_retreat_rate_km2_per_year
        - mean_sensitivity_km2_per_c
        - n_significant (number of glaciers with sensitivity p < 0.05)
    """
    df = pd.DataFrame(per_glacier_results)
    if len(df) == 0:
        return pd.DataFrame()

    grouped = (
        df.groupby("glacier_region")
        .agg(
            n_glaciers=("glacier_name", "count"),
            mean_warming_rate_c_per_decade=("warming_rate_c_per_decade", "mean"),
            mean_retreat_rate_km2_per_year=("retreat_rate_km2_per_year", "mean"),
            mean_sensitivity_km2_per_c=("sensitivity_km2_per_c", "mean"),
            n_significant=("sensitivity_p_value", lambda s: int((s < 0.05).sum())),
        )
        .reset_index()
    )

    return grouped.sort_values("mean_warming_rate_c_per_decade", ascending=False)


def build_results_table(per_glacier_results):
    """Generate a publication-ready results table.

    Parameters
    ----------
    per_glacier_results : list of dict
        From the paper pipeline.

    Returns
    -------
    pandas.DataFrame
        One row per glacier with all key metrics. Suitable for LaTeX export.
    """
    rows = []
    for r in per_glacier_results:
        rows.append(
            {
                "Glacier": r.get("glacier_name", "?"),
                "Region": r.get("glacier_region", "?"),
                "Years": f"{r.get('year_start', '?')}-{r.get('year_end', '?')}",
                "Area Loss (%)": (
                    f"{r.get('area_change_pct', np.nan):.1f}"
                    if not np.isnan(r.get("area_change_pct", np.nan))
                    else "—"
                ),
                "Retreat (km²/yr)": (
                    f"{r.get('retreat_rate_km2_per_year', np.nan):.3f}"
                    if not np.isnan(r.get("retreat_rate_km2_per_year", np.nan))
                    else "—"
                ),
                "Warming (°C/dec)": (
                    f"{r.get('warming_rate_c_per_decade', np.nan):.3f}"
                    if not np.isnan(r.get("warming_rate_c_per_decade", np.nan))
                    else "—"
                ),
                "Sensitivity (km²/°C)": (
                    f"{r.get('sensitivity_km2_per_c', np.nan):.2f}"
                    if not np.isnan(r.get("sensitivity_km2_per_c", np.nan))
                    else "—"
                ),
                "R²": (
                    f"{r.get('sensitivity_r_squared', np.nan):.2f}"
                    if not np.isnan(r.get("sensitivity_r_squared", np.nan))
                    else "—"
                ),
                "p": (
                    f"{r.get('sensitivity_p_value', np.nan):.3f}"
                    if not np.isnan(r.get("sensitivity_p_value", np.nan))
                    else "—"
                ),
            }
        )
    return pd.DataFrame(rows)
