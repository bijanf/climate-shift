"""
"Ghost Ice" overlay visualization — the signature visual.

Creates Instagram-ready slides showing:
  - Modern satellite imagery as the base
  - Historical glacier extent as a translucent ice-cyan overlay
  - The "lost zone" (historical minus modern) with a ghostly stipple pattern
  - Headline statistic: percentage of ice lost

This is the most powerful single visualization for communicating glacier retreat.
"""

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from ..config import (
    C_BG,
    C_ICE,
    C_LIGHT,
    C_SUB,
    C_TEXT,
    FONT_FAMILY,
    IG_DPI,
    IG_FIG,
    IG_OUT_DIR,
)
from ..style import (
    add_north_arrow,
    add_slide_number,
    add_source_line,
    add_title_zone,
    apply_theme,
)


def make_ghost_ice_slide(
    modern_rgb,
    historical_mask,
    modern_mask,
    glacier_name,
    year_early,
    year_late,
    area_early_km2,
    area_late_km2,
    filename=None,
    extent=None,
    slide_num=None,
    total_slides=None,
    source_text="Data: Landsat (USGS/NASA) · GLIMS (NSIDC)",
):
    """Create a Ghost Ice Instagram slide.

    Parameters
    ----------
    modern_rgb : numpy.ndarray
        Modern satellite RGB image, shape (H, W, 3), values in [0, 1].
    historical_mask : numpy.ndarray
        Boolean mask of historical glacier extent, shape (H, W).
    modern_mask : numpy.ndarray
        Boolean mask of modern glacier extent, shape (H, W).
    glacier_name : str
        Display name of the glacier.
    year_early, year_late : int
        Years of the historical and modern data.
    area_early_km2, area_late_km2 : float
        Glacier areas for the headline statistic.
    filename : str or Path, optional
        Output file path. Auto-generated if None.
    extent : tuple, optional
        (left, right, bottom, top) for imshow extent.
    slide_num, total_slides : int, optional
        For slide numbering (e.g. 1/4).
    source_text : str
        Data source attribution.

    Returns
    -------
    Path
        Path to the saved image.
    """
    apply_theme()

    # Compute headline statistic
    loss_pct = (area_early_km2 - area_late_km2) / area_early_km2 * 100 if area_early_km2 > 0 else 0
    loss_km2 = area_early_km2 - area_late_km2

    # Create the figure
    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    # ── Title zone ──
    if loss_pct >= 90:
        headline = f"−{loss_pct:.0f}%"
        subtitle = f"{glacier_name}: Nearly Gone"
    elif loss_pct >= 50:
        headline = f"−{loss_pct:.0f}%"
        subtitle = f"{glacier_name}: More Than Half Lost"
    else:
        headline = f"−{loss_pct:.1f}%"
        subtitle = f"{glacier_name}: Glacier Area Lost"

    add_title_zone(fig, headline, subtitle)

    # ── Time range ──
    fig.text(
        0.50,
        0.855,
        f"{year_early} → {year_late}",
        fontsize=16,
        ha="center",
        va="top",
        color=C_SUB,
        family=FONT_FAMILY,
    )

    # ── Map axes ──
    ax = fig.add_axes([0.03, 0.12, 0.94, 0.70])
    ax.set_facecolor(C_BG)

    # Base: modern satellite image
    if modern_rgb is not None:
        # Enhance contrast for dark theme
        rgb = np.clip(modern_rgb * 1.5, 0, 1)
        ax.imshow(rgb, extent=extent, aspect="auto", interpolation="bilinear")
    else:
        # If no RGB available, show a dark base
        h, w = historical_mask.shape
        ax.imshow(np.full((h, w, 3), 0.08), extent=extent, aspect="auto")

    # Ghost overlay: historical extent in translucent ice-cyan
    ghost = np.zeros((*historical_mask.shape, 4))
    # Historical extent that is NOW gone → ghostly blue
    lost_zone = historical_mask & ~modern_mask
    ghost[lost_zone] = [0.66, 0.85, 0.92, 0.35]  # C_ICE at 35% alpha

    # Current ice extent → brighter overlay
    ghost[modern_mask] = [0.66, 0.85, 0.92, 0.15]  # subtle tint on current ice

    ax.imshow(ghost, extent=extent, aspect="auto", interpolation="nearest")

    # Ghost zone hatch pattern for the lost area
    lost_overlay = np.zeros((*historical_mask.shape, 4))
    # Add a stipple effect by masking alternate pixels in the lost zone
    stipple = np.zeros_like(lost_zone)
    stipple[::3, ::3] = True
    stipple_mask = lost_zone & stipple
    lost_overlay[stipple_mask] = [0.66, 0.85, 0.92, 0.6]
    ax.imshow(lost_overlay, extent=extent, aspect="auto", interpolation="nearest")

    # Outline: historical boundary in dashed ice-cyan
    _draw_mask_contour(
        ax,
        historical_mask,
        color=C_ICE,
        linewidth=1.2,
        linestyle="--",
        extent=extent,
        label=f"{year_early}",
    )

    # Outline: modern boundary in solid white
    _draw_mask_contour(
        ax,
        modern_mask,
        color="#FFFFFF",
        linewidth=1.8,
        linestyle="-",
        extent=extent,
        label=f"{year_late}",
    )

    ax.set_xlim(extent[0], extent[1]) if extent else None
    ax.set_ylim(extent[2], extent[3]) if extent else None
    ax.axis("off")

    # ── North arrow (top-right corner) ──
    add_north_arrow(ax, x=0.94, y=0.88, size=0.05)

    # ── Legend ──
    legend_elements = [
        mpatches.Patch(
            facecolor=C_ICE,
            alpha=0.35,
            edgecolor=C_ICE,
            linestyle="--",
            linewidth=1.2,
            label=f"Ice extent {year_early}",
        ),
        mpatches.Patch(
            facecolor="none", edgecolor="#FFFFFF", linewidth=1.8, label=f"Ice extent {year_late}"
        ),
        mpatches.Patch(facecolor=C_ICE, alpha=0.5, label=f"Lost: {loss_km2:.1f} km²"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower left",
        fontsize=9,
        facecolor=C_BG,
        edgecolor=C_LIGHT,
        labelcolor=C_TEXT,
        framealpha=0.8,
    )

    # ── Source line ──
    add_source_line(
        fig,
        source_text,
        context_text=f"Glacier area: {area_early_km2:.1f} km² → {area_late_km2:.1f} km²",
    )

    # ── Slide number ──
    if slide_num and total_slides:
        add_slide_number(fig, slide_num, total_slides)

    # ── Save ──
    if filename is None:
        safe_name = glacier_name.replace(" ", "_").replace("/", "-").lower()
        filename = IG_OUT_DIR / f"ghost_ice_{safe_name}_{year_early}_{year_late}.png"

    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved Ghost Ice slide: {filename}")
    return filename


def _draw_mask_contour(ax, mask, color, linewidth, linestyle, extent=None, label=None):
    """Draw a contour line around a boolean mask."""
    from skimage import measure

    contours = measure.find_contours(mask.astype(float), 0.5)

    for i, contour in enumerate(contours):
        rows, cols = contour[:, 0], contour[:, 1]
        if extent:
            # Map pixel coordinates to extent coordinates
            h, w = mask.shape
            x_min, x_max, y_min, y_max = extent
            xs = x_min + (cols / w) * (x_max - x_min)
            ys = y_max - (rows / h) * (y_max - y_min)
        else:
            xs, ys = cols, rows

        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            label=label if i == 0 else None,
        )
