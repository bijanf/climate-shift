"""
Local climate extraction at glacier locations.

Reads CRU TS v4.09 gridded temperature data and extracts a local climate
time series for any glacier coordinate. Computes warming rates with
bootstrap confidence intervals.

The CRU TS dataset:
  - Resolution: 0.5° gridded (~50 km)
  - Coverage: global land, 1901-2024
  - Variables: tmx (max temp), tmn (min temp), tmp (mean temp), pre (precip)
  - Reference: Harris et al. 2020, Scientific Data

We use tmx (maximum monthly temperature) for melt-relevant warming.

Usage
-----
>>> from glacier_toolkit.analyze.climate_link import (
...     extract_local_temperature,
...     compute_local_warming_rate,
... )
>>> ts = extract_local_temperature(lat=46.45, lon=8.05, season=[6, 7, 8])
>>> rate = compute_local_warming_rate(ts, year_start=1985, year_end=2024)
>>> print(f"Aletsch local warming: {rate['slope_c_per_decade']:.2f} °C/decade")
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
from scipy import stats

from ..config import BOOTSTRAP_N, BOOTSTRAP_SEED, CI_LEVEL, PROJECT_ROOT

# Default CRU TS file (already downloaded by the existing climate shift project)
CRU_TS_TMX = PROJECT_ROOT / "data" / "cru_ts4.09.1901.2024.tmx.dat.nc"


def _load_cru_dataset(path=None):
    """Load the CRU TS netCDF dataset (cached after first call)."""
    if path is None:
        path = CRU_TS_TMX
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"CRU TS file not found: {path}\n"
            f"Download via plot_climate_maps.py or place it at this path."
        )
    return xr.open_dataset(path)


def extract_local_temperature(
    lat,
    lon,
    season=None,
    year_start=1985,
    year_end=2024,
    bbox_pad_deg=0.5,
    cru_path=None,
    variable="tmx",
):
    """Extract a local annual mean temperature time series from CRU TS.

    Parameters
    ----------
    lat, lon : float
        Glacier center coordinates in decimal degrees.
    season : list of int, optional
        Month numbers to average over (e.g. [6, 7, 8] for NH summer).
        If None, uses all months (annual mean).
    year_start, year_end : int
        Time range to extract.
    bbox_pad_deg : float
        Half-width of the box around (lat, lon) to average over.
        Default 0.5° gives a 1°×1° box (≈ 2×2 CRU cells).
    cru_path : Path, optional
        Override the default CRU TS file path.
    variable : str
        CRU variable name. Default "tmx" (max monthly temperature).

    Returns
    -------
    pandas.DataFrame
        Columns:
        - year: int
        - temp_c: float (mean of season months in °C)
        - n_months: int (number of valid months in the average)
    """
    ds = _load_cru_dataset(cru_path)

    # Subset spatial box
    box = ds[variable].sel(
        lat=slice(lat - bbox_pad_deg, lat + bbox_pad_deg),
        lon=slice(lon - bbox_pad_deg, lon + bbox_pad_deg),
    )

    # Spatial mean (cosine-weighted by latitude)
    weights = np.cos(np.deg2rad(box.lat))
    box_mean = box.weighted(weights).mean(dim=["lat", "lon"])

    # Subset time range
    box_mean = box_mean.sel(time=slice(f"{year_start}-01-01", f"{year_end}-12-31"))

    # Filter to season if specified
    if season is not None:
        box_mean = box_mean.sel(time=box_mean.time.dt.month.isin(season))

    # Annual aggregation
    df = box_mean.to_dataframe().reset_index()
    df["year"] = df["time"].dt.year
    df = df.dropna(subset=[variable])

    annual = (
        df.groupby("year")
        .agg(temp_c=(variable, "mean"), n_months=(variable, "count"))
        .reset_index()
    )

    ds.close()
    return annual


def compute_local_warming_rate(
    temperature_df,
    year_start=None,
    year_end=None,
    n_boot=BOOTSTRAP_N,
    ci=CI_LEVEL,
    seed=BOOTSTRAP_SEED,
):
    """Fit a linear warming trend to a temperature time series with bootstrap CI.

    Parameters
    ----------
    temperature_df : DataFrame
        From extract_local_temperature(). Must have 'year' and 'temp_c'.
    year_start, year_end : int, optional
        Subset the time range. If None, uses the full series.
    n_boot, ci, seed : numeric
        Bootstrap parameters (defaults match project conventions).

    Returns
    -------
    dict
        Keys:
        - slope_c_per_year: float
        - slope_c_per_decade: float
        - intercept_c: float
        - r_squared: float
        - p_value: float
        - ci_lower: float (95% CI lower bound on slope, °C/year)
        - ci_upper: float (95% CI upper bound)
        - mk_trend: str ("increasing", "decreasing", "no trend")
        - mk_p_value: float
        - n_years: int
    """
    df = temperature_df
    if year_start is not None:
        df = df[df["year"] >= year_start]
    if year_end is not None:
        df = df[df["year"] <= year_end]

    if len(df) < 3:
        return {
            "slope_c_per_year": np.nan,
            "slope_c_per_decade": np.nan,
            "intercept_c": np.nan,
            "r_squared": np.nan,
            "p_value": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "mk_trend": "no trend",
            "mk_p_value": np.nan,
            "n_years": len(df),
        }

    years = df["year"].values.astype(float)
    temps = df["temp_c"].values

    # Linear regression
    fit = stats.linregress(years, temps)

    # Bootstrap CI on slope
    rng = np.random.default_rng(seed)
    n = len(years)
    slopes = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        slopes[i] = stats.linregress(years[idx], temps[idx]).slope
    ci_lo = float(np.percentile(slopes, (1 - ci) / 2 * 100))
    ci_hi = float(np.percentile(slopes, (1 + ci) / 2 * 100))

    # Mann-Kendall (reuse existing implementation)
    from .statistics import mann_kendall_test

    mk_trend, mk_p = mann_kendall_test(temps)

    return {
        "slope_c_per_year": float(fit.slope),
        "slope_c_per_decade": float(fit.slope * 10),
        "intercept_c": float(fit.intercept),
        "r_squared": float(fit.rvalue**2),
        "p_value": float(fit.pvalue),
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "mk_trend": mk_trend,
        "mk_p_value": float(mk_p),
        "n_years": int(n),
    }


def get_glacier_climate(glacier_config, year_start=1985, year_end=2024, **kwargs):
    """Convenience: get local temperature time series for a registry glacier.

    Parameters
    ----------
    glacier_config : dict
        A glacier entry from GLACIER_REGISTRY.
    year_start, year_end : int
    **kwargs : passed to extract_local_temperature.

    Returns
    -------
    DataFrame
        Annual local temperature time series.
    """
    return extract_local_temperature(
        lat=glacier_config["lat"],
        lon=glacier_config["lon"],
        season=glacier_config.get("season"),
        year_start=year_start,
        year_end=year_end,
        **kwargs,
    )


def get_glacier_warming_rate(glacier_config, year_start=1985, year_end=2024):
    """Convenience: get local warming rate for a registry glacier.

    Parameters
    ----------
    glacier_config : dict
    year_start, year_end : int

    Returns
    -------
    dict
        Same as compute_local_warming_rate(), plus a 'glacier_name' key.
    """
    ts = get_glacier_climate(glacier_config, year_start, year_end)
    rate = compute_local_warming_rate(ts)
    rate["glacier_name"] = glacier_config["name"]
    rate["glacier_region"] = glacier_config["region"]
    return rate
