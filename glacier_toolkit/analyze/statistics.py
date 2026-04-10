"""
Statistical utilities for glacier analysis.

Matches the statistical rigor of the existing climate_shift project:
  - Bootstrap resampling (10,000 iterations, seed=42, percentile CIs)
  - Welch's t-test for period comparison
  - Mann-Kendall trend test for monotonic glacier retreat detection

Adapted from plot_climate_shift.py:177-187.
"""

import numpy as np
from scipy import stats

from ..config import BOOTSTRAP_N, BOOTSTRAP_SEED, CI_LEVEL


def bootstrap_ci(a, b, n_boot=BOOTSTRAP_N, ci=CI_LEVEL, seed=BOOTSTRAP_SEED):
    """Bootstrap 95% CI for the difference of means (b - a).

    Direct port from plot_climate_shift.py:177-187.

    Parameters
    ----------
    a, b : array-like
        Two samples to compare.
    n_boot : int
        Number of bootstrap resamples.
    ci : float
        Confidence level (0.95 = 95% CI).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    tuple (float, float)
        (lower, upper) confidence interval bounds.
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    diffs = np.empty(n_boot)
    for i in range(n_boot):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        diffs[i] = sb.mean() - sa.mean()

    lo = np.percentile(diffs, (1 - ci) / 2 * 100)
    hi = np.percentile(diffs, (1 + ci) / 2 * 100)
    return lo, hi


def bootstrap_trend_ci(years, values, n_boot=BOOTSTRAP_N, ci=CI_LEVEL,
                        seed=BOOTSTRAP_SEED):
    """Bootstrap CI on the linear regression slope.

    Parameters
    ----------
    years : array-like
        Independent variable (year).
    values : array-like
        Dependent variable (e.g. glacier area in km²).
    n_boot : int
    ci : float
    seed : int

    Returns
    -------
    tuple (float, float)
        (lower, upper) CI on the slope (km²/year).
    """
    rng = np.random.default_rng(seed)
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)
    n = len(years)

    slopes = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        result = stats.linregress(years[idx], values[idx])
        slopes[i] = result.slope

    lo = np.percentile(slopes, (1 - ci) / 2 * 100)
    hi = np.percentile(slopes, (1 + ci) / 2 * 100)
    return lo, hi


def bootstrap_statistic(data, stat_func=np.mean, n_boot=BOOTSTRAP_N,
                         ci=CI_LEVEL, seed=BOOTSTRAP_SEED):
    """Bootstrap CI for any single-sample statistic.

    Parameters
    ----------
    data : array-like
    stat_func : callable
        Function to compute the statistic (e.g. np.mean, np.median).
    n_boot : int
    ci : float
    seed : int

    Returns
    -------
    tuple (float, float, float)
        (point_estimate, ci_lower, ci_upper).
    """
    rng = np.random.default_rng(seed)
    data = np.asarray(data, dtype=float)

    point = float(stat_func(data))
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(data, size=len(data), replace=True)
        boot_stats[i] = stat_func(sample)

    lo = np.percentile(boot_stats, (1 - ci) / 2 * 100)
    hi = np.percentile(boot_stats, (1 + ci) / 2 * 100)
    return point, lo, hi


def mann_kendall_test(values):
    """Mann-Kendall trend test for monotonic time series trends.

    More appropriate than parametric tests for glacier area time series
    because it does not assume normality or linearity.

    Parameters
    ----------
    values : array-like
        Time series values (ordered chronologically).

    Returns
    -------
    tuple (str, float)
        (trend_direction, p_value)
        trend_direction: "increasing", "decreasing", or "no trend"
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < 4:
        return "no trend", 1.0

    # Compute S statistic
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1

    # Variance of S (with tie correction)
    unique, counts = np.unique(values, return_counts=True)
    tie_sum = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_sum) / 18

    # Z statistic
    if var_s == 0:
        return "no trend", 1.0

    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0

    # Two-tailed p-value
    p_value = 2 * stats.norm.sf(abs(z))

    if p_value < 0.05:
        trend = "decreasing" if s < 0 else "increasing"
    else:
        trend = "no trend"

    return trend, p_value


def welch_ttest(a, b):
    """Welch's t-test for comparing two periods.

    Matching the pattern from plot_climate_shift.py:285.

    Parameters
    ----------
    a, b : array-like
        Two samples.

    Returns
    -------
    dict
        Keys: t_statistic, p_value, mean_diff, is_significant (at 0.05).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)

    return {
        "t_statistic": t_stat,
        "p_value": p_value,
        "mean_diff": b.mean() - a.mean(),
        "is_significant": p_value < 0.05,
    }


def area_uncertainty_boundary(glacier_mask, pixel_size_m=30):
    """Compute area uncertainty using the boundary-pixel method.

    Following Granshaw & Fountain (2006): uncertainty is ±0.5 pixel
    for every boundary pixel.

    Parameters
    ----------
    glacier_mask : numpy.ndarray
        Boolean mask.
    pixel_size_m : float

    Returns
    -------
    float
        Uncertainty in km² (one-sided ±).
    """
    from scipy.ndimage import binary_erosion

    eroded = binary_erosion(glacier_mask)
    boundary = glacier_mask & ~eroded
    n_boundary = np.sum(boundary)

    return float(n_boundary * pixel_size_m * pixel_size_m * 0.5 / 1e6)
