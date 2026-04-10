#!/usr/bin/env python3
"""
Global-scale paper pipeline (Path C: Nature Geoscience target).

For one or more RGI regions:
  1. Fetch all GLIMS glacier polygons in the region (cached)
  2. Filter to glaciers above min_area_km2 (e.g., 1.0 km²)
  3. De-duplicate by glac_id keeping the historical maximum extent
  4. Server-side GEE batch: compute per-glacier ice area for each year
  5. Extract local climate at each glacier centroid (CRU TS, batched per cell)
  6. Per-glacier climate-glacier coupling regression
  7. Cross-glacier regression stratified by terminus type
  8. Region-level output table + figures

This scales to ~200,000 glaciers across all 19 RGI regions.

Usage:
    glacier-global --region 11                       # Central Europe
    glacier-global --region 11 --top 100 --years 1985,1990,1995,2000,2005,2010,2015,2020,2024
    glacier-global --region 11 12 16                 # multiple regions
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Global-scale climate-glacier coupling pipeline")
    parser.add_argument(
        "--region",
        type=int,
        nargs="+",
        required=True,
        help="One or more RGI region IDs (1-19)",
    )
    parser.add_argument(
        "--min-area-km2",
        type=float,
        default=1.0,
        help="Minimum glacier area to include (km²)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Limit to top N largest glaciers per region (for testing)",
    )
    parser.add_argument(
        "--years",
        type=str,
        default="1985,1990,1995,2000,2005,2010,2015,2020,2024",
        help="Comma-separated years to compute (default: 9 sampled years)",
    )
    parser.add_argument("--ndsi-threshold", type=float, default=0.40)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    from glacier_toolkit.acquire.glims_regions import (
        RGI_REGION_NAMES,
        deduplicate_by_largest,
        fetch_region_glaciers,
    )
    from glacier_toolkit.acquire.landsat_batch import compute_areas_for_glacier_batch
    from glacier_toolkit.analyze.climate_link import (
        compute_local_warming_rate,
        extract_local_temperature,
    )
    from glacier_toolkit.analyze.correlation import cross_glacier_regression
    from glacier_toolkit.config import PAPER_OUT_DIR

    years = [int(y.strip()) for y in args.years.split(",")]

    print("\n" + "=" * 70)
    print("  GLOBAL CLIMATE-GLACIER COUPLING PIPELINE (Path C)")
    print(f"  Regions: {args.region}, years: {years[0]}-{years[-1]} (n={len(years)})")
    print("=" * 70 + "\n")

    region_dfs = []

    for region_id in args.region:
        region_name = RGI_REGION_NAMES[region_id]
        print(f"\n{'─' * 70}")
        print(f"  REGION {region_id}: {region_name}")
        print(f"{'─' * 70}\n")

        # ── Step 1: Fetch GLIMS polygons ──
        gdf = fetch_region_glaciers(region_id, min_area_km2=args.min_area_km2)
        gdf = deduplicate_by_largest(gdf)
        print(f"  {len(gdf)} unique glaciers after de-duplication")

        if args.top:
            gdf = gdf.nlargest(args.top, "db_area").reset_index(drop=True)
            print(f"  Limited to top {len(gdf)} by db_area")

        # Compute centroids
        gdf_proj = gdf.to_crs("EPSG:4326")
        gdf["centroid_lat"] = gdf_proj.geometry.centroid.y
        gdf["centroid_lon"] = gdf_proj.geometry.centroid.x

        # ── Step 2: Determine season per glacier (hemisphere-based) ──
        # For now, assume northern hemisphere summer for all NH regions and
        # SH summer for all SH regions
        if region_id in (16, 17, 18, 19):  # tropical, Patagonia, NZ, Antarctica
            if region_id == 16:
                season_months = [6, 7, 8, 9]  # tropical dry season
            else:
                season_months = [12, 1, 2]  # Southern summer
        else:
            season_months = [6, 7, 8]  # Northern summer

        print(f"  Season months: {season_months}")

        # ── Step 3: Server-side batch area computation ──
        cache_path = PAPER_OUT_DIR / f"global_areas_region_{region_id:02d}.csv"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        print("\n  Step 3: Computing per-glacier ice areas via GEE batch ...")
        t0 = time.time()
        long_df = compute_areas_for_glacier_batch(
            gdf,
            years=years,
            season_months=season_months,
            ndsi_threshold=args.ndsi_threshold,
            batch_size=args.batch_size,
            cache_path=cache_path,
        )
        elapsed = time.time() - t0
        print(
            f"\n  Batch processing complete: {len(long_df)} (glacier, year) entries in {elapsed:.0f}s"
        )

        # ── Step 4: Per-glacier trend ──
        print("\n  Step 4: Per-glacier retreat rates ...")
        per_glacier_results = []
        for glac_id, group in long_df.groupby("glac_id"):
            if len(group) < 3:
                continue
            ts = group.sort_values("year")
            from scipy import stats

            fit = stats.linregress(ts["year"].astype(float), ts["ice_area_km2"])

            # Get glacier metadata from gdf
            row = gdf[gdf["glac_id"] == glac_id]
            if row.empty:
                continue
            row = row.iloc[0]

            per_glacier_results.append(
                {
                    "glac_id": glac_id,
                    "glac_name": row.get("glac_name", "Unnamed"),
                    "glacier_region": region_name,
                    "lat": row["centroid_lat"],
                    "lon": row["centroid_lon"],
                    "db_area_km2": row["db_area"],
                    "ice_area_1990": _value_at(ts, 1990),
                    "ice_area_2024": _value_at(ts, 2024),
                    "retreat_rate_km2_per_year": fit.slope,
                    "retreat_p": fit.pvalue,
                    "retreat_r2": fit.rvalue**2,
                    "n_years": len(ts),
                    "terminus_type": "land",  # placeholder; refine later
                }
            )

        print(f"    {len(per_glacier_results)} glaciers with valid trends")

        # ── Step 5: Local climate at each glacier ──
        print("\n  Step 5: Extracting local climate (CRU TS) ...")

        # Group glaciers by CRU TS cell to avoid redundant extractions
        for r in per_glacier_results:
            try:
                temp_df = extract_local_temperature(
                    lat=r["lat"],
                    lon=r["lon"],
                    season=season_months,
                    year_start=years[0],
                    year_end=years[-1],
                )
                warming = compute_local_warming_rate(temp_df)
                r["warming_rate_c_per_decade"] = warming["slope_c_per_decade"]
                r["warming_p"] = warming["p_value"]
            except Exception as exc:
                print(f"    Climate extraction failed for {r['glac_name']}: {exc}")
                r["warming_rate_c_per_decade"] = np.nan
                r["warming_p"] = np.nan

        # ── Step 6: Cross-glacier regression ──
        print("\n  Step 6: Cross-glacier regression ...")
        cross_all = cross_glacier_regression(per_glacier_results)
        cross_land = cross_glacier_regression(per_glacier_results, terminus_filter="land")

        print(f"\n  ALL glaciers in region (n={cross_all['n_glaciers']}):")
        if cross_all["n_glaciers"] >= 3:
            print(f"    Pearson r:  {cross_all['pearson_r']:+.3f} (p={cross_all['pearson_p']:.4f})")
            print(
                f"    Spearman ρ: {cross_all['spearman_r']:+.3f} (p={cross_all['spearman_p']:.4f})"
            )
            print(f"    Slope:      {cross_all['regression_slope']:+.3f} km²/yr per °C/decade")

        # ── Step 7: Save region results ──
        region_df = pd.DataFrame(per_glacier_results)
        region_df["region_id"] = region_id
        out_csv = PAPER_OUT_DIR / f"global_results_region_{region_id:02d}.csv"
        region_df.to_csv(out_csv, index=False)
        print(f"\n  Saved: {out_csv}")
        region_dfs.append(region_df)

        # Save region summary JSON
        summary = {
            "region_id": region_id,
            "region_name": region_name,
            "n_glaciers": len(per_glacier_results),
            "years": years,
            "n_years": len(years),
            "season_months": season_months,
            "cross_all": {
                k: (
                    float(v)
                    if isinstance(v, (np.floating, float, int)) and not isinstance(v, bool)
                    else v
                )
                for k, v in cross_all.items()
            },
            "cross_land": {
                k: (
                    float(v)
                    if isinstance(v, (np.floating, float, int)) and not isinstance(v, bool)
                    else v
                )
                for k, v in cross_land.items()
            },
        }
        with open(PAPER_OUT_DIR / f"global_summary_region_{region_id:02d}.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)

    # ── Combine all regions ──
    if region_dfs:
        combined = pd.concat(region_dfs, ignore_index=True)
        combined.to_csv(PAPER_OUT_DIR / "global_results_combined.csv", index=False)
        print(f"\n{'=' * 70}")
        print(f"  COMBINED RESULTS: {len(combined)} glaciers across {len(region_dfs)} regions")
        print(f"{'=' * 70}")

        # Final cross-glacier regression on combined dataset
        from glacier_toolkit.analyze.correlation import cross_glacier_regression

        all_results = combined.to_dict("records")
        cross = cross_glacier_regression(all_results)
        print(f"\n  Combined cross-glacier regression (n={cross['n_glaciers']}):")
        if cross["n_glaciers"] >= 3:
            print(f"    Pearson r:  {cross['pearson_r']:+.3f} (p={cross['pearson_p']:.4g})")
            print(f"    Spearman ρ: {cross['spearman_r']:+.3f} (p={cross['spearman_p']:.4g})")

    print(f"\n{'=' * 70}")
    print("  GLOBAL PIPELINE COMPLETE")
    print(f"{'=' * 70}\n")


def _value_at(ts_df, year):
    """Get the ice_area_km2 at a specific year, or NaN."""
    row = ts_df[ts_df["year"] == year]
    if row.empty:
        return float("nan")
    return float(row.iloc[0]["ice_area_km2"])


if __name__ == "__main__":
    main()
