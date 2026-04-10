"""
Scale-aware paper figures for the Phase 2 (Nature Geoscience) analysis.

These figures are designed for hundreds to thousands of glaciers,
not the per-glacier panels of Phase 1. They use density visualizations
(hexbins, KDEs), regional aggregations (boxplots), and global maps with
markers.

All figures follow the publication-quality style from paper_figures.py
(white background, 300 DPI, PDF + PNG output).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from ..config import PAPER_OUT_DIR
from .paper_figures import _save_paper_fig, apply_paper_style

# ══════════════════════════════════════════════════════════════════════════════
# Figure 5: Per-region warming-vs-retreat scatter grid
# ══════════════════════════════════════════════════════════════════════════════


def figure_per_region_scatter_grid(combined_df, filename=None):
    """Multi-panel scatter showing the climate-glacier relationship in each region.

    Reveals the regional heterogeneity that's hidden in global averages.

    Parameters
    ----------
    combined_df : pandas.DataFrame
        From global_results_combined.csv. Must have columns:
        warming_rate_c_per_decade, retreat_rate_km2_per_year, glacier_region.
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()

    valid = combined_df.dropna(
        subset=["warming_rate_c_per_decade", "retreat_rate_km2_per_year", "glacier_region"]
    )
    regions = sorted(valid["glacier_region"].unique())
    n = len(regions)
    n_cols = min(3, n)
    n_rows = int(np.ceil(n / n_cols))

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(n_cols * 3.5, n_rows * 3.0),
        squeeze=False,
    )
    axes = axes.flatten()

    for ax, region in zip(axes, regions, strict=False):
        g = valid[valid["glacier_region"] == region]
        warming = g["warming_rate_c_per_decade"].values
        retreat = g["retreat_rate_km2_per_year"].values

        # Scatter, sized by db_area_km2 if available
        if "db_area_km2" in g.columns:
            sizes = np.clip(np.log10(g["db_area_km2"].values + 1) * 20, 5, 100)
        else:
            sizes = 25

        ax.scatter(
            warming,
            retreat,
            s=sizes,
            c="#1976D2",
            alpha=0.5,
            edgecolors="white",
            linewidths=0.4,
            zorder=3,
        )

        # Regression line + Spearman annotation
        if len(g) >= 5:
            sr, sp = stats.spearmanr(warming, retreat)
            fit = stats.linregress(warming, retreat)
            x_line = np.array([warming.min(), warming.max()])
            y_line = fit.intercept + fit.slope * x_line
            ax.plot(x_line, y_line, color="#222222", lw=1.0, ls="--", zorder=2)

            sig_marker = "*" if sp < 0.05 else ""
            ax.text(
                0.02,
                0.97,
                f"n={len(g)}\nρ={sr:+.2f}{sig_marker}\np={sp:.3f}",
                transform=ax.transAxes,
                fontsize=7,
                color="#444444",
                va="top",
                ha="left",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="none"),
            )

        ax.axhline(0, color="#888888", lw=0.4, ls=":", zorder=1)
        ax.set_title(region, fontsize=9, fontweight="bold", pad=4)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, lw=0.3)

    # Hide unused axes
    for ax in axes[n:]:
        ax.set_visible(False)

    fig.supxlabel("Local warming rate (°C/decade)", fontsize=10)
    fig.supylabel("Glacier area trend (km²/year)", fontsize=10)
    fig.suptitle(
        "Climate-glacier coupling varies dramatically by region (Phase 2)",
        fontsize=11,
        fontweight="bold",
        y=1.00,
    )
    fig.tight_layout()

    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig5_per_region_scatter_grid.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 6: Cross-region pooled scatter with regression
# ══════════════════════════════════════════════════════════════════════════════


def figure_cross_region_combined(combined_df, filename=None):
    """Single-panel scatter pooling all regions.

    The headline figure for the Phase 2 paper. Shows that across the
    global warming gradient (when we span enough regions to get a wide
    x-axis range), faster-warming areas have faster-retreating glaciers.

    Each glacier is colored by its region, with the cross-region OLS
    fit overlaid.

    Parameters
    ----------
    combined_df : pandas.DataFrame
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()

    valid = combined_df.dropna(subset=["warming_rate_c_per_decade", "retreat_rate_km2_per_year"])
    regions = sorted(valid["glacier_region"].unique())
    cmap = plt.get_cmap("tab10")
    region_colors = {r: cmap(i % 10) for i, r in enumerate(regions)}

    fig, ax = plt.subplots(figsize=(8, 5.5))

    for region in regions:
        g = valid[valid["glacier_region"] == region]
        ax.scatter(
            g["warming_rate_c_per_decade"],
            g["retreat_rate_km2_per_year"],
            c=[region_colors[region]],
            s=30,
            alpha=0.6,
            edgecolors="white",
            linewidths=0.4,
            label=f"{region} (n={len(g)})",
            zorder=3,
        )

    # Pooled cross-region regression
    warming = valid["warming_rate_c_per_decade"].values
    retreat = valid["retreat_rate_km2_per_year"].values
    fit = stats.linregress(warming, retreat)
    sr, sp = stats.spearmanr(warming, retreat)
    pr, pp = stats.pearsonr(warming, retreat)

    x_line = np.array([warming.min(), warming.max()])
    y_line = fit.intercept + fit.slope * x_line
    ax.plot(
        x_line,
        y_line,
        color="#222222",
        lw=2.0,
        ls="--",
        zorder=4,
        label=f"Pooled OLS: slope={fit.slope:+.3f}, R²={fit.rvalue**2:.3f}",
    )

    # Headline statistics box
    stats_text = (
        f"Pooled n = {len(valid)}\n"
        f"Spearman ρ = {sr:+.3f}\n"
        f"Spearman p = {sp:.2g}\n"
        f"Pearson r = {pr:+.3f}\n"
        f"Pearson p = {pp:.2g}"
    )
    ax.text(
        0.98,
        0.97,
        stats_text,
        transform=ax.transAxes,
        fontsize=9,
        color="#222222",
        va="top",
        ha="right",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor="#888888"),
    )

    ax.axhline(0, color="#888888", lw=0.5, ls=":", zorder=1)
    ax.axvline(0, color="#888888", lw=0.5, ls=":", zorder=1)
    ax.set_xlabel("Local warming rate (°C/decade, JJA Tmax from CRU TS v4.09)")
    ax.set_ylabel("Glacier area trend (km²/year)")
    ax.set_title(
        "Phase 2: cross-region climate-glacier coupling",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )
    ax.legend(loc="lower left", fontsize=7, framealpha=0.95, ncol=1)
    ax.grid(True, alpha=0.3, lw=0.4)

    fig.tight_layout()
    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig6_cross_region_combined.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 7: Regional summary boxplots
# ══════════════════════════════════════════════════════════════════════════════


def figure_regional_boxplots(combined_df, filename=None):
    """Side-by-side boxplots: warming rate distribution per region + retreat rate.

    Parameters
    ----------
    combined_df : pandas.DataFrame
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()

    valid = combined_df.dropna(
        subset=["warming_rate_c_per_decade", "retreat_rate_km2_per_year", "glacier_region"]
    )
    regions = sorted(valid["glacier_region"].unique())

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    ax_w, ax_r = axes

    # Warming rate boxplot
    warming_data = [
        valid[valid["glacier_region"] == r]["warming_rate_c_per_decade"].values for r in regions
    ]
    bp1 = ax_w.boxplot(
        warming_data,
        tick_labels=regions,
        patch_artist=True,
        widths=0.6,
        medianprops=dict(color="#222222", linewidth=1.2),
    )
    cmap = plt.get_cmap("tab10")
    for i, patch in enumerate(bp1["boxes"]):
        patch.set_facecolor(cmap(i % 10))
        patch.set_alpha(0.6)
    ax_w.axhline(0, color="#888888", lw=0.5, ls=":")
    ax_w.set_ylabel("Local warming rate (°C/decade)")
    ax_w.set_title("(a) Local warming rates by region", fontsize=10, pad=6)
    ax_w.tick_params(axis="x", rotation=30, labelsize=7)
    ax_w.grid(True, axis="y", alpha=0.3, lw=0.3)

    # Retreat rate boxplot
    retreat_data = [
        valid[valid["glacier_region"] == r]["retreat_rate_km2_per_year"].values for r in regions
    ]
    bp2 = ax_r.boxplot(
        retreat_data,
        tick_labels=regions,
        patch_artist=True,
        widths=0.6,
        medianprops=dict(color="#222222", linewidth=1.2),
    )
    for i, patch in enumerate(bp2["boxes"]):
        patch.set_facecolor(cmap(i % 10))
        patch.set_alpha(0.6)
    ax_r.axhline(0, color="#888888", lw=0.5, ls=":")
    ax_r.set_ylabel("Glacier area trend (km²/year)")
    ax_r.set_title("(b) Glacier area trends by region", fontsize=10, pad=6)
    ax_r.tick_params(axis="x", rotation=30, labelsize=7)
    ax_r.grid(True, axis="y", alpha=0.3, lw=0.3)

    fig.tight_layout()
    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig7_regional_boxplots.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 8: World map with glacier markers (scale-aware)
# ══════════════════════════════════════════════════════════════════════════════


def figure_world_map_scale(combined_df, filename=None):
    """World map with all analyzed glaciers as points, colored by retreat rate.

    Parameters
    ----------
    combined_df : pandas.DataFrame
        Must have lat, lon, retreat_rate_km2_per_year columns.
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    valid = combined_df.dropna(subset=["lat", "lon", "retreat_rate_km2_per_year"])

    fig = plt.figure(figsize=(11, 5.5))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    ax.set_global()

    ax.add_feature(cfeature.OCEAN, facecolor="#F0F4F8")
    ax.add_feature(cfeature.LAND, facecolor="#E8E8E8", edgecolor="none")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#666666")
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor="#999999")

    # Color by retreat rate (negative = retreating = red, positive = blue)
    retreat = valid["retreat_rate_km2_per_year"].values
    vmax = float(np.nanpercentile(np.abs(retreat), 95))

    sc = ax.scatter(
        valid["lon"],
        valid["lat"],
        c=retreat,
        cmap="RdBu",
        vmin=-vmax,
        vmax=vmax,
        s=15,
        alpha=0.8,
        edgecolors="white",
        linewidths=0.3,
        transform=ccrs.PlateCarree(),
    )

    cbar = fig.colorbar(sc, ax=ax, orientation="horizontal", pad=0.05, fraction=0.04, shrink=0.6)
    cbar.set_label("Glacier area trend (km²/year)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    ax.set_title(
        f"Phase 2: {len(valid)} glaciers across 5 regions",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )

    fig.tight_layout()
    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig8_world_map_scale.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Helper: load combined results
# ══════════════════════════════════════════════════════════════════════════════


def load_combined_results(path=None):
    """Load the combined cross-region results CSV."""
    if path is None:
        path = PAPER_OUT_DIR / "global_results_combined.csv"
    return pd.read_csv(path)
