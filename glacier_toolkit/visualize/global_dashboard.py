"""
Global glacier retreat dashboard — world map visualization.

Creates a Robinson-projection world map showing all tracked glaciers,
colored by percentage area lost, with inset panels for the most dramatic cases.
"""

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from pathlib import Path

from ..config import (
    C_BG, C_TEXT, C_SUB, C_LIGHT, C_ACC, GLACIER_REGISTRY,
    IG_DPI, IG_FIG, GLOBAL_OUT_DIR, FONT_FAMILY,
)
from ..style import (
    global_map_figure, add_glacier_marker, add_title_zone,
    add_source_line, LOSS_CMAP, apply_theme,
)


def make_global_dashboard(
    glacier_stats,
    filename=None,
    title_big=None,
    title_sub="Global Glacier Retreat from Space",
    source_text="Data: Landsat (USGS/NASA) · GLIMS (NSIDC) · GEE",
    top_n_insets=4,
):
    """Create the global glacier retreat dashboard.

    Parameters
    ----------
    glacier_stats : dict
        {registry_key: {"area_change_pct": float, "area_early_km2": float,
         "area_late_km2": float, "year_early": int, "year_late": int, ...}}
    filename : str or Path, optional
    title_big : str, optional
        Headline number. Auto-computed if None (average % loss).
    title_sub : str
    source_text : str
    top_n_insets : int
        Number of inset mini-panels for most dramatic retreats.

    Returns
    -------
    Path
        Path to saved image.
    """
    apply_theme()

    # Compute summary stats
    pct_losses = [abs(s.get("area_change_pct", 0)) for s in glacier_stats.values()
                  if s.get("area_change_pct") is not None]
    avg_loss = np.mean(pct_losses) if pct_losses else 0
    n_glaciers = len(glacier_stats)
    total_lost_km2 = sum(
        s.get("area_early_km2", 0) - s.get("area_late_km2", 0)
        for s in glacier_stats.values()
        if s.get("area_early_km2") is not None
    )

    if title_big is None:
        title_big = f"−{avg_loss:.0f}% Average"

    # Create world map
    fig, ax = global_map_figure(figsize=IG_FIG)

    # Title
    add_title_zone(fig, title_big, title_sub)

    # Plot each glacier as a colored dot
    for key, stats in glacier_stats.items():
        glacier = GLACIER_REGISTRY.get(key)
        if glacier is None:
            continue

        pct = abs(stats.get("area_change_pct", 0))
        add_glacier_marker(
            ax,
            glacier["lat"], glacier["lon"],
            glacier["name"].split("/")[0].split("(")[0].strip(),
            value_pct=pct,
            fontsize=7,
        )

    # Colorbar for % loss
    sm = plt.cm.ScalarMappable(cmap=LOSS_CMAP,
                                norm=plt.Normalize(vmin=0, vmax=100))
    sm.set_array([])
    cax = fig.add_axes([0.15, 0.065, 0.55, 0.015])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_edgecolor(C_LIGHT)
    cb.set_ticks([0, 25, 50, 75, 100])
    cb.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
    cb.ax.tick_params(labelsize=9, colors=C_SUB, length=0)
    cax.set_facecolor(C_BG)
    fig.text(0.73, 0.065, "area lost", fontsize=10, color=C_SUB,
             va="center", family=FONT_FAMILY)

    # Summary stats box
    stats_text = (f"{n_glaciers} glaciers tracked\n"
                  f"{total_lost_km2:,.0f} km² total ice lost")
    fig.text(0.50, 0.038, stats_text,
             fontsize=8, ha="center", color=C_SUB, family=FONT_FAMILY,
             linespacing=1.5)

    # Source line
    add_source_line(fig, source_text)

    # Save
    if filename is None:
        filename = GLOBAL_OUT_DIR / "global_glacier_dashboard.png"
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved global dashboard: {filename}")
    return filename


def make_region_dashboard(
    region_name,
    glacier_stats,
    center_lat,
    center_lon,
    extent,
    filename=None,
):
    """Create a regional zoom dashboard (e.g. 'Andes', 'Alps', 'Himalayas').

    Parameters
    ----------
    region_name : str
    glacier_stats : dict
        Same format as make_global_dashboard.
    center_lat, center_lon : float
    extent : tuple
        (west, south, east, north).
    filename : str or Path, optional

    Returns
    -------
    Path
    """
    apply_theme()

    pct_losses = [abs(s.get("area_change_pct", 0)) for s in glacier_stats.values()
                  if s.get("area_change_pct") is not None]
    avg_loss = np.mean(pct_losses) if pct_losses else 0

    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    add_title_zone(fig, f"−{avg_loss:.0f}%",
                   f"{region_name}: Glacier Retreat")

    ax = fig.add_axes([0.03, 0.10, 0.94, 0.75],
                      projection=ccrs.Orthographic(center_lon, center_lat))

    from ..style import make_glacier_map
    make_glacier_map(ax, extent)

    for key, stats in glacier_stats.items():
        glacier = GLACIER_REGISTRY.get(key)
        if glacier is None:
            continue
        pct = abs(stats.get("area_change_pct", 0))
        add_glacier_marker(ax, glacier["lat"], glacier["lon"],
                           glacier["name"].split("/")[0].strip(),
                           value_pct=pct)

    add_source_line(fig, "Data: Landsat (USGS/NASA) · GLIMS (NSIDC)")

    if filename is None:
        safe = region_name.lower().replace(" ", "_")
        filename = GLOBAL_OUT_DIR / f"region_dashboard_{safe}.png"
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved region dashboard: {filename}")
    return filename
