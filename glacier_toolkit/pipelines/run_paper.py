#!/usr/bin/env python3
"""
End-to-end paper pipeline for the climate-glacier coupling study.

For each glacier in the registry:
  1. Load cached glacier area time series (or compute from NDSI files)
  2. Extract local CRU TS temperature time series
  3. Compute climate-glacier correlation and sensitivity
  4. Compare to published reference if available

Then aggregate:
  5. Cross-glacier regression (warming rate vs retreat rate)
  6. Per-region summary
  7. GLIMS validation table
  8. Generate paper figures
  9. Output JSON, CSV, and LaTeX results

Usage:
    python -m glacier_toolkit.pipelines.run_paper
    python -m glacier_toolkit.pipelines.run_paper --glaciers aletsch columbia gangotri
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end paper pipeline: climate-glacier coupling analysis"
    )
    parser.add_argument(
        "--glaciers",
        nargs="*",
        default=None,
        help="Specific glacier keys (default: all in registry)",
    )
    parser.add_argument("--year-start", type=int, default=1985)
    parser.add_argument("--year-end", type=int, default=2024)
    parser.add_argument(
        "--require-cached",
        action="store_true",
        help="Skip glaciers without cached NDSI files (don't trigger downloads)",
    )
    args = parser.parse_args()

    from glacier_toolkit.analyze.climate_link import (
        compute_local_warming_rate,
        get_glacier_climate,
    )
    from glacier_toolkit.analyze.correlation import (
        build_results_table,
        compute_climate_sensitivity,
        cross_glacier_regression,
        per_region_summary,
    )
    from glacier_toolkit.analyze.glacier_area import (
        build_area_timeseries,
        compute_area_change,
        fit_linear_trend,
    )
    from glacier_toolkit.config import GLACIER_REGISTRY, LANDSAT_DIR, PAPER_OUT_DIR
    from glacier_toolkit.validate.glims_validation import (
        get_published_reference,
        validate_against_references,
    )
    from glacier_toolkit.visualize.paper_figures import (
        figure_glacier_time_series_grid,
        figure_warming_vs_retreat_scatter,
        figure_world_map,
    )

    keys = args.glaciers if args.glaciers else list(GLACIER_REGISTRY.keys())

    print(f"\n{'=' * 70}")
    print("  PAPER PIPELINE: Climate-Glacier Coupling Analysis")
    print(f"  Glaciers: {len(keys)}, Years: {args.year_start}-{args.year_end}")
    print(f"{'=' * 70}\n")

    per_glacier_results = []
    validation_records = []

    for i, key in enumerate(keys, 1):
        glacier = GLACIER_REGISTRY[key]
        print(f"[{i}/{len(keys)}] {glacier['name']} ({glacier['region']})")

        # ── Load cached NDSI files ──
        safe_name = glacier["name"].replace(" ", "_").replace("/", "-").lower()
        ndsi_dir = LANDSAT_DIR / safe_name
        ndsi_files = {}
        if ndsi_dir.exists():
            for f in sorted(ndsi_dir.glob("ndsi_*.tif")):
                try:
                    year = int(f.stem.split("_")[-1])
                    if args.year_start <= year <= args.year_end:
                        ndsi_files[year] = f
                except ValueError:
                    pass

        if not ndsi_files:
            print(f"  Skip: no cached NDSI files in {ndsi_dir}")
            if args.require_cached:
                continue

        # ── Glacier area time series ──
        if ndsi_files:
            try:
                ts_df = build_area_timeseries(ndsi_files)
                change = compute_area_change(ts_df)
                trend = fit_linear_trend(ts_df)
                area_change_pct = change["change_pct"]
                retreat_rate = trend["slope_km2_per_year"]
                print(
                    f"  Area: {len(ts_df)} years, Δ={area_change_pct:+.1f}%, "
                    f"trend={retreat_rate:+.3f} km²/yr"
                )
            except Exception as exc:
                print(f"  Error in area analysis: {exc}")
                continue
        else:
            ts_df = pd.DataFrame()
            area_change_pct = np.nan
            retreat_rate = np.nan

        # ── Local climate ──
        try:
            temp_df = get_glacier_climate(glacier, args.year_start, args.year_end)
            warming = compute_local_warming_rate(temp_df)
            warming_rate = warming["slope_c_per_decade"]
            print(f"  Climate: warming={warming_rate:+.3f} °C/dec (p={warming['p_value']:.3f})")
        except Exception as exc:
            print(f"  Error in climate extraction: {exc}")
            continue

        # ── Climate-glacier sensitivity ──
        if len(ts_df) >= 5:
            sensitivity = compute_climate_sensitivity(ts_df, temp_df)
            sens_val = sensitivity["sensitivity_km2_per_c"]
            sens_p = sensitivity["p_value"]
            print(
                f"  Sensitivity: {sens_val:+.2f} km²/°C "
                f"(R²={sensitivity['r_squared']:.2f}, p={sens_p:.3f})"
            )
        else:
            sensitivity = {
                "sensitivity_km2_per_c": np.nan,
                "r_squared": np.nan,
                "p_value": np.nan,
                "ci_lower": np.nan,
                "ci_upper": np.nan,
            }

        # ── GLIMS validation if reference is available ──
        ref = get_published_reference(key)
        if ref and len(ts_df) > 0:
            ref_year = ref["reference_year"]
            our_row = ts_df[ts_df["year"] == ref_year]
            if not our_row.empty:
                validation_records.append(
                    {
                        "name": glacier["name"],
                        "computed_km2": float(our_row.iloc[0]["area_km2"]),
                        "reference_km2": ref["reference_km2"],
                        "reference_year": ref_year,
                        "reference_source": ref["reference_source"],
                    }
                )

        # ── Compile per-glacier result ──
        per_glacier_results.append(
            {
                "key": key,
                "glacier_name": glacier["name"],
                "glacier_region": glacier["region"],
                "lat": glacier["lat"],
                "lon": glacier["lon"],
                "year_start": args.year_start,
                "year_end": args.year_end,
                "n_years_satellite": len(ts_df),
                "n_years_climate": warming["n_years"],
                "area_change_pct": area_change_pct,
                "retreat_rate_km2_per_year": retreat_rate,
                "warming_rate_c_per_decade": warming_rate,
                "warming_p_value": warming["p_value"],
                "sensitivity_km2_per_c": sensitivity["sensitivity_km2_per_c"],
                "sensitivity_r_squared": sensitivity["r_squared"],
                "sensitivity_p_value": sensitivity["p_value"],
                "sensitivity_ci_lower": sensitivity["ci_lower"],
                "sensitivity_ci_upper": sensitivity["ci_upper"],
                "time_series": ts_df,  # for figures
            }
        )

    if not per_glacier_results:
        print("\n  No usable data. Run the data pipeline first.")
        return

    # ── Cross-glacier regression ──
    print(f"\n{'=' * 70}")
    print("  Cross-glacier regression (warming rate vs retreat rate)")
    print(f"{'=' * 70}")

    cross = cross_glacier_regression(per_glacier_results)
    print(f"  N glaciers: {cross['n_glaciers']}")
    print(f"  Pearson r:  {cross['pearson_r']:+.3f} (p={cross['pearson_p']:.4f})")
    print(f"  Spearman ρ: {cross['spearman_r']:+.3f} (p={cross['spearman_p']:.4f})")
    print(f"  Slope:      {cross['regression_slope']:+.3f} km²/yr per °C/decade")
    print(f"  R²:         {cross['r_squared']:.3f}")

    # ── Per-region summary ──
    region_df = per_region_summary(per_glacier_results)
    print("\n  Per-region summary:")
    if not region_df.empty:
        print(region_df.to_string(index=False))

    # ── GLIMS validation ──
    if validation_records:
        print(f"\n{'=' * 70}")
        print("  GLIMS validation")
        print(f"{'=' * 70}")
        val = validate_against_references(validation_records)
        print(f"  N references:       {val['n_glaciers']}")
        print(
            f"  Mean bias:          {val['mean_bias_km2']:+.2f} km² ({val['mean_bias_pct']:+.1f}%)"
        )
        print(f"  RMSE:               {val['rmse_km2']:.2f} km²")
        print(f"  Mean abs error:     {val['mean_absolute_error_pct']:.1f}%")
        print(f"  Max error:          {val['max_error_pct']:.1f}%")

    # ── Save outputs ──
    print(f"\n{'=' * 70}")
    print("  Saving paper outputs")
    print(f"{'=' * 70}")

    # Strip non-serializable time series before JSON dump
    serializable = []
    for r in per_glacier_results:
        out = {k: v for k, v in r.items() if k != "time_series"}
        serializable.append(out)

    PAPER_OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(PAPER_OUT_DIR / "results.json", "w") as f:
        json.dump(
            {
                "per_glacier": serializable,
                "cross_glacier_regression": cross,
                "validation": (
                    {k: v for k, v in val.items() if k != "per_glacier"}
                    if validation_records
                    else None
                ),
            },
            f,
            indent=2,
            default=str,
        )
    print("  Saved: results.json")

    # Results table
    table = build_results_table(per_glacier_results)
    table.to_csv(PAPER_OUT_DIR / "results_table.csv", index=False)
    table.to_latex(PAPER_OUT_DIR / "results_table.tex", index=False, escape=False)
    print("  Saved: results_table.csv + results_table.tex")

    # Region summary
    if not region_df.empty:
        region_df.to_csv(PAPER_OUT_DIR / "region_summary.csv", index=False)
        print("  Saved: region_summary.csv")

    # Validation table
    if validation_records:
        val["per_glacier"].to_csv(PAPER_OUT_DIR / "validation_table.csv", index=False)
        print("  Saved: validation_table.csv")

    # ── Figures ──
    print("\n  Generating paper figures...")
    try:
        figure_glacier_time_series_grid(per_glacier_results)
    except Exception as exc:
        print(f"  Figure 1 error: {exc}")

    try:
        figure_warming_vs_retreat_scatter(per_glacier_results, cross)
    except Exception as exc:
        print(f"  Figure 2 error: {exc}")

    try:
        figure_world_map(per_glacier_results)
    except Exception as exc:
        print(f"  Figure 3 error: {exc}")

    print(f"\n{'=' * 70}")
    print(f"  PAPER PIPELINE COMPLETE — output in {PAPER_OUT_DIR}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
