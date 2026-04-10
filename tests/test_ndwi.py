"""Tests for glacier_toolkit.analyze.ndwi."""

from __future__ import annotations

import numpy as np

from glacier_toolkit.analyze.ndwi import (
    compute_ndwi,
    detect_water_bodies,
    filter_proglacial_lakes,
    measure_lake_areas,
)


class TestComputeNDWI:
    def test_returns_correct_shape(self):
        green = np.random.rand(50, 50)
        nir = np.random.rand(50, 50)
        ndwi = compute_ndwi(green, nir)
        assert ndwi.shape == (50, 50)

    def test_pure_water(self):
        # Water: high green, low NIR
        green = np.full((10, 10), 0.6)
        nir = np.full((10, 10), 0.1)
        ndwi = compute_ndwi(green, nir)
        expected = (0.6 - 0.1) / (0.6 + 0.1)
        assert np.allclose(ndwi, expected)

    def test_pure_vegetation(self):
        # Vegetation: low green, high NIR
        green = np.full((10, 10), 0.2)
        nir = np.full((10, 10), 0.8)
        ndwi = compute_ndwi(green, nir)
        expected = (0.2 - 0.8) / (0.2 + 0.8)
        assert np.allclose(ndwi, expected)
        assert (ndwi < 0).all()


class TestDetectWaterBodies:
    def test_detects_synthetic_lake(self):
        ndwi = np.full((100, 100), -0.5)
        ndwi[40:60, 40:60] = 0.5  # 400-pixel "lake"
        mask = detect_water_bodies(ndwi, threshold=0.3, min_area_km2=0.1, pixel_size_m=30)
        assert mask[50, 50]
        assert mask.sum() > 0

    def test_filters_small_water_bodies(self):
        ndwi = np.full((100, 100), -0.5)
        ndwi[5:7, 5:7] = 0.5  # tiny pond — should be filtered
        mask = detect_water_bodies(ndwi, threshold=0.3, min_area_km2=0.5, pixel_size_m=30)
        assert mask.sum() == 0


class TestFilterProglacialLakes:
    def test_keeps_lakes_near_glacier(self):
        # Glacier in top-left, lake right next to it
        glacier = np.zeros((100, 100), dtype=bool)
        glacier[:30, :30] = True

        water = np.zeros((100, 100), dtype=bool)
        water[31:40, 31:40] = True  # adjacent lake

        result = filter_proglacial_lakes(water, glacier, max_distance_pixels=20)
        assert result.sum() > 0

    def test_removes_distant_water(self):
        glacier = np.zeros((100, 100), dtype=bool)
        glacier[:10, :10] = True

        water = np.zeros((100, 100), dtype=bool)
        water[80:90, 80:90] = True  # far away

        result = filter_proglacial_lakes(water, glacier, max_distance_pixels=10)
        assert result.sum() == 0


class TestMeasureLakeAreas:
    def test_measures_single_lake(self):
        water = np.zeros((100, 100), dtype=bool)
        water[40:60, 40:60] = True  # 400 pixels
        lakes = measure_lake_areas(water, pixel_size_m=30)
        assert len(lakes) == 1
        assert lakes[0]["n_pixels"] == 400
        assert abs(lakes[0]["area_km2"] - 0.36) < 1e-6  # 400 * 900 / 1e6

    def test_sorts_by_area_descending(self):
        water = np.zeros((100, 100), dtype=bool)
        water[10:20, 10:20] = True  # 100 pixels
        water[40:60, 40:60] = True  # 400 pixels
        water[80:85, 80:85] = True  # 25 pixels
        lakes = measure_lake_areas(water, pixel_size_m=30)
        assert len(lakes) == 3
        assert lakes[0]["n_pixels"] >= lakes[1]["n_pixels"] >= lakes[2]["n_pixels"]
