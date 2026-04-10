"""
Reusable dark-theme plotting helpers for the Glacier Toolkit.

Extracted and generalized from:
  - plot_climate_shift.py  (strip_axes, slide layout, bootstrap viz)
  - plot_climate_maps.py   (make_map, colormaps, colorbars)

All functions produce Instagram-ready (1080x1350 @ 150 DPI) figures with the
shared dark theme.
"""

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

from .config import (
    C_ACC,
    C_BG,
    C_ICE,
    C_LAND,
    C_LIGHT,
    C_ROCK,
    C_SUB,
    C_TEXT,
    FONT_FAMILY,
    FONT_STACK,
    IG_FIG,
)

# ══════════════════════════════════════════════════════════════════════════════
# Matplotlib global defaults
# ══════════════════════════════════════════════════════════════════════════════


def apply_theme():
    """Set global matplotlib rcParams to match the project dark theme."""
    plt.rcParams.update(
        {
            "font.family": FONT_FAMILY,
            "font.sans-serif": FONT_STACK,
            "axes.grid": False,
            "axes.facecolor": C_BG,
            "figure.facecolor": C_BG,
            "text.color": C_TEXT,
            "axes.labelcolor": C_TEXT,
            "xtick.color": C_SUB,
            "ytick.color": C_SUB,
        }
    )


# ══════════════════════════════════════════════════════════════════════════════
# Custom colormaps for glacier visualization
# ══════════════════════════════════════════════════════════════════════════════

# Glacier retreat: rock brown → ice white → water blue
_glacier_colors = [
    C_ROCK,  # exposed bedrock
    "#8D6E63",  # lighter brown
    "#BCAAA4",  # warm gray (debris-covered)
    "#E0E0E0",  # light gray (dirty ice)
    C_ICE,  # clean ice cyan
    "#FFFFFF",  # bright snow
]
GLACIER_CMAP = mcolors.LinearSegmentedColormap.from_list("glacier", _glacier_colors, N=256)

# NDSI diverging: rock (negative) → neutral → ice (positive)
_ndsi_colors = [
    "#4E342E",
    "#795548",
    "#A1887F",  # brown (rock/soil, NDSI < 0)
    C_BG,  # neutral center
    "#80DEEA",
    "#4DD0E1",
    "#00BCD4",  # cyan (snow/ice, NDSI > 0)
]
NDSI_CMAP = mcolors.LinearSegmentedColormap.from_list("ndsi", _ndsi_colors, N=256)

# Lake/water: dark → deep blue → light blue
_water_colors = [C_BG, "#0D47A1", "#1565C0", "#1976D2", "#42A5F5", "#90CAF9"]
WATER_CMAP = mcolors.LinearSegmentedColormap.from_list("water", _water_colors, N=256)

# Area change (% loss): green (stable) → amber → red (severe loss)
_loss_colors = [
    "#2E7D32",  # dark green (stable/growing)
    "#66BB6A",  # light green
    "#FFA726",  # amber (moderate loss)
    "#EF5350",  # red (severe loss)
    "#B71C1C",  # dark red (catastrophic)
]
LOSS_CMAP = mcolors.LinearSegmentedColormap.from_list("loss", _loss_colors, N=256)

# Ghost ice overlay: transparent → translucent ice-cyan
_ghost_colors = [
    (0.66, 0.85, 0.92, 0.0),  # C_ICE at alpha=0
    (0.66, 0.85, 0.92, 0.15),  # barely visible
    (0.66, 0.85, 0.92, 0.4),  # ghostly
]
GHOST_CMAP = mcolors.LinearSegmentedColormap.from_list("ghost", _ghost_colors, N=256)


# ══════════════════════════════════════════════════════════════════════════════
# Axis helpers (from plot_climate_shift.py:470)
# ══════════════════════════════════════════════════════════════════════════════


def strip_axes(ax, keep_bottom=True):
    """Remove chart junk: spines, grid, top/right ticks."""
    ax.set_facecolor(C_BG)
    for sp in ax.spines.values():
        sp.set_visible(False)
    if keep_bottom:
        ax.spines["bottom"].set_visible(True)
        ax.spines["bottom"].set_color(C_LIGHT)
        ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(False)
    ax.tick_params(left=False, labelleft=False, bottom=keep_bottom, colors=C_SUB, labelsize=10)


# ══════════════════════════════════════════════════════════════════════════════
# Figure factories
# ══════════════════════════════════════════════════════════════════════════════


def make_ig_figure():
    """Create a blank Instagram-format figure (1080x1350) with dark background."""
    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)
    return fig


def make_wide_figure(width_in=14, height_in=9):
    """Create a wider figure for paper/presentation outputs."""
    fig = plt.figure(figsize=(width_in, height_in))
    fig.patch.set_facecolor(C_BG)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Layout zones (from the recurring patterns in both existing scripts)
# ══════════════════════════════════════════════════════════════════════════════


def add_title_zone(
    fig, big_text, sub_text, big_fontsize=50, sub_fontsize=20, big_color=None, sub_color=None
):
    """Add the standard two-line title block at the top of an IG slide.

    Pattern from plot_climate_maps.py:142-147:
      big number (e.g. "+2.3 °C") in accent color, subtitle below in white.
    """
    fig.text(
        0.50,
        0.965,
        big_text,
        fontsize=big_fontsize,
        fontweight="bold",
        ha="center",
        va="top",
        color=big_color or C_ACC,
        family=FONT_FAMILY,
    )
    fig.text(
        0.50,
        0.895,
        sub_text,
        fontsize=sub_fontsize,
        ha="center",
        va="top",
        color=sub_color or C_TEXT,
        fontweight="bold",
        family=FONT_FAMILY,
    )


def add_source_line(fig, source_text, context_text=None):
    """Add source attribution at the bottom of an IG slide.

    Pattern from plot_climate_maps.py:196-201.
    """
    if context_text:
        fig.text(
            0.50, 0.032, context_text, fontsize=7.5, ha="center", color=C_SUB, family=FONT_FAMILY
        )
    fig.text(0.50, 0.012, source_text, fontsize=6.5, ha="center", color=C_LIGHT, family=FONT_FAMILY)


def add_colorbar(fig, mappable, cb_unit="", vmin=0, vmax=1, extend="neither", position=None):
    """Add a horizontal colorbar matching the project style.

    Pattern from plot_climate_maps.py:180-193.
    """
    if position is None:
        position = [0.15, 0.065, 0.70, 0.015]

    cax = fig.add_axes(position)
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal", extend=extend)
    cb.outline.set_edgecolor(C_LIGHT)

    span = vmax - vmin
    step = 1 if span <= 8 else (5 if span <= 30 else 10)
    clean_ticks = np.arange(int(np.ceil(vmin / step) * step), int(np.floor(vmax)) + 1, step)
    if len(clean_ticks) > 0:
        cb.set_ticks(clean_ticks)
        cb.set_ticklabels([f"{int(t)}" for t in clean_ticks])
    cb.ax.tick_params(labelsize=10, colors=C_SUB, length=0)
    cax.set_facecolor(C_BG)

    if cb_unit:
        right_edge = position[0] + position[2] + 0.03
        fig.text(
            right_edge,
            position[1],
            cb_unit,
            fontsize=11,
            color=C_SUB,
            va="center",
            family=FONT_FAMILY,
        )

    return cb


# ══════════════════════════════════════════════════════════════════════════════
# Cartographic decorations
# ══════════════════════════════════════════════════════════════════════════════


def add_north_arrow(ax, x=0.90, y=0.85, size=0.14, color=None, labelcolor=None):
    """Draw a clear, prominent north arrow on a matplotlib axes.

    Designed for image axes (e.g. satellite raster overlays) where the
    imagery is north-up — which is the standard for projected satellite
    rasters from Landsat, Sentinel-2, and most GIS workflows.

    The arrow is drawn on a dark rounded background panel so it remains
    visible against both bright snow/ice and dark rock/water, and is
    sized to remain legible in small README/social media previews.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    x, y : float
        Center position in axes coordinates (0-1). Default: top-right.
    size : float
        Arrow length in axes coordinates.
    color : str, optional
        Arrow color. Defaults to project ice-cyan for contrast.
    labelcolor : str, optional
        "N" label color. Defaults to bright white.
    """
    import matplotlib.patches as mpatches

    if color is None:
        color = C_ICE
    if labelcolor is None:
        labelcolor = "#FFFFFF"

    # Larger background panel for visibility
    pad_x = size * 0.65
    pad_y_below = size * 0.65
    pad_y_above = size * 1.2  # extra room for the N label
    bg = mpatches.FancyBboxPatch(
        (x - pad_x, y - pad_y_below),
        2 * pad_x,
        pad_y_below + pad_y_above,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        transform=ax.transAxes,
        facecolor=C_BG,
        edgecolor=C_ICE,
        linewidth=1.5,
        alpha=0.9,
        zorder=10,
    )
    ax.add_patch(bg)

    # Arrow shaft + head pointing up — thick and bold
    ax.annotate(
        "",
        xy=(x, y + size * 0.6),
        xytext=(x, y - size * 0.5),
        xycoords="axes fraction",
        arrowprops=dict(
            arrowstyle="-|>,head_length=0.7,head_width=0.45",
            color=color,
            linewidth=3.5,
            mutation_scale=22,
        ),
        annotation_clip=False,
        zorder=11,
    )

    # Big "N" label above the arrow head
    ax.text(
        x,
        y + size * 0.78,
        "N",
        transform=ax.transAxes,
        fontsize=22,
        fontweight="bold",
        color=labelcolor,
        ha="center",
        va="bottom",
        family=FONT_FAMILY,
        zorder=12,
    )


def add_scale_bar(ax, length_km, x=0.05, y=0.05, height=0.005, color=None):
    """Draw a simple horizontal scale bar in axes coordinates.

    Note: This is a *visual* scale bar that uses the axes coordinate system.
    For an accurate metric scale, the imagery's geographic extent must be
    known and passed in via the imshow extent parameter.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    length_km : float
        Length the bar represents in km (for the label).
    x, y : float
        Bottom-left position in axes coordinates.
    height : float
        Bar thickness in axes coordinates.
    color : str, optional
        Bar color. Defaults to project text color.
    """
    import matplotlib.patches as mpatches

    if color is None:
        color = C_TEXT

    # Bar (~12% of axes width)
    bar_width = 0.12
    bar = mpatches.Rectangle(
        (x, y),
        bar_width,
        height,
        transform=ax.transAxes,
        facecolor=color,
        edgecolor=color,
        linewidth=0.8,
    )
    ax.add_patch(bar)

    # Label centered above the bar
    ax.text(
        x + bar_width / 2,
        y + height + 0.012,
        f"{length_km:g} km",
        transform=ax.transAxes,
        fontsize=9,
        color=color,
        ha="center",
        va="bottom",
        family=FONT_FAMILY,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Map helpers (from plot_climate_maps.py:131-205)
# ══════════════════════════════════════════════════════════════════════════════


def make_glacier_map(ax, extent, add_features=True):
    """Set up a cartopy GeoAxes with the project's dark map style.

    Parameters
    ----------
    ax : cartopy.mpl.geoaxes.GeoAxes
        Axes with a cartopy projection.
    extent : tuple
        (west, south, east, north) in PlateCarree degrees.
    add_features : bool
        Whether to add ocean, land, borders, coastlines.
    """
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    if add_features:
        ax.add_feature(cfeature.OCEAN, facecolor=C_BG)
        ax.add_feature(cfeature.LAND, facecolor=C_LAND, edgecolor="none")
        ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor=C_LIGHT)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="#5F6368")


def global_map_figure(figsize=None):
    """Create a Robinson-projection world map figure for the global dashboard."""
    if figsize is None:
        figsize = IG_FIG

    fig = plt.figure(figsize=figsize)
    fig.patch.set_facecolor(C_BG)

    ax = fig.add_axes([0.03, 0.10, 0.94, 0.75], projection=ccrs.Robinson())
    ax.set_global()
    ax.add_feature(cfeature.OCEAN, facecolor=C_BG)
    ax.add_feature(cfeature.LAND, facecolor=C_LAND, edgecolor="none")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#5F6368")
    ax.outline_patch.set_edgecolor(C_LIGHT)
    ax.outline_patch.set_linewidth(0.5)

    return fig, ax


def add_glacier_marker(ax, lat, lon, label, value_pct=None, **kwargs):
    """Plot a glacier marker on a map axes with optional % loss label.

    Parameters
    ----------
    ax : GeoAxes
    lat, lon : float
    label : str
        Glacier name.
    value_pct : float, optional
        Percentage area loss. Colors marker from green (0%) to red (100%).
    """
    if value_pct is not None:
        color = LOSS_CMAP(min(abs(value_pct) / 100, 1.0))
    else:
        color = C_ACC

    ax.plot(
        lon,
        lat,
        "o",
        ms=kwargs.get("ms", 8),
        color=color,
        markeredgecolor="white",
        markeredgewidth=0.8,
        transform=ccrs.PlateCarree(),
        zorder=5,
    )
    ax.text(
        lon + kwargs.get("label_offset_lon", 1.5),
        lat + kwargs.get("label_offset_lat", 0.5),
        label,
        fontsize=kwargs.get("fontsize", 8),
        color=C_TEXT,
        fontweight="bold",
        transform=ccrs.PlateCarree(),
        zorder=5,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Slide numbering helper
# ══════════════════════════════════════════════════════════════════════════════


def add_slide_number(fig, current, total, x=0.95, y=0.97):
    """Add a subtle slide counter (e.g. '2/4') in the top-right corner."""
    fig.text(
        x,
        y,
        f"{current}/{total}",
        fontsize=12,
        color=C_LIGHT,
        ha="right",
        va="top",
        family=FONT_FAMILY,
    )
