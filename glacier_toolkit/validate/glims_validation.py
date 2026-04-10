"""
Validation of computed glacier areas against published GLIMS reference data.

GLIMS (Global Land Ice Measurements from Space) provides published glacier
outlines from multiple surveys. We use these as ground truth for our
NDSI-derived glacier masks, computing bias and RMSE.

Reference: https://www.glims.org / https://nsidc.org/data/glims
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compare_to_reference(computed_area_km2, reference_area_km2):
    """Compare a single computed glacier area to a published reference.

    Parameters
    ----------
    computed_area_km2 : float
        Our NDSI-derived area.
    reference_area_km2 : float
        Published reference (e.g. from GLIMS or a paper).

    Returns
    -------
    dict
        Keys:
        - bias_km2: float (computed - reference)
        - bias_pct: float ((computed - reference) / reference * 100)
        - relative_error_pct: float (abs(bias) / reference * 100)
    """
    if reference_area_km2 == 0:
        return {
            "bias_km2": float(computed_area_km2),
            "bias_pct": np.nan,
            "relative_error_pct": np.nan,
        }

    bias = computed_area_km2 - reference_area_km2
    return {
        "bias_km2": float(bias),
        "bias_pct": float(bias / reference_area_km2 * 100),
        "relative_error_pct": float(abs(bias) / reference_area_km2 * 100),
    }


def validate_against_references(comparisons):
    """Compute aggregate validation statistics across multiple glaciers.

    Parameters
    ----------
    comparisons : list of dict
        Each dict must have:
        - 'name': str
        - 'computed_km2': float
        - 'reference_km2': float
        - optional: 'reference_year', 'reference_source'

    Returns
    -------
    dict
        Keys:
        - n_glaciers
        - mean_bias_km2 (positive = we overestimate)
        - mean_bias_pct
        - rmse_km2
        - mean_absolute_error_pct
        - max_error_pct
        - per_glacier: DataFrame with all comparisons
    """
    rows = []
    for c in comparisons:
        result = compare_to_reference(c["computed_km2"], c["reference_km2"])
        rows.append({**c, **result})

    df = pd.DataFrame(rows)

    if len(df) == 0:
        return {
            "n_glaciers": 0,
            "mean_bias_km2": np.nan,
            "mean_bias_pct": np.nan,
            "rmse_km2": np.nan,
            "mean_absolute_error_pct": np.nan,
            "max_error_pct": np.nan,
            "per_glacier": df,
        }

    return {
        "n_glaciers": len(df),
        "mean_bias_km2": float(df["bias_km2"].mean()),
        "mean_bias_pct": float(df["bias_pct"].mean()),
        "rmse_km2": float(np.sqrt((df["bias_km2"] ** 2).mean())),
        "mean_absolute_error_pct": float(df["relative_error_pct"].mean()),
        "max_error_pct": float(df["relative_error_pct"].max()),
        "per_glacier": df,
    }


# ── Built-in reference values from published literature ──────────────────────
#
# These are *single-year published areas* used to spot-check our methodology.
# Sources are cited per row. For the paper, we'll add more references and
# document the matching methodology in the methods section.

PUBLISHED_REFERENCES = [
    {
        "key": "aletsch",
        "name": "Aletsch Glacier",
        "reference_km2": 79.6,
        "reference_year": 2016,
        "reference_source": "GLAMOS 2016 (Glamos Annual Report)",
    },
    {
        "key": "pasterze",
        "name": "Pasterze Glacier",
        "reference_km2": 16.5,
        "reference_year": 2015,
        "reference_source": "Fischer et al. 2015",
    },
    {
        "key": "mer_de_glace",
        "name": "Mer de Glace",
        "reference_km2": 32.0,
        "reference_year": 2018,
        "reference_source": "Vincent et al. 2019",
    },
    {
        "key": "gangotri",
        "name": "Gangotri Glacier",
        "reference_km2": 143.0,
        "reference_year": 2014,
        "reference_source": "Bhambri et al. 2011 / RGI v6.0",
    },
    {
        "key": "khumbu",
        "name": "Khumbu Glacier",
        "reference_km2": 17.0,
        "reference_year": 2015,
        "reference_source": "Bolch et al. 2008 / RGI v6.0",
    },
    {
        "key": "columbia",
        "name": "Columbia Glacier",
        "reference_km2": 920.0,
        "reference_year": 2015,
        "reference_source": "McNabb et al. 2014 / RGI v6.0",
    },
]


def get_published_reference(glacier_key):
    """Look up a built-in published reference area for a registry glacier.

    Parameters
    ----------
    glacier_key : str
        Registry key (e.g. "aletsch").

    Returns
    -------
    dict or None
        The reference record, or None if no published reference is available.
    """
    for ref in PUBLISHED_REFERENCES:
        if ref["key"] == glacier_key:
            return ref
    return None
