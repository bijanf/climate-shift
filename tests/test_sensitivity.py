"""Tests for glacier_toolkit.analyze.sensitivity."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from glacier_toolkit.analyze.correlation import cross_glacier_regression
from glacier_toolkit.analyze.sensitivity import (
    define_sensitivity_grid,
    summarize_robustness,
)


class TestDefineSensitivityGrid:
    def test_returns_list_of_dicts(self):
        variants = define_sensitivity_grid()
        assert len(variants) >= 5
        for v in variants:
            assert "name" in v
            assert "category" in v
            assert "ndsi_threshold" in v
            assert "rolling_window" in v
            assert "year_start" in v
            assert "year_end" in v
            assert "method" in v

    def test_first_variant_is_default(self):
        variants = define_sensitivity_grid()
        assert variants[0]["category"] == "default"
        # Default should match the central paper finding parameters
        assert variants[0]["ndsi_threshold"] == 0.40
        assert variants[0]["rolling_window"] == 3
        assert variants[0]["method"] == "ols"

    def test_categories_present(self):
        variants = define_sensitivity_grid()
        categories = {v["category"] for v in variants}
        # Must cover the four key dimensions plus default
        for expected in {"default", "ndsi_threshold", "rolling_window", "method"}:
            assert expected in categories

    def test_ndsi_sweep_brackets_default(self):
        variants = define_sensitivity_grid()
        ndsi_variants = [v for v in variants if v["category"] == "ndsi_threshold"]
        thresholds = [v["ndsi_threshold"] for v in ndsi_variants]
        assert min(thresholds) < 0.40 < max(thresholds)


class TestSummarizeRobustness:
    def test_all_significant_negative(self):
        # Synthetic sensitivity sweep with consistently strong results
        df = pd.DataFrame(
            {
                "spearman_rho_land": [-0.85, -0.80, -0.78, -0.82, -0.86],
                "spearman_p_land": [0.0002, 0.001, 0.005, 0.001, 0.0001],
            }
        )
        summary = summarize_robustness(df)
        assert summary["n_variants"] == 5
        assert summary["all_significant"] is True
        assert summary["all_negative"] is True
        assert summary["rho_min"] == -0.86
        assert summary["rho_max"] == -0.78
        assert -0.86 <= summary["rho_mean"] <= -0.78

    def test_mixed_significance(self):
        df = pd.DataFrame(
            {
                "spearman_rho_land": [-0.85, -0.40, -0.30],
                "spearman_p_land": [0.001, 0.06, 0.20],
            }
        )
        summary = summarize_robustness(df)
        assert summary["all_significant"] is False
        assert summary["all_negative"] is True
        assert summary["n_significant"] == 1

    def test_empty_input(self):
        df = pd.DataFrame(
            {
                "spearman_rho_land": [np.nan, np.nan],
                "spearman_p_land": [np.nan, np.nan],
            }
        )
        summary = summarize_robustness(df)
        assert summary["n_variants"] == 0


class TestTheilSenRegression:
    """Tests for the new Theil-Sen option in cross_glacier_regression."""

    def test_theilsen_returns_method_field(self):
        results = [
            {
                "warming_rate_c_per_decade": 0.1 * i,
                "retreat_rate_km2_per_year": -0.5 * i,
                "glacier_name": f"G{i}",
                "glacier_region": "X",
                "terminus_type": "land",
            }
            for i in range(1, 11)
        ]
        out = cross_glacier_regression(results, method="theilsen")
        assert out["method"] == "theilsen"
        assert out["theilsen_ci_lower"] is not None
        assert out["theilsen_ci_upper"] is not None
        # CI should bracket the slope
        assert out["theilsen_ci_lower"] <= out["regression_slope"] <= out["theilsen_ci_upper"]

    def test_ols_returns_method_field(self):
        results = [
            {
                "warming_rate_c_per_decade": 0.1 * i,
                "retreat_rate_km2_per_year": -0.5 * i,
                "glacier_name": f"G{i}",
                "glacier_region": "X",
                "terminus_type": "land",
            }
            for i in range(1, 11)
        ]
        out = cross_glacier_regression(results, method="ols")
        assert out["method"] == "ols"
        assert out["theilsen_ci_lower"] is None

    def test_theilsen_robust_to_outlier(self):
        # 9 clean points + 1 huge outlier
        warming = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.5]
        retreat = [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7, -0.8, -0.9, -100]
        results = [
            {
                "warming_rate_c_per_decade": w,
                "retreat_rate_km2_per_year": r,
                "glacier_name": f"G{i}",
                "glacier_region": "X",
                "terminus_type": "land",
            }
            for i, (w, r) in enumerate(zip(warming, retreat, strict=False))
        ]
        ols = cross_glacier_regression(results, method="ols")
        ts = cross_glacier_regression(results, method="theilsen")
        # The OLS slope is dragged toward the outlier; Theil-Sen is not
        # so |OLS slope| > |Theil-Sen slope|
        assert abs(ols["regression_slope"]) > abs(ts["regression_slope"])
