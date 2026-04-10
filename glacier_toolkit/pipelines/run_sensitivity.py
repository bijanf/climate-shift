#!/usr/bin/env python3
"""
Sensitivity analysis pipeline for the climate-glacier coupling paper.

Sweeps across reasonable methodology choices and reports how the central
finding (land-terminating Spearman ρ) varies. Generates a sensitivity
table (CSV + LaTeX) and a forest-plot figure.

Usage:
    python -m glacier_toolkit.pipelines.run_sensitivity
    glacier-sensitivity
"""

from __future__ import annotations

import json


def main():
    from glacier_toolkit.acquire.glims_gee import fetch_glims_for_glacier
    from glacier_toolkit.analyze.sensitivity import (
        define_sensitivity_grid,
        run_sensitivity_sweep,
        summarize_robustness,
    )
    from glacier_toolkit.config import GLACIER_REGISTRY, LANDSAT_DIR, PAPER_OUT_DIR
    from glacier_toolkit.visualize.paper_figures import figure_sensitivity_forest

    print("\n" + "=" * 70)
    print("  SENSITIVITY ANALYSIS — climate-glacier coupling paper")
    print("=" * 70 + "\n")

    # ── Load all glaciers with cached NDSI files ──
    print("Loading cached NDSI files for all glaciers ...")
    glaciers_with_files = []
    for key, glacier in GLACIER_REGISTRY.items():
        glacier = {**glacier, "key": key}
        safe_name = glacier["name"].replace(" ", "_").replace("/", "-").lower()
        ndsi_dir = LANDSAT_DIR / safe_name
        ndsi_files = {}
        if ndsi_dir.exists():
            for f in sorted(ndsi_dir.glob("ndsi_*.tif")):
                try:
                    year = int(f.stem.split("_")[-1])
                    ndsi_files[year] = f
                except ValueError:
                    pass
        if ndsi_files:
            glaciers_with_files.append((glacier, ndsi_files))

    print(f"  {len(glaciers_with_files)} glaciers with cached data")

    # ── Pre-fetch all GLIMS polygons ──
    print("\nPre-fetching GLIMS polygons (cached) ...")
    polygon_cache = {}
    for glacier, _ in glaciers_with_files:
        try:
            polygon_cache[glacier["key"]] = fetch_glims_for_glacier(glacier)
        except Exception as exc:
            print(f"  Warning: GLIMS fetch failed for {glacier['name']}: {exc}")
            polygon_cache[glacier["key"]] = None

    # ── Define and run the sensitivity sweep ──
    print("\nRunning sensitivity sweep across all variants:")
    variants = define_sensitivity_grid()
    print(f"  {len(variants)} variants defined")
    print()

    sensitivity_df = run_sensitivity_sweep(glaciers_with_files, polygon_cache, variants)

    # ── Print results table ──
    print("\n" + "=" * 70)
    print("  SENSITIVITY RESULTS — Land-terminating glaciers")
    print("=" * 70)
    display_cols = [
        "name",
        "n_land",
        "spearman_rho_land",
        "spearman_p_land",
        "pearson_r_land",
        "r_squared_land",
    ]
    print(sensitivity_df[display_cols].to_string(index=False))

    # ── Robustness summary ──
    summary = summarize_robustness(sensitivity_df)
    print(f"\n{'=' * 70}")
    print("  ROBUSTNESS SUMMARY (land-terminating Spearman ρ)")
    print(f"{'=' * 70}")
    print(f"  Variants tested:      {summary['n_variants']}")
    print(
        f"  ρ range:              [{summary['rho_min']:+.3f}, {summary['rho_max']:+.3f}], "
        f"mean = {summary['rho_mean']:+.3f}"
    )
    print(f"  Max p-value:          {summary['p_max']:.4f}")
    print(f"  Significant in all:   {summary['all_significant']}")
    print(f"  Negative sign in all: {summary['all_negative']}")

    # ── Save outputs ──
    PAPER_OUT_DIR.mkdir(parents=True, exist_ok=True)
    sens_dir = PAPER_OUT_DIR / "sensitivity"
    sens_dir.mkdir(exist_ok=True)

    sensitivity_df.to_csv(sens_dir / "sensitivity_table.csv", index=False)
    sensitivity_df.to_latex(
        sens_dir / "sensitivity_table.tex",
        index=False,
        float_format="%.3f",
        escape=False,
    )

    with open(sens_dir / "robustness_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Saved: {sens_dir / 'sensitivity_table.csv'}")
    print(f"  Saved: {sens_dir / 'sensitivity_table.tex'}")
    print(f"  Saved: {sens_dir / 'robustness_summary.json'}")

    # ── Generate figure ──
    print("\n  Generating sensitivity forest plot ...")
    try:
        figure_sensitivity_forest(sensitivity_df, filename=sens_dir / "fig4_sensitivity_forest.pdf")
    except Exception as exc:
        print(f"  Figure error: {exc}")

    print(f"\n{'=' * 70}")
    print(f"  SENSITIVITY ANALYSIS COMPLETE — output in {sens_dir}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
