"""
Time-lapse frame generation and GIF/video assembly.

Produces one PNG per year with consistent extent, projection, and styling,
suitable for assembly into animated GIFs or MP4 videos.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from ..config import (
    C_BG,
    C_ICE,
    C_SUB,
    C_TEXT,
    FONT_FAMILY,
    IG_DPI,
    IG_FIG,
    IG_OUT_DIR,
)
from ..style import add_north_arrow, apply_theme


def generate_timelapse_frames(
    annual_data,
    glacier_name,
    output_dir=None,
    extent=None,
    show_outline=True,
):
    """Generate one PNG frame per year for time-lapse assembly.

    Parameters
    ----------
    annual_data : dict
        {year: {"rgb": ndarray (H,W,3), "mask": ndarray (H,W) bool,
                "area_km2": float}}
        Not all keys are required; at minimum provide "mask" or "rgb".
    glacier_name : str
    output_dir : Path, optional
    extent : tuple, optional
    show_outline : bool
        Draw glacier boundary contour on each frame.

    Returns
    -------
    list of Path
        Paths to generated frame images, sorted by year.
    """
    apply_theme()

    safe_name = glacier_name.replace(" ", "_").replace("/", "-").lower()
    if output_dir is None:
        output_dir = IG_OUT_DIR / f"timelapse_{safe_name}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_paths = []
    years = sorted(annual_data.keys())

    # Get consistent image dimensions from first frame
    first = annual_data[years[0]]
    if "rgb" in first:
        h, w = first["rgb"].shape[:2]
    elif "mask" in first:
        h, w = first["mask"].shape
    else:
        raise ValueError("Each year must have 'rgb' or 'mask' data")

    for year in years:
        data = annual_data[year]

        fig = plt.figure(figsize=IG_FIG)
        fig.patch.set_facecolor(C_BG)

        # Title with glacier name
        fig.text(
            0.50,
            0.97,
            glacier_name,
            fontsize=24,
            fontweight="bold",
            ha="center",
            va="top",
            color=C_TEXT,
            family=FONT_FAMILY,
        )

        # Big year number
        fig.text(
            0.50,
            0.92,
            str(year),
            fontsize=60,
            fontweight="bold",
            ha="center",
            va="top",
            color=C_ICE,
            family=FONT_FAMILY,
            alpha=0.8,
        )

        ax = fig.add_axes([0.03, 0.08, 0.94, 0.78])
        ax.set_facecolor(C_BG)

        # Show RGB or NDSI mask
        if "rgb" in data and data["rgb"] is not None:
            rgb = np.clip(data["rgb"] * 1.5, 0, 1)
            ax.imshow(rgb, extent=extent, aspect="auto", interpolation="bilinear")
        elif "mask" in data:
            # Show mask as ice-cyan on dark background
            vis = np.zeros((h, w, 3))
            mask = data["mask"]
            vis[mask] = [0.66, 0.85, 0.92]  # C_ICE
            ax.imshow(vis, extent=extent, aspect="auto")

        # Glacier outline
        if show_outline and "mask" in data:
            _draw_contour(ax, data["mask"], C_ICE, 1.5, extent)

        # North arrow
        add_north_arrow(ax, x=0.88, y=0.83, size=0.10)

        ax.axis("off")

        # Area stat
        if "area_km2" in data:
            fig.text(
                0.50,
                0.05,
                f"{data['area_km2']:.1f} km²",
                fontsize=18,
                ha="center",
                color=C_SUB,
                family=FONT_FAMILY,
            )

        # Save frame
        frame_path = output_dir / f"frame_{year}.png"
        fig.savefig(frame_path, dpi=IG_DPI, facecolor=C_BG)
        plt.close(fig)
        frame_paths.append(frame_path)

    print(f"  Generated {len(frame_paths)} timelapse frames in {output_dir}")
    return frame_paths


def assemble_gif(frame_paths, output_path=None, fps=2, loop=0):
    """Assemble PNG frames into an animated GIF.

    Parameters
    ----------
    frame_paths : list of Path
        Sorted frame images.
    output_path : Path, optional
    fps : int
        Frames per second.
    loop : int
        Number of loops (0 = infinite).

    Returns
    -------
    Path
        Path to the output GIF.
    """
    if not frame_paths:
        raise ValueError("No frames to assemble")

    if output_path is None:
        output_path = frame_paths[0].parent / "timelapse.gif"
    output_path = Path(output_path)

    frames = [Image.open(p) for p in frame_paths]
    duration_ms = int(1000 / fps)

    # Hold the last frame longer
    durations = [duration_ms] * len(frames)
    durations[-1] = duration_ms * 3

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        optimize=True,
    )

    print(f"  Saved GIF: {output_path} ({len(frames)} frames, {fps} fps)")
    return output_path


def _draw_contour(ax, mask, color, linewidth, extent=None):
    """Draw contour of a boolean mask."""
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
        ax.plot(xs, ys, color=color, linewidth=linewidth)
