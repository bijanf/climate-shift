#!/usr/bin/env python3
"""
Generate a global glacier retreat dashboard.

Analyzes all glaciers in the registry and produces a world map
showing retreat statistics for each glacier.

Usage:
  python -m glacier_toolkit.pipelines.run_global_overview
  python -m glacier_toolkit.pipelines.run_global_overview --year-start 1990 --year-end 2024
"""

import argparse
import json

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Generate global glacier retreat dashboard")
    parser.add_argument("--year-start", type=int, default=1990)
    parser.add_argument("--year-end", type=int, default=2024)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument(
        "--glaciers",
        nargs="*",
        default=None,
        help="Specific glacier keys to include (default: all)",
    )
    args = parser.parse_args()

    from glacier_toolkit.config import GLACIER_REGISTRY, GLOBAL_OUT_DIR, OUTPUTS_DIR

    keys = args.glaciers if args.glaciers else list(GLACIER_REGISTRY.keys())

    print(f"\n{'=' * 60}")
    print("  GLOBAL GLACIER RETREAT OVERVIEW")
    print(f"  Analyzing {len(keys)} glaciers across all continents")
    print(f"{'=' * 60}\n")

    glacier_stats = {}

    for i, key in enumerate(keys, 1):
        glacier = GLACIER_REGISTRY[key]
        print(f"\n[{i}/{len(keys)}] {glacier['name']} ({glacier['region']})")
        print("-" * 40)

        safe_name = glacier["name"].replace(" ", "_").replace("/", "-").lower()
        glacier_dir = OUTPUTS_DIR / safe_name

        # Check for cached results
        results_file = glacier_dir / "analysis_results.json"
        if results_file.exists() and args.skip_download:
            with open(results_file) as f:
                results = json.load(f)
            change = results.get("change", {})
            glacier_stats[key] = {
                "area_change_pct": change.get("change_pct", 0),
                "area_early_km2": change.get("baseline_area_km2", 0),
                "area_late_km2": change.get("modern_area_km2", 0),
                "year_early": change.get("baseline_year"),
                "year_late": change.get("modern_year"),
            }
            print(f"  Loaded cached results: {change.get('change_pct', 0):.1f}% change")
            continue

        # Run analysis
        try:
            from glacier_toolkit.acquire.landsat import export_timeseries
            from glacier_toolkit.analyze.glacier_area import (
                build_area_timeseries,
                compute_area_change,
            )

            if not args.skip_download:
                ndsi_files = export_timeseries(
                    glacier,
                    year_start=args.year_start,
                    year_end=args.year_end,
                    output_dir=glacier_dir / "ndsi",
                )
            else:
                ndsi_dir = glacier_dir / "ndsi"
                ndsi_files = {}
                if ndsi_dir.exists():
                    for f in sorted(ndsi_dir.glob("ndsi_*.tif")):
                        try:
                            year = int(f.stem.split("_")[-1])
                            ndsi_files[year] = f
                        except ValueError:
                            pass

            if ndsi_files:
                ts_df = build_area_timeseries(ndsi_files)
                change = compute_area_change(ts_df)
                glacier_stats[key] = {
                    "area_change_pct": change["change_pct"],
                    "area_early_km2": change["baseline_area_km2"],
                    "area_late_km2": change["modern_area_km2"],
                    "year_early": change["baseline_year"],
                    "year_late": change["modern_year"],
                }
                print(f"  Result: {change['change_pct']:.1f}% area change")
            else:
                print("  Skipped: no data available")

        except Exception as exc:
            print(f"  Error: {exc}")

    # Generate global dashboard
    if glacier_stats:
        print(f"\n{'=' * 60}")
        print("  Generating Global Dashboard")
        print(f"{'=' * 60}\n")

        from glacier_toolkit.visualize.global_dashboard import make_global_dashboard

        dashboard_path = make_global_dashboard(glacier_stats)

        # Save summary
        summary = {
            "n_glaciers": len(glacier_stats),
            "avg_change_pct": float(
                np.mean(
                    [
                        abs(s["area_change_pct"])
                        for s in glacier_stats.values()
                        if s.get("area_change_pct") is not None
                    ]
                )
            ),
            "glaciers": glacier_stats,
        }
        with open(GLOBAL_OUT_DIR / "global_summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"\n  Dashboard: {dashboard_path}")
        print(f"  Summary:   {GLOBAL_OUT_DIR / 'global_summary.json'}")
    else:
        print("\n  No glacier data available. Run individual analyses first.")

    print(f"\n{'=' * 60}")
    print("  GLOBAL OVERVIEW COMPLETE")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
