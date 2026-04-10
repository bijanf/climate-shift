"""
Multi-factor GLOF risk classification framework.

Assigns risk levels (LOW / MODERATE / HIGH / VERY HIGH) to glacial lakes
based on multiple hazard indicators.

References:
  - Emmer & Vilimek (2013) — dam type classification
  - Huggel et al. (2004) — GLOF hazard assessment
  - Worni et al. (2014) — downstream impact assessment
"""

import numpy as np
import pandas as pd


# Risk factor weights (sum to 1.0)
RISK_WEIGHTS = {
    "lake_area": 0.15,
    "lake_growth_rate": 0.20,
    "dam_type": 0.20,
    "estimated_volume": 0.15,
    "downstream_population": 0.15,
    "flow_distance": 0.10,
    "glacier_steepness": 0.05,
}

# Risk level thresholds (on 0-100 composite score)
RISK_THRESHOLDS = {
    "VERY HIGH": 75,
    "HIGH": 50,
    "MODERATE": 25,
    "LOW": 0,
}


def score_lake_area(area_km2):
    """Score lake area on a 0-100 scale."""
    if area_km2 >= 1.0:
        return 100
    elif area_km2 >= 0.5:
        return 80
    elif area_km2 >= 0.1:
        return 60
    elif area_km2 >= 0.01:
        return 30
    return 10


def score_growth_rate(pct_per_year):
    """Score lake growth rate on a 0-100 scale."""
    if pct_per_year >= 10:
        return 100
    elif pct_per_year >= 5:
        return 80
    elif pct_per_year >= 2:
        return 50
    elif pct_per_year >= 0.5:
        return 25
    return 10


def score_dam_type(dam_type):
    """Score dam type (moraine is most dangerous)."""
    scores = {
        "moraine": 100,
        "ice": 80,
        "bedrock": 20,
    }
    return scores.get(dam_type, 50)


def score_volume(volume_million_m3):
    """Score estimated lake volume."""
    if volume_million_m3 >= 10:
        return 100
    elif volume_million_m3 >= 1:
        return 75
    elif volume_million_m3 >= 0.1:
        return 50
    elif volume_million_m3 >= 0.01:
        return 25
    return 10


def score_downstream_population(population):
    """Score downstream population exposure."""
    if population >= 10000:
        return 100
    elif population >= 1000:
        return 80
    elif population >= 100:
        return 50
    elif population >= 10:
        return 25
    return 5


def score_flow_distance(distance_km):
    """Score proximity (closer = higher risk)."""
    if distance_km <= 5:
        return 100
    elif distance_km <= 15:
        return 75
    elif distance_km <= 30:
        return 50
    elif distance_km <= 50:
        return 25
    return 10


def score_glacier_steepness(mean_slope_deg):
    """Score glacier steepness above lake (steeper = higher avalanche risk)."""
    if mean_slope_deg >= 45:
        return 100
    elif mean_slope_deg >= 30:
        return 70
    elif mean_slope_deg >= 20:
        return 40
    return 15


def classify_risk(lake_record):
    """Compute multi-factor GLOF risk score and classification.

    Parameters
    ----------
    lake_record : dict
        Keys (all optional, defaults to conservative values):
        - area_km2: float
        - growth_rate_pct_per_year: float
        - dam_type: str ("moraine", "ice", "bedrock")
        - volume_million_m3: float
        - downstream_population: float
        - flow_distance_km: float
        - glacier_slope_deg: float

    Returns
    -------
    dict
        Keys: composite_score (0-100), risk_level (str),
        factor_scores (dict of individual scores).
    """
    factor_scores = {
        "lake_area": score_lake_area(
            lake_record.get("area_km2", 0)),
        "lake_growth_rate": score_growth_rate(
            lake_record.get("growth_rate_pct_per_year", 0)),
        "dam_type": score_dam_type(
            lake_record.get("dam_type", "moraine")),
        "estimated_volume": score_volume(
            lake_record.get("volume_million_m3", 0)),
        "downstream_population": score_downstream_population(
            lake_record.get("downstream_population", 0)),
        "flow_distance": score_flow_distance(
            lake_record.get("flow_distance_km", 50)),
        "glacier_steepness": score_glacier_steepness(
            lake_record.get("glacier_slope_deg", 0)),
    }

    composite = sum(
        factor_scores[k] * RISK_WEIGHTS[k] for k in RISK_WEIGHTS
    )

    risk_level = "LOW"
    for level, threshold in sorted(RISK_THRESHOLDS.items(),
                                    key=lambda x: x[1], reverse=True):
        if composite >= threshold:
            risk_level = level
            break

    return {
        "composite_score": round(composite, 1),
        "risk_level": risk_level,
        "factor_scores": factor_scores,
    }


def generate_risk_table(lake_records):
    """Generate a publication-ready risk assessment table.

    Parameters
    ----------
    lake_records : list of dict
        Each dict should have 'name' and the keys expected by classify_risk().

    Returns
    -------
    pandas.DataFrame
        Table with columns: Lake, Area, Growth Rate, Dam Type, Volume,
        Population, Distance, Composite Score, Risk Level.
        Suitable for LaTeX export via df.to_latex().
    """
    rows = []
    for rec in lake_records:
        result = classify_risk(rec)
        rows.append({
            "Lake": rec.get("name", "Unknown"),
            "Area (km²)": f"{rec.get('area_km2', 0):.3f}",
            "Growth (%/yr)": f"{rec.get('growth_rate_pct_per_year', 0):.1f}",
            "Dam Type": rec.get("dam_type", "—"),
            "Volume (M m³)": f"{rec.get('volume_million_m3', 0):.2f}",
            "Pop. at Risk": f"{rec.get('downstream_population', 0):,.0f}",
            "Dist. (km)": f"{rec.get('flow_distance_km', 0):.1f}",
            "Score": result["composite_score"],
            "Risk Level": result["risk_level"],
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    return df
