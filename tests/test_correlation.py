"""Tests for glacier_toolkit.analyze.correlation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from glacier_toolkit.analyze.correlation import (
    build_results_table,
    compute_climate_glacier_correlation,
    compute_climate_sensitivity,
    cross_glacier_regression,
    per_region_summary,
)


@pytest.fixture
def coupled_pair():
    """Synthetic glacier-climate pair with strong negative coupling."""
    years = np.arange(1985, 2025)
    rng = np.random.default_rng(42)
    temp_c = np.linspace(10, 12, len(years)) + rng.normal(0, 0.2, len(years))
    area_km2 = 100 - 15 * (temp_c - 10) + rng.normal(0, 1, len(years))
    return (
        pd.DataFrame({"year": years, "area_km2": area_km2}),
        pd.DataFrame({"year": years, "temp_c": temp_c}),
    )


class TestComputeClimateGlacierCorrelation:
    def test_detects_strong_anticorrelation(self, coupled_pair):
        area_df, temp_df = coupled_pair
        result = compute_climate_glacier_correlation(area_df, temp_df)
        assert result["pearson_r"] < -0.7  # strong negative
        assert result["pearson_p"] < 0.001
        assert result["n_years"] == 40

    def test_returns_required_keys(self, coupled_pair):
        area_df, temp_df = coupled_pair
        result = compute_climate_glacier_correlation(area_df, temp_df)
        for key in ["n_years", "pearson_r", "pearson_p", "spearman_r", "spearman_p"]:
            assert key in result

    def test_short_series_returns_nan(self):
        area_df = pd.DataFrame({"year": [2020, 2021], "area_km2": [10, 9]})
        temp_df = pd.DataFrame({"year": [2020, 2021], "temp_c": [12, 13]})
        result = compute_climate_glacier_correlation(area_df, temp_df)
        assert np.isnan(result["pearson_r"])


class TestComputeClimateSensitivity:
    def test_detects_negative_sensitivity(self, coupled_pair):
        area_df, temp_df = coupled_pair
        result = compute_climate_sensitivity(area_df, temp_df, n_boot=200)
        # Coupled with -15 km²/°C
        assert result["sensitivity_km2_per_c"] < 0
        assert -20 < result["sensitivity_km2_per_c"] < -10
        assert result["is_significant"]
        assert result["sign_correct"]

    def test_ci_brackets_estimate(self, coupled_pair):
        area_df, temp_df = coupled_pair
        result = compute_climate_sensitivity(area_df, temp_df, n_boot=200)
        assert result["ci_lower"] <= result["sensitivity_km2_per_c"] <= result["ci_upper"]

    def test_no_relationship(self):
        years = np.arange(1985, 2025)
        rng = np.random.default_rng(42)
        area_df = pd.DataFrame({"year": years, "area_km2": rng.normal(100, 1, 40)})
        temp_df = pd.DataFrame({"year": years, "temp_c": rng.normal(10, 0.5, 40)})
        result = compute_climate_sensitivity(area_df, temp_df, n_boot=200)
        # CI should bracket zero for uncorrelated data
        assert result["ci_lower"] < 0 < result["ci_upper"] or not result["is_significant"]


class TestCrossGlacierRegression:
    def test_detects_cross_glacier_pattern(self):
        # Synthetic: more warming → more retreat
        results = []
        for i in range(15):
            results.append(
                {
                    "warming_rate_c_per_decade": 0.1 + i * 0.1,
                    "retreat_rate_km2_per_year": -0.5 - i * 0.5,
                    "glacier_name": f"G{i}",
                    "glacier_region": "Test",
                }
            )
        cross = cross_glacier_regression(results)
        assert cross["n_glaciers"] == 15
        assert cross["pearson_r"] < -0.9
        assert cross["regression_slope"] < 0  # more warming → more (negative) retreat

    def test_too_few_glaciers(self):
        results = [
            {
                "warming_rate_c_per_decade": 0.5,
                "retreat_rate_km2_per_year": -0.3,
                "glacier_name": "A",
                "glacier_region": "X",
            }
        ]
        cross = cross_glacier_regression(results)
        assert np.isnan(cross["pearson_r"])


class TestPerRegionSummary:
    def test_groups_by_region(self):
        results = [
            {
                "glacier_name": "A",
                "glacier_region": "Alps",
                "warming_rate_c_per_decade": 0.5,
                "retreat_rate_km2_per_year": -0.3,
                "sensitivity_km2_per_c": -10,
                "sensitivity_p_value": 0.01,
            },
            {
                "glacier_name": "B",
                "glacier_region": "Alps",
                "warming_rate_c_per_decade": 0.6,
                "retreat_rate_km2_per_year": -0.4,
                "sensitivity_km2_per_c": -12,
                "sensitivity_p_value": 0.02,
            },
            {
                "glacier_name": "C",
                "glacier_region": "Andes",
                "warming_rate_c_per_decade": 0.3,
                "retreat_rate_km2_per_year": -0.2,
                "sensitivity_km2_per_c": -8,
                "sensitivity_p_value": 0.10,
            },
        ]
        df = per_region_summary(results)
        assert len(df) == 2  # Alps + Andes
        alps = df[df["glacier_region"] == "Alps"].iloc[0]
        assert alps["n_glaciers"] == 2
        assert alps["n_significant"] == 2  # both p < 0.05


class TestBuildResultsTable:
    def test_returns_dataframe(self):
        results = [
            {
                "glacier_name": "Aletsch",
                "glacier_region": "Alps",
                "year_start": 1985,
                "year_end": 2024,
                "area_change_pct": -25.0,
                "retreat_rate_km2_per_year": -0.5,
                "warming_rate_c_per_decade": 0.7,
                "sensitivity_km2_per_c": -12.0,
                "sensitivity_r_squared": 0.6,
                "sensitivity_p_value": 0.001,
            }
        ]
        df = build_results_table(results)
        assert len(df) == 1
        assert "Glacier" in df.columns
        assert "Sensitivity (km²/°C)" in df.columns
