#!/usr/bin/env python3
"""
Analyze ANY glacier by name or coordinates.

Usage:
  python -m glacier_toolkit.pipelines.run_single_glacier --name "Aletsch"
  python -m glacier_toolkit.pipelines.run_single_glacier --lat 30.9 --lon 79.1 --glacier-name "Gangotri"
  python -m glacier_toolkit.pipelines.run_single_glacier --name "columbia" --year-start 1985 --year-end 2024

Produces:
  - NDSI GeoTIFFs for each year
  - Glacier area time series (CSV)
  - Trend analysis with bootstrap CIs
  - Ghost Ice slide (Instagram-ready)
  - Before/After comparison slide
  - Time series chart slide
  - Methodology slide
  - Auto-generated Instagram caption
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Analyze glacier retreat from satellite imagery"
    )
    parser.add_argument("--name", type=str,
                        help="Glacier registry key (e.g. 'aletsch', 'columbia')")
    parser.add_argument("--lat", type=float, help="Latitude for custom location")
    parser.add_argument("--lon", type=float, help="Longitude for custom location")
    parser.add_argument("--glacier-name", type=str, default="Custom Glacier",
                        help="Display name for custom location")
    parser.add_argument("--year-start", type=int, default=1985)
    parser.add_argument("--year-end", type=int, default=2024)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip satellite data download (use cached)")
    parser.add_argument("--ndsi-threshold", type=float, default=0.4)

    args = parser.parse_args()

    # ── Resolve glacier config ──
    from glacier_toolkit.config import get_glacier, make_custom_glacier, OUTPUTS_DIR

    if args.name:
        glacier = get_glacier(args.name)
        print(f"\n{'='*60}")
        print(f"  GLACIER RETREAT ANALYSIS: {glacier['name']}")
        print(f"  Region: {glacier['region']}")
        print(f"{'='*60}\n")
    elif args.lat is not None and args.lon is not None:
        glacier = make_custom_glacier(args.glacier_name, args.lat, args.lon)
        print(f"\n{'='*60}")
        print(f"  GLACIER RETREAT ANALYSIS: {glacier['name']}")
        print(f"  Location: {args.lat:.2f}°, {args.lon:.2f}°")
        print(f"{'='*60}\n")
    else:
        parser.error("Provide --name OR (--lat and --lon)")
        return

    safe_name = glacier["name"].replace(" ", "_").replace("/", "-").lower()
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUTS_DIR / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Download satellite data ──
    print("Step 1: Satellite Data Acquisition")
    print("-" * 40)

    if not args.skip_download:
        from glacier_toolkit.acquire.landsat import export_timeseries
        ndsi_files = export_timeseries(
            glacier,
            year_start=args.year_start,
            year_end=args.year_end,
            output_dir=output_dir / "ndsi",
        )
    else:
        # Load cached files
        ndsi_dir = output_dir / "ndsi"
        ndsi_files = {}
        if ndsi_dir.exists():
            for f in sorted(ndsi_dir.glob("ndsi_*.tif")):
                try:
                    year = int(f.stem.split("_")[-1])
                    ndsi_files[year] = f
                except ValueError:
                    pass
        print(f"  Found {len(ndsi_files)} cached NDSI files")

    if not ndsi_files:
        print("  ERROR: No NDSI data available. Run without --skip-download first.")
        return

    # ── Step 2: Compute area time series ──
    print(f"\nStep 2: Computing Glacier Area Time Series")
    print("-" * 40)

    from glacier_toolkit.analyze.glacier_area import (
        build_area_timeseries, compute_area_change, fit_linear_trend,
        detect_acceleration,
    )

    ts_df = build_area_timeseries(ndsi_files, threshold=args.ndsi_threshold)
    ts_df.to_csv(output_dir / "area_timeseries.csv", index=False)
    print(f"  Time series: {len(ts_df)} years")
    print(f"  Saved: area_timeseries.csv")

    # Area change
    change = compute_area_change(ts_df)
    print(f"\n  Area change:")
    print(f"    {change['baseline_year']}: {change['baseline_area_km2']:.2f} km²")
    print(f"    {change['modern_year']}:  {change['modern_area_km2']:.2f} km²")
    print(f"    Change: {change['change_km2']:.2f} km² ({change['change_pct']:.1f}%)")

    # Trend analysis
    trend = fit_linear_trend(ts_df)
    print(f"\n  Linear trend: {trend['slope_km2_per_year']:.4f} km²/year")
    print(f"    95% CI: [{trend['ci_lower']:.4f}, {trend['ci_upper']:.4f}]")
    print(f"    R²: {trend['r_squared']:.3f}")
    print(f"    Mann-Kendall: {trend['mk_trend']} (p={trend['mk_p_value']:.4f})")

    # Acceleration test
    accel = detect_acceleration(ts_df)
    if accel["is_accelerating"] is not None:
        print(f"\n  Acceleration test (breakpoint {accel['breakpoint_year']}):")
        print(f"    Early slope: {accel['early_slope']:.4f} km²/yr")
        print(f"    Late slope:  {accel['late_slope']:.4f} km²/yr")
        print(f"    Accelerating: {accel['is_accelerating']}")

    # Save results
    results = {
        "glacier": glacier["name"],
        "region": glacier["region"],
        "change": change,
        "trend": {k: float(v) if isinstance(v, (np.floating, float)) else v
                  for k, v in trend.items()},
        "acceleration": {k: float(v) if isinstance(v, (np.floating, float)) else v
                         for k, v in accel.items()},
    }
    with open(output_dir / "analysis_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: analysis_results.json")

    # ── Step 3: Generate visualizations ──
    print(f"\nStep 3: Generating Visualizations")
    print("-" * 40)

    # Load earliest and latest NDSI for masks
    from glacier_toolkit.analyze.ndsi import load_ndsi_geotiff, classify_glacier

    years_available = sorted(ndsi_files.keys())
    early_year = years_available[0]
    late_year = years_available[-1]

    early_ndsi = load_ndsi_geotiff(ndsi_files[early_year])
    late_ndsi = load_ndsi_geotiff(ndsi_files[late_year])
    early_mask = classify_glacier(early_ndsi, threshold=args.ndsi_threshold)
    late_mask = classify_glacier(late_ndsi, threshold=args.ndsi_threshold)

    bbox = glacier["bbox"]
    extent = (bbox[0], bbox[2], bbox[1], bbox[3])  # (left, right, bottom, top)

    # Slide 1: Ghost Ice
    from glacier_toolkit.visualize.ghost_ice import make_ghost_ice_slide
    make_ghost_ice_slide(
        modern_rgb=None,  # Would need RGB export; using mask-only mode
        historical_mask=early_mask,
        modern_mask=late_mask,
        glacier_name=glacier["name"],
        year_early=early_year,
        year_late=late_year,
        area_early_km2=change["baseline_area_km2"],
        area_late_km2=change["modern_area_km2"],
        extent=extent,
        slide_num=1, total_slides=4,
    )

    # Slide 2: Comparison
    from glacier_toolkit.visualize.comparison_maps import make_comparison_slide
    make_comparison_slide(
        early_rgb=None,
        late_rgb=None,
        early_mask=early_mask,
        late_mask=late_mask,
        glacier_name=glacier["name"],
        year_early=early_year,
        year_late=late_year,
        area_early_km2=change["baseline_area_km2"],
        area_late_km2=change["modern_area_km2"],
        extent=extent,
        slide_num=2, total_slides=4,
    )

    # Slide 3: Time series chart
    from glacier_toolkit.visualize.carousel import (
        make_timeseries_slide, make_methodology_slide, generate_caption,
    )
    make_timeseries_slide(ts_df, trend, glacier["name"])

    # Slide 4: Methodology
    make_methodology_slide(glacier["name"], {
        "baseline_year": change["baseline_year"],
        "modern_year": change["modern_year"],
    })

    # ── Step 4: Generate caption ──
    print(f"\nStep 4: Instagram Caption")
    print("-" * 40)

    caption = generate_caption(glacier["name"], {
        "area_change_pct": change["change_pct"],
        "area_change_km2": change["change_km2"],
        "baseline_year": change["baseline_year"],
        "modern_year": change["modern_year"],
        "slope_km2_per_year": trend["slope_km2_per_year"],
    })

    caption_path = output_dir / "instagram_caption.txt"
    with open(caption_path, "w") as f:
        f.write(caption)
    print(f"  Saved: {caption_path}")
    print(f"\n  Caption preview:\n")
    print("  " + caption[:300].replace("\n", "\n  ") + "...")

    print(f"\n{'='*60}")
    print(f"  ANALYSIS COMPLETE: {glacier['name']}")
    print(f"  Output directory: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
