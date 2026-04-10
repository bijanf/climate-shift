"""
Before/after comparison map slides for Instagram.

Two-panel layout showing satellite imagery from an early and late year,
with glacier boundary overlays and headline area-loss statistic.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ..config import (
    C_ACC,
    C_BG,
    C_ICE,
    C_LIGHT,
    C_TEXT,
    FONT_FAMILY,
    IG_DPI,
    IG_FIG,
    IG_OUT_DIR,
)
from ..style import add_slide_number, add_source_line, add_title_zone, apply_theme


def make_comparison_slide(
    early_rgb,
    late_rgb,
    early_mask,
    late_mask,
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
    """Create a before/after comparison Instagram slide.

    Parameters
    ----------
    early_rgb, late_rgb : numpy.ndarray
        Satellite RGB images, shape (H, W, 3), values in [0, 1].
    early_mask, late_mask : numpy.ndarray
        Boolean glacier masks for each period.
    glacier_name : str
    year_early, year_late : int
    area_early_km2, area_late_km2 : float
    filename : str or Path, optional
    extent : tuple, optional
    slide_num, total_slides : int, optional
    source_text : str

    Returns
    -------
    Path
        Path to the saved image.
    """
    apply_theme()

    loss_pct = (area_early_km2 - area_late_km2) / area_early_km2 * 100 if area_early_km2 > 0 else 0

    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    # ── Title ──
    headline = f"−{abs(loss_pct):.1f}% Ice Area"
    subtitle = f"{glacier_name}: Then vs. Now"
    add_title_zone(fig, headline, subtitle)

    # ── Top panel: early year ──
    ax1 = fig.add_axes([0.03, 0.46, 0.94, 0.38])
    ax1.set_facecolor(C_BG)
    if early_rgb is not None:
        ax1.imshow(
            np.clip(early_rgb * 1.5, 0, 1), extent=extent, aspect="auto", interpolation="bilinear"
        )
    _overlay_mask_outline(ax1, early_mask, color=C_ICE, linewidth=1.5, extent=extent)
    ax1.text(
        0.02,
        0.95,
        str(year_early),
        transform=ax1.transAxes,
        fontsize=22,
        fontweight="bold",
        color=C_TEXT,
        va="top",
        family=FONT_FAMILY,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=C_BG, alpha=0.7, edgecolor="none"),
    )
    ax1.text(
        0.02,
        0.05,
        f"{area_early_km2:.1f} km²",
        transform=ax1.transAxes,
        fontsize=14,
        color=C_ICE,
        va="bottom",
        family=FONT_FAMILY,
    )
    ax1.axis("off")

    # ── Bottom panel: late year ──
    ax2 = fig.add_axes([0.03, 0.07, 0.94, 0.38])
    ax2.set_facecolor(C_BG)
    if late_rgb is not None:
        ax2.imshow(
            np.clip(late_rgb * 1.5, 0, 1), extent=extent, aspect="auto", interpolation="bilinear"
        )
    # Show the OLD boundary as dashed (ghost) and new as solid
    _overlay_mask_outline(
        ax2, early_mask, color=C_ICE, linewidth=1.0, linestyle="--", extent=extent
    )
    _overlay_mask_outline(ax2, late_mask, color="#FFFFFF", linewidth=1.5, extent=extent)
    ax2.text(
        0.02,
        0.95,
        str(year_late),
        transform=ax2.transAxes,
        fontsize=22,
        fontweight="bold",
        color=C_TEXT,
        va="top",
        family=FONT_FAMILY,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=C_BG, alpha=0.7, edgecolor="none"),
    )
    ax2.text(
        0.02,
        0.05,
        f"{area_late_km2:.1f} km²",
        transform=ax2.transAxes,
        fontsize=14,
        color=C_ACC,
        va="bottom",
        family=FONT_FAMILY,
    )
    ax2.axis("off")

    # ── Divider line between panels ──
    from matplotlib.lines import Line2D

    line = Line2D(
        [0.05, 0.95],
        [0.455, 0.455],
        color=C_LIGHT,
        linewidth=0.8,
        transform=fig.transFigure,
        clip_on=False,
    )
    fig.add_artist(line)

    # ── Source ──
    add_source_line(fig, source_text)

    if slide_num and total_slides:
        add_slide_number(fig, slide_num, total_slides)

    # ── Save ──
    if filename is None:
        safe_name = glacier_name.replace(" ", "_").replace("/", "-").lower()
        filename = IG_OUT_DIR / f"comparison_{safe_name}_{year_early}_{year_late}.png"

    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved comparison slide: {filename}")
    return filename


def _overlay_mask_outline(ax, mask, color, linewidth, linestyle="-", extent=None):
    """Draw contour of a boolean mask on axes."""
    from skimage import measure

    contours = measure.find_contours(mask.astype(float), 0.5)
    for contour in contours:
        rows, cols = contour[:, 0], contour[:, 1]
        if extent:
            h, w = mask.shape
            x_min, x_max, y_min, y_max = extent
            xs = x_min + (cols / w) * (x_max - x_min)
            ys = y_max - (rows / h) * (y_max - y_min)
        else:
            xs, ys = cols, rows
        ax.plot(xs, ys, color=color, linewidth=linewidth, linestyle=linestyle)
