"""Shared pytest fixtures for the glacier_toolkit test suite."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def rng() -> np.random.Generator:
    """Reproducible random generator (seed=42, matching project default)."""
    return np.random.default_rng(42)


@pytest.fixture
def synthetic_glacier_mask() -> np.ndarray:
    """A 100x100 boolean mask with a circular 'glacier' in the center."""
    h, w = 100, 100
    yy, xx = np.ogrid[:h, :w]
    center_y, center_x, radius = 50, 50, 30
    return (yy - center_y) ** 2 + (xx - center_x) ** 2 <= radius**2


@pytest.fixture
def synthetic_ndsi_array(rng: np.random.Generator) -> np.ndarray:
    """A 100x100 NDSI array with a 'glacier' (NDSI > 0.4) in the center."""
    arr = rng.uniform(-0.5, 0.2, size=(100, 100))
    yy, xx = np.ogrid[:100, :100]
    glacier = (yy - 50) ** 2 + (xx - 50) ** 2 <= 30**2
    arr[glacier] = rng.uniform(0.5, 0.9, size=glacier.sum())
    return arr


@pytest.fixture
def synthetic_area_timeseries():
    """A pandas DataFrame mimicking a real glacier area time series with retreat."""
    import pandas as pd

    years = np.arange(1985, 2025)
    # Linear retreat from 100 km² to 60 km² with some noise
    rng = np.random.default_rng(42)
    areas = np.linspace(100, 60, len(years)) + rng.normal(0, 1.5, len(years))
    return pd.DataFrame(
        {
            "year": years,
            "area_km2": areas,
            "uncertainty_km2": np.full(len(years), 2.0),
            "n_pixels": (areas * 1000).astype(int),
        }
    )
