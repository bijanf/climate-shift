"""Tests for glacier_toolkit.analyze.statistics."""

from __future__ import annotations

import numpy as np
import pytest

from glacier_toolkit.analyze.statistics import (
    area_uncertainty_boundary,
    bootstrap_ci,
    bootstrap_statistic,
    bootstrap_trend_ci,
    mann_kendall_test,
    welch_ttest,
)


class TestBootstrapCI:
    def test_returns_tuple_of_floats(self, rng):
        a = rng.normal(0, 1, 100)
        b = rng.normal(1, 1, 100)
        lo, hi = bootstrap_ci(a, b, n_boot=500)
        assert isinstance(lo, float)
        assert isinstance(hi, float)

    def test_lower_less_than_upper(self, rng):
        a = rng.normal(0, 1, 100)
        b = rng.normal(2, 1, 100)
        lo, hi = bootstrap_ci(a, b, n_boot=500)
        assert lo < hi

    def test_detects_real_difference(self, rng):
        # b is shifted by 5 — CI should NOT include 0
        a = rng.normal(0, 1, 200)
        b = rng.normal(5, 1, 200)
        lo, hi = bootstrap_ci(a, b, n_boot=1000)
        assert lo > 0, "CI should not contain 0 when there is a real difference"

    def test_no_difference_includes_zero(self, rng):
        a = rng.normal(0, 1, 200)
        b = rng.normal(0, 1, 200)
        lo, hi = bootstrap_ci(a, b, n_boot=1000)
        assert lo <= 0 <= hi, "CI should contain 0 for identical distributions"

    def test_reproducible_with_same_seed(self, rng):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([3.0, 4.0, 5.0, 6.0, 7.0])
        result1 = bootstrap_ci(a, b, n_boot=500, seed=42)
        result2 = bootstrap_ci(a, b, n_boot=500, seed=42)
        assert result1 == result2


class TestBootstrapTrendCI:
    def test_detects_negative_trend(self):
        years = np.arange(1985, 2025)
        # Strong negative trend (glacier retreat)
        areas = np.linspace(100, 50, len(years))
        lo, hi = bootstrap_trend_ci(years, areas, n_boot=500)
        assert hi < 0, "CI should be entirely negative for retreating glacier"

    def test_detects_no_trend(self, rng):
        years = np.arange(1985, 2025)
        areas = rng.normal(100, 1, len(years))  # flat with noise
        lo, hi = bootstrap_trend_ci(years, areas, n_boot=500)
        # CI should contain 0 (no significant trend)
        assert lo <= 0 <= hi or abs(lo) < 0.1


class TestMannKendall:
    def test_strictly_decreasing(self):
        values = np.arange(20, 0, -1).astype(float)
        trend, p = mann_kendall_test(values)
        assert trend == "decreasing"
        assert p < 0.05

    def test_strictly_increasing(self):
        values = np.arange(1, 21).astype(float)
        trend, p = mann_kendall_test(values)
        assert trend == "increasing"
        assert p < 0.05

    def test_no_trend_random(self, rng):
        values = rng.normal(0, 1, 50)
        trend, p = mann_kendall_test(values)
        # Random data should usually show no trend
        assert isinstance(trend, str)
        assert 0 <= p <= 1

    def test_too_short_returns_no_trend(self):
        trend, p = mann_kendall_test(np.array([1.0, 2.0, 3.0]))
        assert trend == "no trend"
        assert p == 1.0

    def test_constant_returns_no_trend(self):
        trend, p = mann_kendall_test(np.full(20, 5.0))
        assert trend == "no trend"


class TestWelchTTest:
    def test_detects_real_difference(self, rng):
        a = rng.normal(0, 1, 100)
        b = rng.normal(5, 1, 100)
        result = welch_ttest(a, b)
        assert result["is_significant"]
        assert result["p_value"] < 0.05
        assert result["mean_diff"] > 0

    def test_no_difference(self, rng):
        a = rng.normal(0, 1, 200)
        b = rng.normal(0, 1, 200)
        result = welch_ttest(a, b)
        assert not result["is_significant"]
        assert result["p_value"] > 0.05

    def test_returns_required_keys(self, rng):
        a = rng.normal(0, 1, 50)
        b = rng.normal(1, 1, 50)
        result = welch_ttest(a, b)
        assert {"t_statistic", "p_value", "mean_diff", "is_significant"} <= set(result)


class TestBootstrapStatistic:
    def test_mean(self, rng):
        data = rng.normal(5, 1, 1000)
        point, lo, hi = bootstrap_statistic(data, np.mean, n_boot=500)
        assert lo < point < hi
        assert abs(point - 5) < 0.5

    def test_median(self, rng):
        data = rng.normal(0, 1, 500)
        point, lo, hi = bootstrap_statistic(data, np.median, n_boot=500)
        assert abs(point) < 0.5  # median of N(0,1) is ~0


class TestAreaUncertainty:
    def test_zero_for_empty_mask(self):
        mask = np.zeros((50, 50), dtype=bool)
        unc = area_uncertainty_boundary(mask)
        assert unc == 0.0

    def test_positive_for_real_glacier(self, synthetic_glacier_mask):
        unc = area_uncertainty_boundary(synthetic_glacier_mask, pixel_size_m=30)
        assert unc > 0

    def test_scales_with_pixel_size(self, synthetic_glacier_mask):
        unc_30 = area_uncertainty_boundary(synthetic_glacier_mask, pixel_size_m=30)
        unc_60 = area_uncertainty_boundary(synthetic_glacier_mask, pixel_size_m=60)
        # Larger pixels → larger uncertainty
        assert unc_60 > unc_30
