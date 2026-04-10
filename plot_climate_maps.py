#!/usr/bin/env python3
"""
plot_climate_maps.py — Gridded Climate Shift Maps for Instagram
================================================================
Downloads CRU TS v4.09 monthly max temperature data and produces
publication-quality maps showing summer warming across Europe,
the Alps, and major cities.

Data: CRU TS v4.09 (Harris et al. 2020) — 0.5° gridded, 1901–2024
"""

import os
import gzip
import shutil
import warnings
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from urllib.request import urlopen, Request
from pathlib import Path

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent / "data"
NC_FILE  = DATA_DIR / "cru_ts4.09.1901.2024.tmx.dat.nc"
NC_GZ    = DATA_DIR / "cru_ts4.09.1901.2024.tmx.dat.nc.gz"
CRU_URL  = ("https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.09/"
            "cruts.2503051245.v4.09/tmx/cru_ts4.09.1901.2024.tmx.dat.nc.gz")

HIST_START, HIST_END = "1930", "1959"
MOD_START,  MOD_END  = "1995", "2024"
SUMMER_MONTHS = [6, 7, 8]

# Instagram slide dimensions
IG_DPI = 150
IG_FIG = (1080 / IG_DPI, 1350 / IG_DPI)

# Dark theme tokens (matching the station carousel)
C_BG    = "#0F1419"
C_TEXT  = "#E8EAED"
C_SUB   = "#9AA0A6"
C_LIGHT = "#3C4043"
C_ACC   = "#FF6B6B"
SOURCE  = "Data: CRU TS v4.09 (Harris et al. 2020)  |  Analysis 2026"

# Diverging colormap for Europe overview: blue → dark → vivid red
_div_colors = [
    "#2166AC", "#4393C3", "#92C5DE",               # cool blues
    "#3A3A3A",                                       # neutral dark centre
    "#F4A582", "#E05040", "#D32F2F", "#B71C1C",   # vivid warm reds
]
SHIFT_CMAP = mcolors.LinearSegmentedColormap.from_list("shift", _div_colors, N=256)

# Sequential warm colormap for regional/city zooms (everything is positive warming)
_warm_colors = ["#1A1A2E", "#2D1B3D", "#6A1B4D", "#C0392B", "#E74C3C",
                "#FF6B6B", "#FF8A65", "#FFCC80", "#FFF9C4"]
WARM_SEQ_CMAP = mcolors.LinearSegmentedColormap.from_list("warm_seq", _warm_colors, N=256)

# Heat-days colormap: dark → amber → bright red
_heat_colors = [C_BG, "#1A0E00", "#4A2800", "#B8660A", "#FFA726", "#FF6B6B", "#FF1744"]
HEAT_CMAP = mcolors.LinearSegmentedColormap.from_list("heat", _heat_colors, N=256)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Download & load data
# ══════════════════════════════════════════════════════════════════════════════

def ensure_data():
    """Download and decompress CRU TS if not already cached."""
    DATA_DIR.mkdir(exist_ok=True)
    if NC_FILE.exists():
        print(f"  Using cached {NC_FILE.name}")
        return
    if not NC_GZ.exists():
        print(f"  Downloading CRU TS v4.09 tmx (~180 MB) …")
        req = Request(CRU_URL, headers={"User-Agent": "climate-maps/1.0"})
        with urlopen(req, timeout=600) as resp, open(NC_GZ, "wb") as f:
            shutil.copyfileobj(resp, f)
        print(f"  Downloaded {NC_GZ.name}")
    print(f"  Decompressing …")
    with gzip.open(NC_GZ, "rb") as gz, open(NC_FILE, "wb") as out:
        shutil.copyfileobj(gz, out)
    print(f"  Ready: {NC_FILE.name}")


print("=" * 60)
print("  GRIDDED CLIMATE SHIFT MAPS")
print("=" * 60)

print("\nStep 1: Data")
ensure_data()

print("\nStep 2: Loading & computing summer TMAX shift …")
ds = xr.open_dataset(NC_FILE)

# Summer (JJA) months only
summer = ds.tmx.sel(time=ds.time.dt.month.isin(SUMMER_MONTHS))

# Climatologies
hist_clim = summer.sel(time=slice(HIST_START, HIST_END)).mean(dim="time")
mod_clim  = summer.sel(time=slice(MOD_START,  MOD_END)).mean(dim="time")
shift     = mod_clim - hist_clim

# Count months with TMAX > 30 °C  (proxy for extreme heat frequency)
hist_hot = (summer.sel(time=slice(HIST_START, HIST_END)) > 30).sum(dim="time").astype(float)
mod_hot  = (summer.sel(time=slice(MOD_START,  MOD_END))  > 30).sum(dim="time").astype(float)
# Normalize to per-year
hist_yrs = len(summer.sel(time=slice(HIST_START, HIST_END)).time) / 3  # 3 months/yr
mod_yrs  = len(summer.sel(time=slice(MOD_START,  MOD_END)).time)  / 3
hot_change = (mod_hot / mod_yrs) - (hist_hot / hist_yrs)  # extra hot months per year

# European mean shift (land only, area-weighted)
eu_shift = shift.sel(lat=slice(34, 72), lon=slice(-25, 45))
weights  = np.cos(np.deg2rad(eu_shift.lat))
eu_mean  = float(eu_shift.weighted(weights).mean().values)
print(f"  European mean summer TMAX shift: +{eu_mean:.2f} °C")
print(f"  ({HIST_START}–{HIST_END} → {MOD_START}–{MOD_END})")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Map plotting
# ══════════════════════════════════════════════════════════════════════════════

def make_map(data, extent, projection, title_big, title_sub,
             filename, cmap=SHIFT_CMAP, vmin=-3, vmax=3, vcenter=0,
             city_markers=None, cb_unit="°C", cb_extend="neither",
             # legacy params kept but ignored
             subtitle=None, colorbar_label=None, stat_line=None):
    """Produce one minimal Instagram-format map slide."""

    fig = plt.figure(figsize=IG_FIG)
    fig.patch.set_facecolor(C_BG)

    # ── Title: big number + short phrase (≤10 words total) ──
    fig.text(0.50, 0.965, title_big,
             fontsize=50, fontweight="bold", ha="center", va="top",
             color=C_ACC, family="sans-serif")
    fig.text(0.50, 0.895, title_sub,
             fontsize=20, ha="center", va="top", color=C_TEXT,
             fontweight="bold", family="sans-serif")

    # ── Map: fills most of the slide ──
    ax = fig.add_axes([0.03, 0.10, 0.94, 0.75], projection=projection)
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.OCEAN,     facecolor=C_BG)
    ax.add_feature(cfeature.LAND,      facecolor="#1E2630", edgecolor="none")
    ax.add_feature(cfeature.BORDERS,   linewidth=0.4, edgecolor="#3C4043")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="#5F6368")

    if vcenter is not None:
        norm = mcolors.TwoSlopeNorm(vmin=vmin, vcenter=vcenter, vmax=vmax)
    else:
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    plot_data = np.ma.masked_invalid(data.values)
    im = ax.pcolormesh(
        data.lon.values, data.lat.values, plot_data,
        cmap=cmap, norm=norm, shading="nearest",
        transform=ccrs.PlateCarree(), zorder=2,
    )
    ax.add_feature(cfeature.BORDERS,   linewidth=0.4, edgecolor="#555555", zorder=3)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.6, edgecolor="#777777", zorder=3)

    # City markers
    if city_markers:
        for name, lat, lon in city_markers:
            ax.plot(lon, lat, "o", ms=7, color=C_ACC, markeredgecolor="white",
                    markeredgewidth=0.8, transform=ccrs.PlateCarree(), zorder=5)
            ax.text(lon + 0.4, lat + 0.4, name, fontsize=9, color=C_TEXT,
                    fontweight="bold", transform=ccrs.PlateCarree(), zorder=5)

    # ── Colorbar: numbers + unit only ──
    cax = fig.add_axes([0.15, 0.065, 0.70, 0.015])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend=cb_extend)
    cb.outline.set_edgecolor(C_LIGHT)
    span = vmax - vmin
    step = 1 if span <= 8 else (5 if span <= 30 else 10)
    clean_ticks = np.arange(int(np.ceil(vmin / step) * step),
                            int(np.floor(vmax)) + 1, step)
    cb.set_ticks(clean_ticks)
    cb.set_ticklabels([f"{int(t)}" for t in clean_ticks])
    cb.ax.tick_params(labelsize=10, colors=C_SUB, length=0)
    cax.set_facecolor(C_BG)
    # Unit label at the right end of colorbar
    fig.text(0.88, 0.065, cb_unit, fontsize=11, color=C_SUB, va="center",
             family="sans-serif")

    # ── Reference + context (small, bottom) ──
    fig.text(0.50, 0.032,
             "2024: Europe's hottest year on record (Copernicus ESOTC 2024)",
             fontsize=7.5, ha="center", color=C_SUB, family="sans-serif")
    fig.text(0.50, 0.012,
             "Data: CRU TS v4.09 (Harris et al. 2020) · E-OBS v32 (Cornes et al. 2018)",
             fontsize=6.5, ha="center", color=C_LIGHT, family="sans-serif")

    fig.savefig(filename, dpi=IG_DPI, facecolor=C_BG)
    plt.close(fig)
    print(f"  Saved {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Generate all maps
# ══════════════════════════════════════════════════════════════════════════════

print("\nStep 3: Generating maps …\n")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "axes.grid": False,
})

# Crop to Europe for the main maps
eu_data = shift.sel(lat=slice(34, 72), lon=slice(-25, 45))
eu_hot  = hot_change.sel(lat=slice(34, 72), lon=slice(-25, 45))

# ── Map 1: Europe Warming ──
make_map(
    data=eu_data,
    extent=[-13, 43, 34, 72],
    projection=ccrs.LambertConformal(central_longitude=10, central_latitude=50),
    title_big=f"+{eu_mean:.1f} °C",
    title_sub="Europe Is Warming",
    filename="map_europe_warming.png",
    vmin=-2, vmax=4, vcenter=0,
    city_markers=[
        ("Paris", 48.86, 2.35), ("Berlin", 52.52, 13.40),
        ("Madrid", 40.42, -3.70), ("Rome", 41.90, 12.50),
        ("Stockholm", 59.33, 18.07), ("Vienna", 48.21, 16.37),
    ],
)

# ── Map 2: Alps Zoom ──
alps_data = shift.sel(lat=slice(43.5, 48.5), lon=slice(4, 17))
alps_mean = float(alps_data.mean().values)
make_map(
    data=alps_data,
    extent=[4, 17, 43.5, 48.5],
    projection=ccrs.Mercator(),
    title_big=f"+{alps_mean:.1f} °C",
    title_sub="The Alps Are Heating Up",
    filename="map_alps_warming.png",
    cmap=WARM_SEQ_CMAP, vmin=0, vmax=3.5, vcenter=1.5,
    city_markers=[
        ("Zurich", 47.37, 8.54), ("Innsbruck", 47.26, 11.39),
        ("Milan", 45.46, 9.19), ("Munich", 48.14, 11.58),
        ("Geneva", 46.20, 6.14),
    ],
)

# ── Map 3: City zooms (Paris, Berlin, Madrid) ──
cities = [
    ("Paris", 48.86, 2.35, 5.0),
    ("Berlin", 52.52, 13.40, 5.0),
    ("Madrid", 40.42, -3.70, 5.5),
    ("Rome", 41.90, 12.50, 5.0),
    ("Vienna", 48.21, 16.37, 5.0),
]

for city_name, clat, clon, box_half in cities:
    city_data = shift.sel(
        lat=slice(clat - box_half, clat + box_half),
        lon=slice(clon - box_half, clon + box_half),
    )
    city_mean = float(city_data.mean().values)
    make_map(
        data=city_data,
        extent=[clon - box_half, clon + box_half,
                clat - box_half, clat + box_half],
        projection=ccrs.Mercator(),
        title_big=f"+{city_mean:.1f} °C",
        title_sub=f"{city_name}",
        filename=f"map_{city_name.lower()}_warming.png",
        cmap=WARM_SEQ_CMAP, vmin=0, vmax=3.5, vcenter=1.5,
        city_markers=[(city_name, clat, clon)],
    )

# ── Map 4: Extreme Heat Days (E-OBS daily, 0.25° resolution) ──
EOBS_HOT = DATA_DIR / "eobs_hot_days_30C.nc"
if EOBS_HOT.exists():
    hd = xr.open_dataset(EOBS_HOT)
    extra_days = hd["extra_hot_days"].sel(
        latitude=slice(34, 72), longitude=slice(-25, 45))
    eu_extra_mean = float(extra_days.mean().values)
    make_map(
        data=extra_days.rename({"latitude": "lat", "longitude": "lon"}),
        extent=[-13, 43, 34, 72],
        projection=ccrs.LambertConformal(central_longitude=10, central_latitude=50),
        title_big="30 °C+",
        title_sub="More Hot Days Each Summer",
        filename="map_extreme_heat_days.png",
        cmap=HEAT_CMAP,
        vmin=0, vmax=35, vcenter=None,
        cb_unit="days",
        cb_extend="max",
    )
else:
    print("  Skipping extreme heat map — E-OBS hot days file not found")

print(f"\nDone. Maps saved:")
for f in sorted(Path(".").glob("map_*.png")):
    print(f"  {f}")
