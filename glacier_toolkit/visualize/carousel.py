"""
Instagram carousel assembler and caption generator.

Creates a 4-slide Instagram carousel for any glacier:
  Slide 1: Ghost Ice overlay (most visually striking)
  Slide 2: Before/After comparison
  Slide 3: Area time series chart with trend line
  Slide 4: Methodology + data sources

Also auto-generates Instagram captions with hashtags,
matching the format in instagram_captions.txt.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from ..config import (
    C_BG, C_TEXT, C_SUB, C_LIGHT, C_ACC, C_ICE, C_COOL, C_WARM,
    IG_DPI, IG_FIG, IG_OUT_DIR, FONT_FAMILY,
)
from ..style import (
    strip_axes, add_title_zone, add_source_line,
    add_slide_number, apply_theme,
)


def make_timeseries_slide(
    timeseries_df,
    trend_info,
    glacier_name,
    filename=None,
    slide_num=3,
    total_slides=4,
):
    """Create a time series chart slide showing glacier area over time.

    Parameters
    ----------
    timeseries_df : pandas.DataFrame
        Columns: year, area_km2, uncertainty_km2.
    trend_info : dict
        From glacier_area.fit_linear_trend(). Keys: slope_km2_per_year,
        ci_lower, ci_upper, mk_trend, mk_p_value.
    glacier_name : str
    filename : str or Path, optional
    slide_num, total_slides : int

    Returns
    -------
    Path
    """
    apply_theme()

    df = timeseries_df
    slope = trend_info["slope_km2_per_year"]
    ci_lo = trend_info["ci_lower"]
    ci_hi = trend_info["ci_upper"]

    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    # Headline: rate of loss
    headline = f"{slope:.2f} km²/yr"
    subtitle = f"{glacier_name}: Rate of Ice Loss"
    add_title_zone(fig, headline, subtitle)

    # Chart area
    ax = fig.add_axes([0.12, 0.18, 0.82, 0.62])
    strip_axes(ax)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(C_LIGHT)
    ax.spines["left"].set_linewidth(0.8)
    ax.tick_params(left=True, labelleft=True)

    years = df["year"].values
    areas = df["area_km2"].values

    # Area line with uncertainty band
    ax.plot(years, areas, color=C_ICE, linewidth=2.5, zorder=3)
    ax.fill_between(years, areas, alpha=0.15, color=C_ICE, zorder=2)

    if "uncertainty_km2" in df.columns:
        unc = df["uncertainty_km2"].values
        ax.fill_between(years, areas - unc, areas + unc,
                        alpha=0.2, color=C_ICE, zorder=2)

    # Trend line with CI band
    trend_y = trend_info.get("intercept_km2", 0) + slope * years.astype(float)
    ax.plot(years, trend_y, color=C_ACC, linewidth=1.5, linestyle="--",
            zorder=4, label=f"Trend: {slope:.2f} km²/yr")

    ci_lo_y = trend_info.get("intercept_km2", 0) + ci_lo * years.astype(float)
    ci_hi_y = trend_info.get("intercept_km2", 0) + ci_hi * years.astype(float)
    ax.fill_between(years, ci_lo_y, ci_hi_y, alpha=0.15, color=C_ACC,
                    zorder=1)

    ax.set_xlabel("Year", fontsize=12, color=C_SUB)
    ax.set_ylabel("Glacier Area (km²)", fontsize=12, color=C_SUB)
    ax.tick_params(colors=C_SUB, labelsize=10)

    # Legend
    ax.legend(loc="upper right", fontsize=9, facecolor=C_BG,
              edgecolor=C_LIGHT, labelcolor=C_TEXT)

    # Statistical annotation
    mk_trend = trend_info.get("mk_trend", "")
    mk_p = trend_info.get("mk_p_value", 1)
    sig_text = f"Mann-Kendall: {mk_trend} (p={mk_p:.4f})"
    fig.text(0.50, 0.13, sig_text,
             fontsize=9, ha="center", color=C_SUB, family=FONT_FAMILY)

    # CI annotation
    ci_text = f"95% CI on trend: [{ci_lo:.3f}, {ci_hi:.3f}] km²/yr"
    fig.text(0.50, 0.10, ci_text,
             fontsize=8, ha="center", color=C_LIGHT, family=FONT_FAMILY)

    add_source_line(fig, "Data: Landsat (USGS/NASA) · Analysis: glacier_toolkit")
    add_slide_number(fig, slide_num, total_slides)

    if filename is None:
        safe_name = glacier_name.replace(" ", "_").replace("/", "-").lower()
        filename = IG_OUT_DIR / f"timeseries_{safe_name}.png"
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved timeseries slide: {filename}")
    return filename


def make_methodology_slide(
    glacier_name,
    stats_summary,
    filename=None,
    slide_num=4,
    total_slides=4,
):
    """Create a methodology/sources slide (final carousel slide).

    Parameters
    ----------
    glacier_name : str
    stats_summary : dict
        Keys: baseline_year, modern_year, area_change_km2, area_change_pct,
        n_years_analyzed, satellite, method.
    filename : str or Path, optional

    Returns
    -------
    Path
    """
    apply_theme()

    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    add_title_zone(fig, "How?", "Methodology & Data Sources",
                   big_fontsize=40)

    # Content as structured text blocks
    y = 0.78
    line_height = 0.045

    sections = [
        ("SATELLITE DATA", [
            "Landsat 5/7/8/9 (USGS/NASA) — 30m resolution, 1984–present",
            "Processed via Google Earth Engine (cloud-masked median composites)",
        ]),
        ("GLACIER DETECTION", [
            "NDSI = (Green − SWIR) / (Green + SWIR)",
            "Threshold: 0.4 (Dozier 1989) + connected-component filtering",
            "Boundary validation: GLIMS database (NSIDC, 200k+ glaciers)",
        ]),
        ("STATISTICS", [
            f"Period: {stats_summary.get('baseline_year', '1985')} – "
            f"{stats_summary.get('modern_year', '2024')}",
            "Trend: Linear regression with 10,000-sample bootstrap 95% CI",
            "Significance: Mann-Kendall monotonic trend test",
            "Uncertainty: Boundary-pixel method (Granshaw & Fountain 2006)",
        ]),
        ("TOOLS", [
            "Python · Google Earth Engine · QGIS · glacier_toolkit",
            "Open-source: github.com — all code and data freely available",
        ]),
    ]

    for section_title, items in sections:
        fig.text(0.08, y, section_title,
                 fontsize=13, fontweight="bold", color=C_ACC,
                 family=FONT_FAMILY)
        y -= line_height * 0.8

        for item in items:
            fig.text(0.08, y, f"  {item}",
                     fontsize=9.5, color=C_TEXT, family=FONT_FAMILY,
                     wrap=True)
            y -= line_height

        y -= line_height * 0.5  # section gap

    # Inspired-by credit
    fig.text(0.50, 0.08,
             "Inspired by Chasing Ice & Chasing Time",
             fontsize=10, ha="center", color=C_SUB, style="italic",
             family=FONT_FAMILY)

    add_source_line(fig,
                    "glacier_toolkit v0.1 · Climate Shift Project · 2026")
    add_slide_number(fig, slide_num, total_slides)

    if filename is None:
        safe_name = glacier_name.replace(" ", "_").replace("/", "-").lower()
        filename = IG_OUT_DIR / f"methodology_{safe_name}.png"
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved methodology slide: {filename}")
    return filename


def generate_caption(glacier_name, stats, hashtags=None):
    """Auto-generate an Instagram caption for a glacier carousel.

    Parameters
    ----------
    glacier_name : str
    stats : dict
        Keys: area_change_pct, area_change_km2, baseline_year, modern_year,
        slope_km2_per_year.
    hashtags : list of str, optional

    Returns
    -------
    str
        Ready-to-post caption.
    """
    pct = abs(stats.get("area_change_pct", 0))
    km2 = abs(stats.get("area_change_km2", 0))
    y1 = stats.get("baseline_year", "1985")
    y2 = stats.get("modern_year", "2024")
    rate = abs(stats.get("slope_km2_per_year", 0))

    caption = (
        f"{glacier_name} has lost {pct:.0f}% of its ice area since {y1}.\n\n"
        f"That's {km2:.1f} km\u00b2 of ice — gone.\n\n"
        f"Using 40 years of NASA/USGS Landsat satellite imagery, I tracked "
        f"the retreat of {glacier_name} from space. The glacier is shrinking "
        f"at {rate:.2f} km\u00b2 per year.\n\n"
        f"Swipe to see:\n"
        f"1/ Ghost Ice — where ice used to be\n"
        f"2/ Then vs. Now — satellite comparison\n"
        f"3/ The data — {y2 - y1 if isinstance(y1, int) else '40'} years of area measurements\n"
        f"4/ How I did it — methodology & open-source tools\n\n"
        f"Inspired by Chasing Ice & Chasing Time.\n\n"
        f"All data is freely available. All code is open-source.\n"
        f"You can do this too.\n\n"
    )

    if hashtags is None:
        hashtags = [
            "#ClimateChange", "#GlacierRetreat", "#ClimateCrisis",
            "#Satellite", "#RemoteSensing", "#NASA", "#Landsat",
            "#ChasingIce", "#GlacierMelting", "#ClimateScience",
            "#DataVisualization", "#EarthObservation", "#Cryosphere",
            "#ClimateAction", "#SciComm", "#OpenScience",
        ]

    caption += " ".join(hashtags)
    return caption
