"""Tests for glacier_toolkit.analyze.ndsi."""

from __future__ import annotations

import numpy as np
import pytest

from glacier_toolkit.analyze.ndsi import (
    classify_glacier,
    compute_area_uncertainty_km2,
    compute_glacier_area_km2,
    compute_ndsi,
)


class TestComputeNDSI:
    def test_returns_correct_shape(self):
        green = np.random.rand(50, 50)
        swir = np.random.rand(50, 50)
        ndsi = compute_ndsi(green, swir)
        assert ndsi.shape == (50, 50)

    def test_values_in_valid_range(self):
        green = np.random.rand(100, 100)
        swir = np.random.rand(100, 100)
        ndsi = compute_ndsi(green, swir)
        valid = ndsi[~np.isnan(ndsi)]
        assert valid.min() >= -1
        assert valid.max() <= 1

    def test_pure_snow(self):
        # Pure snow: high green reflectance, low SWIR
        green = np.full((10, 10), 0.9)
        swir = np.full((10, 10), 0.1)
        ndsi = compute_ndsi(green, swir)
        # NDSI = (0.9 - 0.1) / (0.9 + 0.1) = 0.8
        assert np.allclose(ndsi, 0.8)

    def test_pure_rock(self):
        # Rock: low green, high SWIR
        green = np.full((10, 10), 0.1)
        swir = np.full((10, 10), 0.4)
        ndsi = compute_ndsi(green, swir)
        # NDSI = (0.1 - 0.4) / (0.1 + 0.4) = -0.6
        assert np.allclose(ndsi, -0.6)

    def test_handles_zero_division(self):
        green = np.zeros((5, 5))
        swir = np.zeros((5, 5))
        ndsi = compute_ndsi(green, swir)
        assert np.all(np.isnan(ndsi))


class TestClassifyGlacier:
    def test_classifies_synthetic_glacier(self, synthetic_ndsi_array):
        mask = classify_glacier(synthetic_ndsi_array, threshold=0.4)
        assert mask.dtype == bool
        assert mask.sum() > 0  # the synthetic 'glacier' should be detected

    def test_threshold_affects_size(self, synthetic_ndsi_array):
        loose = classify_glacier(synthetic_ndsi_array, threshold=0.3)
        strict = classify_glacier(synthetic_ndsi_array, threshold=0.6)
        # Stricter threshold → smaller mask
        assert strict.sum() <= loose.sum()

    def test_filters_small_components(self):
        # Create an array with one big and one tiny ice patch
        arr = np.full((100, 100), -0.5)
        arr[40:60, 40:60] = 0.7  # 20x20 = 400 pixels = 0.36 km² @ 30m
        arr[5:7, 5:7] = 0.7  # 2x2 = 4 pixels = 0.0036 km² (too small)

        mask = classify_glacier(arr, threshold=0.4, min_area_km2=0.1, pixel_size_m=30)
        # The big patch should remain, the tiny one should be filtered
        assert mask[50, 50]  # center of big patch
        assert not mask[6, 6]  # center of tiny patch


class TestGlacierAreaCalculation:
    def test_zero_for_empty_mask(self):
        mask = np.zeros((100, 100), dtype=bool)
        assert compute_glacier_area_km2(mask, pixel_size_m=30) == 0.0

    def test_correct_area_for_known_mask(self):
        # 100 pixels at 30m = 100 * 900 m² = 90,000 m² = 0.09 km²
        mask = np.zeros((50, 50), dtype=bool)
        mask[:10, :10] = True  # 100 pixels
        area = compute_glacier_area_km2(mask, pixel_size_m=30)
        assert abs(area - 0.09) < 1e-9

    def test_scales_with_pixel_size(self):
        mask = np.ones((10, 10), dtype=bool)  # 100 pixels
        a30 = compute_glacier_area_km2(mask, pixel_size_m=30)
        a60 = compute_glacier_area_km2(mask, pixel_size_m=60)
        # 60m pixels = 4x area
        assert abs(a60 / a30 - 4) < 1e-9


class TestAreaUncertainty:
    def test_zero_for_empty_mask(self):
        mask = np.zeros((50, 50), dtype=bool)
        assert compute_area_uncertainty_km2(mask) == 0.0

    def test_positive_for_real_glacier(self, synthetic_glacier_mask):
        unc = compute_area_uncertainty_km2(synthetic_glacier_mask)
        assert unc > 0
