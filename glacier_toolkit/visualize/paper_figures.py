"""
Publication-quality matplotlib figures for the climate-glacier paper.

These are NOT the Instagram-format slides used by the social-media pipelines.
These are designed for inclusion in a peer-reviewed paper:
  - Light or print-friendly background
  - Multi-panel grids
  - Statistical annotations
  - Caption-ready (figure title is provided by the LaTeX, not the figure)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ..config import PAPER_OUT_DIR

# ── Paper-style theme ────────────────────────────────────────────────────────
PAPER_RC = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.titlesize": 11,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#222222",
    "xtick.color": "#222222",
    "ytick.color": "#222222",
    "text.color": "#111111",
    "axes.labelcolor": "#111111",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
}


def apply_paper_style():
    """Set matplotlib rcParams for publication-quality figures."""
    plt.rcParams.update(PAPER_RC)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 1: Per-glacier time series grid
# ══════════════════════════════════════════════════════════════════════════════


def figure_glacier_time_series_grid(
    glacier_results,
    n_cols=4,
    filename=None,
    panel_size=(2.6, 2.0),
):
    """Multi-panel figure: one panel per glacier showing area time series + trend.

    Parameters
    ----------
    glacier_results : list of dict
        Each must have:
        - 'glacier_name', 'glacier_region'
        - 'time_series': DataFrame with 'year' and 'area_km2'
        - 'retreat_rate_km2_per_year' (slope)
        - 'sensitivity_p_value'
    n_cols : int
        Columns in the panel grid.
    filename : Path, optional
    panel_size : tuple
        (width, height) per panel in inches.

    Returns
    -------
    Path
    """
    apply_paper_style()

    n = len(glacier_results)
    n_rows = int(np.ceil(n / n_cols))
    fig_w = n_cols * panel_size[0]
    fig_h = n_rows * panel_size[1]

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_w, fig_h), squeeze=False)
    axes = axes.flatten()

    for ax, result in zip(axes, glacier_results, strict=False):
        ts = result.get("time_series")
        if ts is None or len(ts) == 0:
            ax.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color="#999999",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            continue

        years = ts["year"].values
        areas = ts["area_km2"].values

        # Time series line
        ax.plot(
            years,
            areas,
            color="#1976D2",
            linewidth=1.5,
            marker="o",
            markersize=2.5,
            markerfacecolor="#1976D2",
            markeredgecolor="white",
            markeredgewidth=0.4,
        )

        # Linear trend
        slope = result.get("retreat_rate_km2_per_year", 0)
        intercept = areas.mean() - slope * years.mean()
        trend_y = intercept + slope * years
        ax.plot(years, trend_y, color="#D32F2F", linewidth=1.0, linestyle="--", alpha=0.8)

        # Title with glacier name
        name = result.get("glacier_name", "?").split("(")[0].split("/")[0].strip()
        ax.set_title(name, fontsize=9, fontweight="bold", pad=2)

        # Slope annotation
        sig = "*" if result.get("sensitivity_p_value", 1) < 0.05 else ""
        ax.text(
            0.02,
            0.05,
            f"{slope:+.2f}{sig} km²/yr",
            transform=ax.transAxes,
            fontsize=7,
            color="#444444",
            ha="left",
            va="bottom",
        )

        ax.tick_params(axis="both", which="major", labelsize=7)
        ax.grid(True, alpha=0.3, linewidth=0.4)

    # Hide unused panels
    for ax in axes[n:]:
        ax.set_visible(False)

    fig.supxlabel("Year", fontsize=10)
    fig.supylabel("Glacier area (km²)", fontsize=10)
    fig.tight_layout()

    if filename is None:
        filename = PAPER_OUT_DIR / "fig1_glacier_time_series_grid.pdf"
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename)
    fig.savefig(str(filename).replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  Saved: {filename}")
    return filename


# ══════════════════════════════════════════════════════════════════════════════
# Figure 2: Climate sensitivity scatter plot
# ══════════════════════════════════════════════════════════════════════════════


def figure_warming_vs_retreat_scatter(
    glacier_results,
    cross_glacier_stats=None,
    filename=None,
):
    """Cross-glacier scatter: local warming rate vs retreat rate.

    Each point is one glacier. The regression line tests the hypothesis
    that faster warming → faster retreat across all glaciers.

    Parameters
    ----------
    glacier_results : list of dict
        Each must have 'warming_rate_c_per_decade' and
        'retreat_rate_km2_per_year' and 'glacier_region'.
    cross_glacier_stats : dict, optional
        From correlation.cross_glacier_regression(). If provided, the line
        and r² are added to the plot.
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()

    fig, ax = plt.subplots(figsize=(6, 4.5))

    # Filter valid results
    valid = [
        r
        for r in glacier_results
        if not (
            np.isnan(r.get("warming_rate_c_per_decade", np.nan))
            or np.isnan(r.get("retreat_rate_km2_per_year", np.nan))
        )
    ]
    if len(valid) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig2_warming_vs_retreat.pdf")

    warming = np.array([r["warming_rate_c_per_decade"] for r in valid])
    retreat = np.array([r["retreat_rate_km2_per_year"] for r in valid])
    regions = [r.get("glacier_region", "Unknown") for r in valid]
    names = [r.get("glacier_name", "?").split("(")[0].split("/")[0].strip() for r in valid]

    # Color by region
    unique_regions = sorted(set(regions))
    cmap = plt.get_cmap("tab10")
    region_colors = {reg: cmap(i % 10) for i, reg in enumerate(unique_regions)}
    point_colors = [region_colors[r] for r in regions]

    ax.scatter(warming, retreat, c=point_colors, s=60, edgecolors="white", linewidths=0.8, zorder=3)

    # Annotate each point with glacier name
    for x, y, name in zip(warming, retreat, names, strict=False):
        ax.annotate(
            name, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=6, color="#444444"
        )

    # Regression line if stats provided
    if cross_glacier_stats:
        slope = cross_glacier_stats.get("regression_slope")
        intercept = cross_glacier_stats.get("regression_intercept")
        r2 = cross_glacier_stats.get("r_squared")
        p = cross_glacier_stats.get("p_value")

        if slope is not None and not np.isnan(slope):
            x_line = np.array([warming.min(), warming.max()])
            y_line = intercept + slope * x_line
            ax.plot(
                x_line,
                y_line,
                color="#222222",
                linewidth=1.2,
                linestyle="--",
                zorder=2,
                label=f"OLS fit: R²={r2:.2f}, p={p:.3f}",
            )
            ax.legend(loc="upper right", framealpha=0.9)

    # Reference lines
    ax.axhline(0, color="#888888", linewidth=0.5, linestyle=":", zorder=1)
    ax.axvline(0, color="#888888", linewidth=0.5, linestyle=":", zorder=1)

    ax.set_xlabel("Local warming rate (°C/decade, JJA Tmax from CRU TS v4.09)")
    ax.set_ylabel("Glacier area trend (km²/year, NDSI from Landsat)")
    ax.grid(True, alpha=0.3, linewidth=0.4)

    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig2_warming_vs_retreat.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 3: World map with glacier markers colored by sensitivity
# ══════════════════════════════════════════════════════════════════════════════


def figure_world_map(glacier_results, filename=None):
    """World map showing all glaciers colored by climate sensitivity.

    Uses cartopy Robinson projection with the project's paper style.

    Parameters
    ----------
    glacier_results : list of dict
        Each must have 'lat', 'lon', 'glacier_name', and an analysis metric.
    filename : Path, optional

    Returns
    -------
    Path
    """
    apply_paper_style()
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    ax.set_global()

    ax.add_feature(cfeature.OCEAN, facecolor="#F0F4F8")
    ax.add_feature(cfeature.LAND, facecolor="#E8E8E8", edgecolor="none")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#666666")
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor="#999999")

    # Plot each glacier
    for r in glacier_results:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is None or lon is None:
            continue

        # Color by warming rate
        warming = r.get("warming_rate_c_per_decade", 0)
        if not np.isnan(warming):
            # Map warming rate to color (0 → green, 1 → red)
            normalized = max(0, min(1, warming / 1.0))
            color = plt.cm.YlOrRd(0.3 + 0.6 * normalized)
        else:
            color = "#888888"

        ax.plot(
            lon,
            lat,
            "o",
            markersize=8,
            color=color,
            markeredgecolor="#222222",
            markeredgewidth=0.6,
            transform=ccrs.PlateCarree(),
        )

        name = r.get("glacier_name", "").split("(")[0].split("/")[0].strip()
        ax.text(lon + 2, lat + 1, name, fontsize=6, color="#222222", transform=ccrs.PlateCarree())

    return _save_paper_fig(fig, filename or PAPER_OUT_DIR / "fig3_world_map.pdf")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _save_paper_fig(fig, filename):
    """Save a figure as both PDF and PNG (for the paper and the README)."""
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename)
    fig.savefig(str(filename).replace(".pdf", ".png"))
    plt.close(fig)
    print(f"  Saved: {filename}")
    return filename
