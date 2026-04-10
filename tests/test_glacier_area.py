"""Tests for glacier_toolkit.analyze.glacier_area."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from glacier_toolkit.analyze.glacier_area import (
    compute_area_change,
    detect_acceleration,
    fit_linear_trend,
)


class TestComputeAreaChange:
    def test_basic_change(self, synthetic_area_timeseries):
        result = compute_area_change(synthetic_area_timeseries)
        assert "change_km2" in result
        assert "change_pct" in result
        assert result["change_km2"] < 0  # synthetic series shows retreat

    def test_explicit_years(self, synthetic_area_timeseries):
        result = compute_area_change(
            synthetic_area_timeseries,
            baseline_year=1990,
            modern_year=2020,
        )
        assert result["baseline_year"] == 1990
        assert result["modern_year"] == 2020

    def test_invalid_year_raises(self, synthetic_area_timeseries):
        with pytest.raises(ValueError, match="not found"):
            compute_area_change(synthetic_area_timeseries, baseline_year=1800)


class TestFitLinearTrend:
    def test_returns_required_keys(self, synthetic_area_timeseries):
        result = fit_linear_trend(synthetic_area_timeseries)
        required = {
            "slope_km2_per_year",
            "intercept_km2",
            "r_squared",
            "ci_lower",
            "ci_upper",
            "mk_trend",
            "mk_p_value",
        }
        assert required <= set(result.keys())

    def test_detects_negative_trend(self, synthetic_area_timeseries):
        result = fit_linear_trend(synthetic_area_timeseries)
        # Synthetic series goes 100 → 60 over 40 years = -1 km²/yr
        assert result["slope_km2_per_year"] < 0
        assert result["mk_trend"] == "decreasing"

    def test_ci_brackets_slope(self, synthetic_area_timeseries):
        result = fit_linear_trend(synthetic_area_timeseries)
        assert result["ci_lower"] <= result["slope_km2_per_year"] <= result["ci_upper"]

    def test_high_r_squared_for_clean_trend(self):
        df = pd.DataFrame(
            {
                "year": np.arange(1985, 2025),
                "area_km2": np.linspace(100, 60, 40),  # perfectly linear
                "uncertainty_km2": np.ones(40),
            }
        )
        result = fit_linear_trend(df)
        assert result["r_squared"] > 0.99


class TestDetectAcceleration:
    def test_detects_accelerating_retreat(self):
        # Slow retreat early, fast retreat late
        df = pd.DataFrame(
            {
                "year": np.arange(1985, 2025),
                "area_km2": np.concatenate(
                    [
                        np.linspace(100, 95, 20),  # slow: -5 over 20 yr
                        np.linspace(95, 60, 20),  # fast: -35 over 20 yr
                    ]
                ),
                "uncertainty_km2": np.ones(40),
            }
        )
        result = detect_acceleration(df, breakpoint_year=2004)
        assert result["is_accelerating"]
        assert result["late_slope"] < result["early_slope"]

    def test_too_short_returns_nan(self):
        df = pd.DataFrame(
            {
                "year": [2020, 2021, 2022],
                "area_km2": [10.0, 9.0, 8.0],
                "uncertainty_km2": [1.0, 1.0, 1.0],
            }
        )
        result = detect_acceleration(df)
        assert np.isnan(result["early_slope"])
