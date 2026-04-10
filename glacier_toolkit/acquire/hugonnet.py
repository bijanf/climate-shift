"""
Hugonnet et al. 2021 per-glacier mass balance dataset loader.

Hugonnet, R., McNabb, R., Berthier, E. et al. (2021) "Accelerated global
glacier mass loss in the early twenty-first century". Nature 592, 726-731.
https://doi.org/10.1038/s41586-021-03436-z

Data DOI: https://doi.org/10.6096/13 (SEDOO/Theia)

The dataset provides per-glacier mass balance and area change estimates
for 217,175 glaciers worldwide for 1-, 2-, 4-, 5-, 10- and 20-year periods
within 2000-2019. We use it as an independent validation dataset for our
own NDSI-derived area trends.

Manual download required
------------------------
The SEDOO portal uses JavaScript-based download links that cannot be
fetched programmatically. The user must download the data manually:

  1. Visit https://doi.org/10.6096/13
  2. Navigate to the data files
  3. Download the CSV(s) of interest, typically:
       dh_*_rgi60_pergla_rates.csv  (per-glacier rates)
  4. Place files in glacier_data/hugonnet/

The loader auto-detects files in that directory.

Schema (per-glacier rates files)
--------------------------------
Each row is one glacier-period combination with columns:
  - rgiid               : RGI v6.0 glacier ID (e.g., 'RGI60-11.01450')
  - period              : Time period like '2000-01-01_2020-01-01'
  - area                : Glacier area in km^2
  - dhdt                : Elevation change rate (m/yr)
  - dhdt_err            : Uncertainty on dhdt
  - dmdt                : Mass balance rate (Gt/yr)
  - dmdt_err            : Uncertainty on dmdt
  - dmdtda              : Specific mass balance (m w.e./yr)
  - dmdtda_err          : Uncertainty on dmdtda
  - reg                 : RGI region (1-19)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import DATA_DIR

HUGONNET_DIR = DATA_DIR.parent / "glacier_data" / "hugonnet"
HUGONNET_DOI = "https://doi.org/10.6096/13"


def find_hugonnet_files(directory=None):
    """Find Hugonnet 2021 CSV files in the local data directory.

    Parameters
    ----------
    directory : Path, optional
        Where to look. Defaults to glacier_data/hugonnet/.

    Returns
    -------
    list of Path
        All matching CSV files. May be empty if user has not downloaded.
    """
    if directory is None:
        directory = HUGONNET_DIR
    directory = Path(directory)
    if not directory.exists():
        return []
    # Match common Hugonnet file naming patterns
    patterns = [
        "*pergla*.csv",
        "dh_*.csv",
        "*rates*.csv",
    ]
    files = set()
    for pat in patterns:
        files.update(directory.glob(pat))
    return sorted(files)


def load_hugonnet_pergla(path=None, period_filter="2000-01-01_2020-01-01"):
    """Load the Hugonnet per-glacier rates dataset.

    Parameters
    ----------
    path : Path, optional
        Path to a specific CSV. If None, auto-detects in HUGONNET_DIR.
    period_filter : str, optional
        Filter to a specific period (default 2000-2020 full record).
        Pass None to load all periods.

    Returns
    -------
    pandas.DataFrame
        Per-glacier mass balance with columns: rgiid, area, dmdt, dmdtda,
        plus their uncertainties and the period.

    Raises
    ------
    FileNotFoundError
        If no Hugonnet files are found in the local cache. Includes
        instructions for manual download.
    """
    if path is None:
        files = find_hugonnet_files()
        if not files:
            raise FileNotFoundError(
                f"No Hugonnet 2021 files found in {HUGONNET_DIR}.\n\n"
                "Manual download required:\n"
                f"  1. Visit {HUGONNET_DOI}\n"
                "  2. Download the per-glacier rates CSV\n"
                f"  3. Save to {HUGONNET_DIR}/\n\n"
                "The loader will auto-detect files matching '*pergla*.csv',\n"
                "'dh_*.csv', or '*rates*.csv'."
            )
        # Prefer files with 'pergla' in the name
        pergla = [f for f in files if "pergla" in f.name.lower()]
        path = pergla[0] if pergla else files[0]

    print(f"  Loading Hugonnet 2021: {path}")
    df = pd.read_csv(path)

    # Filter to a specific period if requested
    if period_filter and "period" in df.columns:
        before = len(df)
        df = df[df["period"] == period_filter]
        print(f"    Filtered to period {period_filter}: {len(df)}/{before} rows")

    return df


def match_to_glims_glaciers(hugonnet_df, glims_gdf):
    """Match Hugonnet RGIid to GLIMS glaciers by their RGI ID.

    GLIMS records carry an 'rgi_id' or similar field linking to RGI v6.0.
    For glaciers we've analyzed via the GLIMS pipeline, we can join the
    Hugonnet mass balance directly.

    Parameters
    ----------
    hugonnet_df : DataFrame
        From load_hugonnet_pergla().
    glims_gdf : GeoDataFrame or DataFrame
        GLIMS glacier records (must have an RGI ID column).

    Returns
    -------
    DataFrame
        Joined dataframe with both Hugonnet mass balance and GLIMS metadata.
    """
    # GLIMS typically uses 'glac_id' as the GLIMS-internal ID; the RGI
    # link is in 'rgi_id' or similar. We try several common column names.
    rgi_cols = ["rgi_id", "rgiid", "RGIId", "rgi_v6_id", "rgi60_id"]
    glims_rgi_col = None
    for col in rgi_cols:
        if col in glims_gdf.columns:
            glims_rgi_col = col
            break

    if glims_rgi_col is None:
        # Fall back to spatial match by centroid (slower, less accurate)
        print("  Warning: no RGI ID column in GLIMS data, cannot match to Hugonnet")
        return pd.DataFrame()

    # Hugonnet uses 'rgiid' typically
    hugo_id_col = "rgiid" if "rgiid" in hugonnet_df.columns else "RGIId"

    return pd.merge(
        glims_gdf,
        hugonnet_df,
        left_on=glims_rgi_col,
        right_on=hugo_id_col,
        how="inner",
    )


def validate_against_hugonnet(our_results_df, hugonnet_df):
    """Compare our retreat trends to Hugonnet mass balance trends.

    For each glacier we have, look up its Hugonnet mass balance, and
    compute the correlation between our area trend (km^2/yr) and Hugonnet's
    specific mass balance (m w.e./yr). Both should be negative for
    retreating glaciers, so the correlation should be positive.

    Parameters
    ----------
    our_results_df : DataFrame
        Output of run_global pipeline. Must have rgiid (or matching key)
        and retreat_rate_km2_per_year.
    hugonnet_df : DataFrame
        From load_hugonnet_pergla().

    Returns
    -------
    dict
        Keys: n_matched, pearson_r, pearson_p, spearman_r, spearman_p,
        slope, intercept.
    """
    from scipy import stats

    hugo_id_col = "rgiid" if "rgiid" in hugonnet_df.columns else "RGIId"
    rgi_cols = ["rgi_id", "rgiid", "rgi_v6_id"]
    our_id_col = None
    for col in rgi_cols:
        if col in our_results_df.columns:
            our_id_col = col
            break

    if our_id_col is None:
        return {"n_matched": 0, "error": "no RGI ID column in our results"}

    merged = pd.merge(
        our_results_df,
        hugonnet_df[[hugo_id_col, "dmdtda", "dmdtda_err"]],
        left_on=our_id_col,
        right_on=hugo_id_col,
        how="inner",
    ).dropna(subset=["retreat_rate_km2_per_year", "dmdtda"])

    if len(merged) < 5:
        return {"n_matched": len(merged), "error": "too few matches"}

    pr, pp = stats.pearsonr(merged["retreat_rate_km2_per_year"], merged["dmdtda"])
    sr, sp = stats.spearmanr(merged["retreat_rate_km2_per_year"], merged["dmdtda"])
    fit = stats.linregress(merged["retreat_rate_km2_per_year"], merged["dmdtda"])

    return {
        "n_matched": len(merged),
        "pearson_r": float(pr),
        "pearson_p": float(pp),
        "spearman_r": float(sr),
        "spearman_p": float(sp),
        "slope": float(fit.slope),
        "intercept": float(fit.intercept),
        "merged": merged,
    }
