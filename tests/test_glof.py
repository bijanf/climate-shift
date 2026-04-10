"""Tests for glacier_toolkit.glof — risk classification, lake timeseries, detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from glacier_toolkit.glof.lake_detection import (
    classify_lake_dam_type,
    detect_glacial_lakes,
    flag_new_lakes,
)
from glacier_toolkit.glof.lake_timeseries import (
    detect_rapid_growth,
    estimate_lake_volume,
)
from glacier_toolkit.glof.risk_classify import (
    RISK_THRESHOLDS,
    classify_risk,
    generate_risk_table,
    score_dam_type,
    score_downstream_population,
    score_growth_rate,
    score_lake_area,
    score_volume,
)


class TestRiskScoring:
    def test_lake_area_scoring_monotonic(self):
        scores = [score_lake_area(a) for a in [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]]
        assert scores == sorted(scores), "Scores should monotonically increase with area"

    def test_growth_rate_scoring_monotonic(self):
        scores = [score_growth_rate(g) for g in [0, 1, 3, 5, 10]]
        assert scores == sorted(scores)

    def test_dam_type_moraine_highest(self):
        assert score_dam_type("moraine") > score_dam_type("ice")
        assert score_dam_type("ice") > score_dam_type("bedrock")

    def test_population_scoring_monotonic(self):
        scores = [score_downstream_population(p) for p in [0, 50, 500, 5000, 50000]]
        assert scores == sorted(scores)


class TestClassifyRisk:
    def test_high_risk_lake(self):
        result = classify_risk(
            {
                "area_km2": 1.0,
                "growth_rate_pct_per_year": 10,
                "dam_type": "moraine",
                "volume_million_m3": 10,
                "downstream_population": 50000,
                "flow_distance_km": 5,
                "glacier_slope_deg": 45,
            }
        )
        assert result["risk_level"] == "VERY HIGH"
        assert result["composite_score"] >= RISK_THRESHOLDS["VERY HIGH"]

    def test_low_risk_lake(self):
        result = classify_risk(
            {
                "area_km2": 0.001,
                "growth_rate_pct_per_year": 0,
                "dam_type": "bedrock",
                "volume_million_m3": 0.001,
                "downstream_population": 0,
                "flow_distance_km": 100,
                "glacier_slope_deg": 5,
            }
        )
        assert result["risk_level"] == "LOW"

    def test_returns_factor_breakdown(self):
        result = classify_risk({"area_km2": 0.5, "dam_type": "moraine"})
        assert "factor_scores" in result
        assert isinstance(result["factor_scores"], dict)


class TestGenerateRiskTable:
    def test_returns_dataframe(self):
        records = [
            {"name": "Lake A", "area_km2": 0.5, "dam_type": "moraine"},
            {"name": "Lake B", "area_km2": 0.1, "dam_type": "bedrock"},
        ]
        table = generate_risk_table(records)
        assert isinstance(table, pd.DataFrame)
        assert len(table) == 2

    def test_sorted_by_score_descending(self):
        records = [
            {"name": "Low", "area_km2": 0.01, "dam_type": "bedrock"},
            {
                "name": "High",
                "area_km2": 1.0,
                "dam_type": "moraine",
                "growth_rate_pct_per_year": 10,
                "downstream_population": 10000,
            },
        ]
        table = generate_risk_table(records)
        assert table["Score"].iloc[0] >= table["Score"].iloc[1]

    def test_has_expected_columns(self):
        records = [{"name": "Test", "area_km2": 0.1}]
        table = generate_risk_table(records)
        expected = {"Lake", "Area (km²)", "Dam Type", "Risk Level", "Score"}
        assert expected <= set(table.columns)


class TestEstimateLakeVolume:
    def test_huggel2002_known_value(self):
        # Huggel et al. 2002: V = 0.104 * A^1.42
        # For 0.5 km² = 500,000 m²:
        # V = 0.104 * 500000^1.42 ≈ 1.29e7 m³ ≈ 12.87 million m³
        vol = estimate_lake_volume(0.5, method="huggel2002")
        assert abs(vol - 12.87) < 0.1

    def test_volume_scales_with_area(self):
        v1 = estimate_lake_volume(0.1)
        v2 = estimate_lake_volume(1.0)
        assert v2 > v1 * 5  # nonlinear scaling

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown method"):
            estimate_lake_volume(1.0, method="bogus")


class TestDetectRapidGrowth:
    def test_flags_rapid_growth(self):
        df = pd.DataFrame(
            {
                "year": np.arange(2000, 2025),
                "area_km2": np.linspace(0.1, 1.0, 25),  # 10x growth in 25 years
            }
        )
        result = detect_rapid_growth(df, threshold_pct_per_year=5)
        assert result["is_rapid"]
        assert result["growth_rate_pct_per_year"] > 5

    def test_no_growth_flagged(self):
        df = pd.DataFrame(
            {
                "year": np.arange(2000, 2025),
                "area_km2": np.full(25, 0.5),  # constant
            }
        )
        result = detect_rapid_growth(df)
        assert not result["is_rapid"]


class TestLakeDetection:
    def test_detects_proglacial_lake(self):
        # Glacier in top-left, lake adjacent to it
        ndwi = np.full((100, 100), -0.5)
        ndwi[40:50, 30:40] = 0.5  # lake right next to glacier

        glacier_mask = np.zeros((100, 100), dtype=bool)
        glacier_mask[30:50, 10:30] = True  # glacier adjacent to lake

        lakes = detect_glacial_lakes(
            ndwi, glacier_mask, buffer_pixels=10, min_area_km2=0.001, pixel_size_m=30
        )
        assert len(lakes) >= 1

    def test_classify_dam_type_ice(self):
        lake = {"distance_to_glacier_m": 30}
        assert classify_lake_dam_type(lake, glacier_mask=None) == "ice"

    def test_classify_dam_type_moraine(self):
        lake = {"distance_to_glacier_m": 500}
        assert classify_lake_dam_type(lake, glacier_mask=None) == "moraine"

    def test_classify_dam_type_bedrock(self):
        lake = {"distance_to_glacier_m": 5000}
        assert classify_lake_dam_type(lake, glacier_mask=None) == "bedrock"


class TestFlagNewLakes:
    def test_finds_new_lakes(self):
        historical = [
            {"centroid_row": 10, "centroid_col": 10, "area_km2": 0.1},
        ]
        current = [
            {"centroid_row": 10, "centroid_col": 10, "area_km2": 0.2},  # match
            {"centroid_row": 80, "centroid_col": 80, "area_km2": 0.3},  # new
        ]
        new = flag_new_lakes(current, historical, match_tolerance_pixels=5)
        assert len(new) == 1
        assert new[0]["centroid_row"] == 80
