"""
Server-side GEE batch processing for glacier area at scale.

This module is the technical core of the Phase 2 (Nature Geoscience)
analysis. Instead of downloading per-glacier GeoTIFFs and computing
NDSI locally, the entire pipeline runs inside Google Earth Engine and
returns just the per-glacier-per-year ice area as numbers.

Why server-side?
----------------
The Phase 1 pipeline downloads a 6-10 MB GeoTIFF per glacier per year.
For 200,000 glaciers × 40 years = 8 million downloads × ~8 MB =
~64 TB. Impossible.

Server-side, GEE does the NDSI classification, applies the per-glacier
polygon mask, sums the ice pixels, and returns just one floating-point
number per glacier per year. The total payload for the global analysis
is megabytes, not terabytes.

Throughput estimate
-------------------
GEE's parallel infrastructure handles ~100-500 glaciers per minute
in batched mode (depending on glacier size and Landsat collection
density). 200,000 glaciers × 40 years can complete in 6-12 hours.

For a region (e.g. Central Europe with ~900 glaciers), it's minutes.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .landsat import (
    HARMONIZATION_COEFFICIENTS,
    LANDSAT_COLLECTIONS,
    _best_sensor_for_year,
    _get_ee,
)


def _build_annual_ice_image(year, season_months, ndsi_threshold=0.40):
    """Build an annual binary ice mask image inside GEE.

    Parameters
    ----------
    year : int
    season_months : list of int
    ndsi_threshold : float

    Returns
    -------
    ee.Image
        Single-band image where ice pixels = 1, non-ice = 0.
    """
    ee = _get_ee()
    sensor_key = _best_sensor_for_year(year)
    info = LANDSAT_COLLECTIONS[sensor_key]

    # Date range
    if any(m <= 2 for m in season_months) and any(m >= 10 for m in season_months):
        start_date = f"{year - 1}-{min(m for m in season_months if m >= 10):02d}-01"
        end_date = f"{year}-{max(m for m in season_months if m <= 6):02d}-28"
    else:
        start_date = f"{year}-{min(season_months):02d}-01"
        end_month = max(season_months)
        end_date = f"{year}-{end_month:02d}-28" if end_month < 12 else f"{year}-12-31"

    # Build the collection — server-side
    coll = (
        ee.ImageCollection(info["collection"])
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", 50))
    )

    sf = info["scale_factor"]
    off = info["scale_offset"]
    green = info["green"]
    swir = info["swir1"]

    def process(img):
        # Scale factors
        scaled = img.select([green, swir]).multiply(sf).add(off)
        # Cloud mask
        qa = img.select("QA_PIXEL")
        cloud_shadow = qa.bitwiseAnd(1 << 3).eq(0)
        cloud = qa.bitwiseAnd(1 << 4).eq(0)
        scaled = scaled.updateMask(cloud_shadow).updateMask(cloud)
        # Cross-sensor harmonization (L5/L7 -> L8)
        if sensor_key in ("L5", "L7"):
            for band, key in [(green, "green"), (swir, "swir1")]:
                coeff = HARMONIZATION_COEFFICIENTS[key]
                harm = (
                    scaled.select(band)
                    .multiply(coeff["slope"])
                    .add(coeff["intercept"])
                    .rename(band)
                )
                scaled = scaled.addBands(harm, overwrite=True)
        return scaled.rename(["green", "swir"])

    composite = coll.map(process).median()

    # NDSI = (green - swir) / (green + swir)
    ndsi = composite.normalizedDifference(["green", "swir"]).rename("ndsi")

    # Binary ice mask — 1 where ice, 0 elsewhere
    ice = ndsi.gte(ndsi_threshold).rename("ice")
    return ice


def compute_glacier_areas_for_year(
    glacier_features, year, season_months, ndsi_threshold=0.40, scale=30
):
    """Compute ice area in km² for each glacier in a FeatureCollection.

    All computation happens server-side in GEE; only the final per-glacier
    area numbers are returned.

    Parameters
    ----------
    glacier_features : ee.FeatureCollection
        Glacier polygons (e.g. from glims_regions).
    year : int
    season_months : list of int
    ndsi_threshold : float
    scale : int
        Pixel size in meters. 30 for Landsat.

    Returns
    -------
    list of dict
        One dict per glacier with: glac_id (or feature id), ice_area_km2,
        plus any glacier metadata that was on the input feature.
    """
    ee = _get_ee()

    ice = _build_annual_ice_image(year, season_months, ndsi_threshold)

    # For each feature, sum the ice pixels within its polygon
    def reduce_one(feature):
        result = ice.multiply(ee.Image.pixelArea()).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=feature.geometry(),
            scale=scale,
            maxPixels=1e10,
            bestEffort=True,
        )
        return feature.set("ice_area_m2", result.get("ice"))

    reduced = glacier_features.map(reduce_one)
    raw = reduced.getInfo()

    rows = []
    for feat in raw.get("features", []):
        props = feat["properties"]
        ice_area_m2 = props.get("ice_area_m2") or 0.0
        rows.append(
            {
                **props,
                "ice_area_km2": float(ice_area_m2) / 1e6,
            }
        )
    return rows


def compute_areas_for_glacier_batch(
    gdf,
    years,
    season_months,
    ndsi_threshold=0.40,
    batch_size=200,
    cache_path=None,
    progress_callback=None,
):
    """Compute glacier areas for many glaciers across many years.

    Splits into batches to stay under GEE getInfo limits, with optional
    caching of intermediate results.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Glacier polygons. Must have 'glac_id' column.
    years : list of int
    season_months : list of int
    ndsi_threshold : float
    batch_size : int
        Glaciers per GEE call. 200 keeps comfortably under the limit.
    cache_path : Path, optional
        Where to incrementally save results. Allows interrupted runs.
    progress_callback : callable, optional
        Called with (year_idx, year, batch_idx, n_batches) for progress.

    Returns
    -------
    pandas.DataFrame
        Long format: one row per (glacier, year) with ice_area_km2.
    """
    ee = _get_ee()

    # Convert GeoDataFrame to GEE FeatureCollection
    print(f"  Converting {len(gdf)} glaciers to GEE features...")
    features_all = _gdf_to_ee_features(gdf)

    n = len(features_all)
    n_batches = (n + batch_size - 1) // batch_size
    print(f"  {n} glaciers in {n_batches} batches of {batch_size}")

    # Resume from cache if present
    existing = pd.DataFrame()
    if cache_path and Path(cache_path).exists():
        existing = pd.read_csv(cache_path)
        print(f"  Resuming from cache: {len(existing)} (glacier, year) entries already done")

    done_keys = set()
    if not existing.empty and {"glac_id", "year"} <= set(existing.columns):
        done_keys = set(zip(existing["glac_id"], existing["year"], strict=False))

    all_rows = list(existing.to_dict("records")) if not existing.empty else []

    for yi, year in enumerate(years):
        print(f"\n  Year {year} ({yi + 1}/{len(years)})")
        for bi in range(n_batches):
            batch = features_all[bi * batch_size : (bi + 1) * batch_size]
            # Skip batches where every glacier-year is already done
            if all((f["properties"]["glac_id"], year) in done_keys for f in batch):
                continue

            t0 = time.time()
            try:
                fc = ee.FeatureCollection(batch)
                rows = compute_glacier_areas_for_year(fc, year, season_months, ndsi_threshold)
                for r in rows:
                    r["year"] = year
                all_rows.extend(rows)

                # Incremental save
                if cache_path:
                    pd.DataFrame(all_rows).to_csv(cache_path, index=False)

                elapsed = time.time() - t0
                print(f"    batch {bi + 1}/{n_batches}: {len(rows)} glaciers in {elapsed:.1f}s")
                if progress_callback:
                    progress_callback(yi, year, bi, n_batches)
            except Exception as exc:
                print(f"    batch {bi + 1}/{n_batches} FAILED: {exc}")

    df = pd.DataFrame(all_rows)
    return df


def _gdf_to_ee_features(gdf):
    """Convert a GeoDataFrame to a list of GEE Feature dicts.

    We work with raw dicts (not ee.Feature objects) so we can build
    FeatureCollections from arbitrary subsets without round-tripping
    through GEE for each feature.
    """
    from shapely.geometry import mapping

    features = []
    for _, row in gdf.iterrows():
        geom = mapping(row.geometry)
        props = {k: row[k] for k in row.index if k != "geometry" and pd.notna(row[k])}
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return features


def build_area_matrix(long_df):
    """Pivot a long-format result DataFrame into a glacier x year matrix.

    Parameters
    ----------
    long_df : DataFrame
        From compute_areas_for_glacier_batch. Long format.

    Returns
    -------
    pandas.DataFrame
        Wide format indexed by glac_id with columns for each year.
    """
    return long_df.pivot_table(
        index="glac_id", columns="year", values="ice_area_km2", aggfunc="first"
    )
