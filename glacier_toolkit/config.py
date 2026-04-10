"""
Global configuration for the Glacier Retreat Monitoring Toolkit.

Defines paths, visual theme tokens (matching the existing climate_shift project),
Instagram dimensions, and a registry of 18+ notable glaciers spanning every
glaciated region on Earth.
"""

from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# Paths
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # climate_shift/
TOOLKIT_ROOT = Path(__file__).resolve().parent  # glacier_toolkit/

DATA_DIR = PROJECT_ROOT / "glacier_data"
LANDSAT_DIR = DATA_DIR / "landsat"
SENTINEL_DIR = DATA_DIR / "sentinel"
GLIMS_DIR = DATA_DIR / "glims"
DEM_DIR = DATA_DIR / "dem"
OUTPUTS_DIR = DATA_DIR / "outputs"

OUTPUT_ROOT = PROJECT_ROOT / "glacier_outputs"
IG_OUT_DIR = OUTPUT_ROOT / "instagram"
PAPER_OUT_DIR = OUTPUT_ROOT / "paper"
GLOBAL_OUT_DIR = OUTPUT_ROOT / "global"

# Ensure directories exist on import
for d in (
    LANDSAT_DIR,
    SENTINEL_DIR,
    GLIMS_DIR,
    DEM_DIR,
    OUTPUTS_DIR,
    IG_OUT_DIR,
    PAPER_OUT_DIR,
    GLOBAL_OUT_DIR,
):
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# Dark theme design tokens (matching plot_climate_shift.py & plot_climate_maps.py)
# ══════════════════════════════════════════════════════════════════════════════

C_BG = "#0F1419"  # near-black background
C_TEXT = "#E8EAED"  # off-white text
C_SUB = "#9AA0A6"  # muted gray for subtitles
C_LIGHT = "#3C4043"  # subtle rules / dividers
C_ACC = "#FF6B6B"  # bright red-coral accent for headline numbers
C_COOL = "#5BA3E6"  # bright blue (historical)
C_WARM = "#EF5350"  # bright red (modern)
C_AMBER = "#FFA726"  # amber accent

# Glacier-specific colors
C_ICE = "#A8D8EA"  # light cyan for historical ice extent
C_ICE_GHOST = "#A8D8EA66"  # same but 40% alpha (hex RGBA) for ghost overlays
C_LAKE = "#1976D2"  # deep blue for glacial lakes
C_ROCK = "#5D4037"  # exposed bedrock brown
C_MELTWATER = "#0D47A1"  # dark blue for meltwater channels
C_LAND = "#1E2630"  # dark land fill (matching plot_climate_maps.py)

FONT_FAMILY = "sans-serif"
FONT_STACK = ["DejaVu Sans", "Helvetica", "Arial"]


# ══════════════════════════════════════════════════════════════════════════════
# Instagram slide dimensions (portrait 4:5, matching existing project)
# ══════════════════════════════════════════════════════════════════════════════

IG_W, IG_H = 1080, 1350
IG_DPI = 150
IG_FIG = (IG_W / IG_DPI, IG_H / IG_DPI)  # (7.2, 9.0) inches


# ══════════════════════════════════════════════════════════════════════════════
# Statistical defaults (matching plot_climate_shift.py)
# ══════════════════════════════════════════════════════════════════════════════

BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95


# ══════════════════════════════════════════════════════════════════════════════
# Seasonality definitions
# ══════════════════════════════════════════════════════════════════════════════

SEASON_NH_SUMMER = [6, 7, 8]  # June–August (Northern Hemisphere)
SEASON_SH_SUMMER = [12, 1, 2]  # December–February (Southern Hemisphere)
SEASON_TROPICAL_DRY = [6, 7, 8, 9]  # default dry season for tropical glaciers


# ══════════════════════════════════════════════════════════════════════════════
# Global Glacier Registry
# ══════════════════════════════════════════════════════════════════════════════
#
# Each entry:
#   name        – display name
#   region      – broad geographic region
#   lat, lon    – center coordinates (decimal degrees; south/west are negative)
#   bbox        – (west, south, east, north) bounding box for satellite queries
#   hemisphere  – "N", "S", or "tropical" (determines summer season)
#   season      – month list for annual composites (overrides hemisphere default)
#   notes       – why this glacier is notable / useful for the project

#
# terminus_type      – glacier terminus environment, controls retreat dynamics:
#                        "land"   – land-terminating, retreat dominated by climate
#                        "marine" – tidewater, retreat dominated by calving
#                        "lake"   – freshwater calving, mixed dynamics

GLACIER_REGISTRY = {
    # ── Alaska ────────────────────────────────────────────────────────────────
    "columbia": {
        "name": "Columbia Glacier",
        "region": "Alaska",
        "lat": 61.13,
        "lon": -147.08,
        "bbox": (-147.5, 60.9, -146.6, 61.4),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "marine",
        "notes": "Iconic 40-year retreat. Best Landsat archive. Lost >20 km since 1980.",
    },
    "mendenhall": {
        "name": "Mendenhall Glacier",
        "region": "Alaska",
        "lat": 58.43,
        "lon": -134.55,
        "bbox": (-134.8, 58.3, -134.3, 58.6),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "lake",
        "notes": "Near Juneau. Growing proglacial lake. Dramatic calving events.",
    },
    # ── Greenland ─────────────────────────────────────────────────────────────
    "jakobshavn": {
        "name": "Jakobshavn Isbræ (Sermeq Kujalleq)",
        "region": "Greenland",
        "lat": 69.17,
        "lon": -49.83,
        "bbox": (-50.5, 68.8, -49.0, 69.5),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "marine",
        "notes": "Fastest-flowing glacier on Earth. Enormous calving front retreat.",
    },
    # ── Patagonia ─────────────────────────────────────────────────────────────
    "grey": {
        "name": "Grey Glacier",
        "region": "Patagonia",
        "lat": -51.0,
        "lon": -73.2,
        "bbox": (-73.6, -51.3, -72.8, -50.7),
        "hemisphere": "S",
        "season": SEASON_SH_SUMMER,
        "terminus_type": "lake",
        "notes": "Torres del Paine. Dramatic calving into Lago Grey.",
    },
    "upsala": {
        "name": "Upsala Glacier",
        "region": "Patagonia",
        "lat": -49.88,
        "lon": -73.28,
        "bbox": (-73.7, -50.2, -72.8, -49.5),
        "hemisphere": "S",
        "season": SEASON_SH_SUMMER,
        "terminus_type": "lake",
        "notes": "One of the fastest-retreating glaciers in South America.",
    },
    # ── Andes (GLOF paper targets) ────────────────────────────────────────────
    "palcaraju": {
        "name": "Palcaraju Glacier / Lake Palcacocha",
        "region": "Andes (Cordillera Blanca)",
        "lat": -9.40,
        "lon": -77.38,
        "bbox": (-77.5, -9.5, -77.2, -9.3),
        "hemisphere": "tropical",
        "season": [5, 6, 7, 8, 9],  # dry season in Cordillera Blanca
        "terminus_type": "land",
        "notes": "GLOF paper target #1. Destroyed Huaraz in 1941. Lake still growing.",
    },
    "hualcan": {
        "name": "Hualcan Glacier / Lake 513",
        "region": "Andes (Cordillera Blanca)",
        "lat": -9.20,
        "lon": -77.55,
        "bbox": (-77.7, -9.3, -77.4, -9.1),
        "hemisphere": "tropical",
        "season": [5, 6, 7, 8, 9],
        "terminus_type": "land",
        "notes": "Active GLOF threat. Well-documented in literature.",
    },
    "pastoruri": {
        "name": "Pastoruri Glacier",
        "region": "Andes (Cordillera Blanca)",
        "lat": -9.93,
        "lon": -77.18,
        "bbox": (-77.3, -10.0, -77.1, -9.85),
        "hemisphere": "tropical",
        "season": [5, 6, 7, 8, 9],
        "terminus_type": "land",
        "notes": "Poster child of tropical glacier loss. Split in two ~2007.",
    },
    # ── European Alps ─────────────────────────────────────────────────────────
    "aletsch": {
        "name": "Aletsch Glacier",
        "region": "European Alps (Switzerland)",
        "lat": 46.45,
        "lon": 8.05,
        "bbox": (7.85, 46.35, 8.25, 46.55),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Largest Alpine glacier (~80 km²). UNESCO World Heritage.",
    },
    "pasterze": {
        "name": "Pasterze Glacier",
        "region": "European Alps (Austria)",
        "lat": 47.08,
        "lon": 12.70,
        "bbox": (12.55, 46.98, 12.85, 47.18),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Austria's largest glacier. Grossglockner. Accessible for fieldwork.",
    },
    "mer_de_glace": {
        "name": "Mer de Glace",
        "region": "European Alps (France)",
        "lat": 45.90,
        "lon": 6.93,
        "bbox": (6.80, 45.82, 7.06, 45.98),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Iconic. Near Chamonix. Powerful before/after potential.",
    },
    # ── Scandinavia ───────────────────────────────────────────────────────────
    "briksdalsbreen": {
        "name": "Briksdalsbreen",
        "region": "Norway",
        "lat": 61.65,
        "lon": 6.82,
        "bbox": (6.65, 61.55, 7.00, 61.75),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Dramatic outlet arm of Jostedalsbreen. Rapid terminus retreat.",
    },
    # ── Iceland ───────────────────────────────────────────────────────────────
    "breidamerkurjokull": {
        "name": "Breiðamerkurjökull",
        "region": "Iceland",
        "lat": 64.08,
        "lon": -16.33,
        "bbox": (-16.7, 63.9, -15.9, 64.3),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "lake",
        "notes": "Vatnajökull outlet. Feeds Jökulsárlón glacial lagoon.",
    },
    # ── Himalayas ─────────────────────────────────────────────────────────────
    "gangotri": {
        "name": "Gangotri Glacier",
        "region": "Himalayas (India)",
        "lat": 30.92,
        "lon": 79.08,
        "bbox": (78.85, 30.75, 79.30, 31.05),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Source of the Ganges. Retreating ~22 m/year. Cultural significance.",
    },
    "khumbu": {
        "name": "Khumbu Glacier",
        "region": "Himalayas (Nepal)",
        "lat": 27.98,
        "lon": 86.85,
        "bbox": (86.70, 27.88, 87.00, 28.08),
        "hemisphere": "N",
        "season": [10, 11, 12, 1, 2],  # post-monsoon + winter (clearest skies)
        "terminus_type": "land",
        "notes": "Everest region. GLOF risk from Imja Lake. Heavily studied.",
    },
    # ── Central Asia ──────────────────────────────────────────────────────────
    "fedchenko": {
        "name": "Fedchenko Glacier",
        "region": "Pamir Mountains (Tajikistan)",
        "lat": 38.85,
        "lon": 72.25,
        "bbox": (72.0, 38.6, 72.5, 39.1),
        "hemisphere": "N",
        "season": SEASON_NH_SUMMER,
        "terminus_type": "land",
        "notes": "Longest non-polar glacier (~77 km). Under-studied. Paper potential.",
    },
    # ── East Africa (extinction stories) ──────────────────────────────────────
    "lewis": {
        "name": "Lewis Glacier (Mt Kenya)",
        "region": "East Africa (Kenya)",
        "lat": -0.15,
        "lon": 37.32,
        "bbox": (37.28, -0.19, 37.36, -0.11),
        "hemisphere": "tropical",
        "season": [1, 2, 3],  # Jan–Mar dry season
        "terminus_type": "land",
        "notes": "Nearly gone. One of last equatorial glaciers. Extinction story.",
    },
    "furtwangler": {
        "name": "Furtwängler Glacier (Kilimanjaro)",
        "region": "East Africa (Tanzania)",
        "lat": -3.07,
        "lon": 37.35,
        "bbox": (37.30, -3.12, 37.40, -3.02),
        "hemisphere": "tropical",
        "season": [1, 2, 3],
        "terminus_type": "land",
        "notes": "Projected gone by ~2030. Most powerful visual of equatorial ice loss.",
    },
    # ── Antarctica ────────────────────────────────────────────────────────────
    "hektoria": {
        "name": "Hektoria Glacier",
        "region": "Antarctic Peninsula",
        "lat": -65.5,
        "lon": -62.0,
        "bbox": (-63.0, -66.0, -61.0, -65.0),
        "hemisphere": "S",
        "season": [12, 1, 2, 3],  # austral summer
        "terminus_type": "marine",
        "notes": "25 km retreat in 1 year (2022–23). Fastest grounded retreat ever.",
    },
    # ── New Zealand ───────────────────────────────────────────────────────────
    "franz_josef": {
        "name": "Franz Josef Glacier",
        "region": "New Zealand",
        "lat": -43.47,
        "lon": 170.18,
        "bbox": (170.05, -43.55, 170.30, -43.40),
        "hemisphere": "S",
        "season": SEASON_SH_SUMMER,
        "terminus_type": "land",
        "notes": "Dramatic advance-retreat cycles. Temperate maritime glacier.",
    },
}


def get_glacier(key):
    """Look up a glacier by registry key (case-insensitive)."""
    key = key.lower().strip()
    if key in GLACIER_REGISTRY:
        return GLACIER_REGISTRY[key]
    # Fuzzy match on name
    for v in GLACIER_REGISTRY.values():
        if key in v["name"].lower():
            return v
    raise KeyError(
        f"Glacier '{key}' not found in registry. Available: {', '.join(GLACIER_REGISTRY.keys())}"
    )


def make_custom_glacier(name, lat, lon, bbox_pad_deg=0.2, hemisphere=None, season=None):
    """Create a glacier config dict for any location not in the registry."""
    if hemisphere is None:
        if abs(lat) < 23.5:
            hemisphere = "tropical"
        elif lat >= 0:
            hemisphere = "N"
        else:
            hemisphere = "S"

    if season is None:
        season = {
            "N": SEASON_NH_SUMMER,
            "S": SEASON_SH_SUMMER,
            "tropical": SEASON_TROPICAL_DRY,
        }[hemisphere]

    return {
        "name": name,
        "region": "Custom",
        "lat": lat,
        "lon": lon,
        "bbox": (lon - bbox_pad_deg, lat - bbox_pad_deg, lon + bbox_pad_deg, lat + bbox_pad_deg),
        "hemisphere": hemisphere,
        "season": season,
        "notes": "User-defined glacier location.",
    }
