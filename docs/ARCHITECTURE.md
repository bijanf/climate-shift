# Architecture

This document describes how the glacier toolkit is organized and why.

## High-level data flow

```
              ┌──────────────────┐
              │  Glacier config  │   (registry or --lat/--lon)
              └────────┬─────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │ Landsat │    │Sentinel │    │  GLIMS  │
   │  (GEE)  │    │ (CDSE)  │    │ (NSIDC) │
   └────┬────┘    └────┬────┘    └────┬────┘
        │              │              │
        └──────┬───────┴──────────────┘
               │
               ▼
       ┌───────────────┐
       │  GeoTIFF/SHP  │   (cached in glacier_data/)
       └───────┬───────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
  ┌─────────┐     ┌──────────┐
  │  NDSI   │     │   NDWI   │
  │ (snow)  │     │  (water) │
  └────┬────┘     └────┬─────┘
       │               │
       ▼               ▼
  ┌─────────┐    ┌──────────┐
  │ Glacier │    │ Lake     │
  │  area   │    │ detect   │
  │ change  │    │ (GLOF)   │
  └────┬────┘    └────┬─────┘
       │              │
       ├──────┬───────┤
       │      │       │
       ▼      ▼       ▼
  ┌─────────┐ ┌───────────┐ ┌──────────┐
  │ Instagram│ │  Risk    │ │  Global  │
  │ carousel │ │  table   │ │ dashboard│
  └──────────┘ └──────────┘ └──────────┘
```

## Module structure

```
glacier_toolkit/
├── config.py             # Constants, theme, glacier registry (20 glaciers)
├── style.py              # Reusable dark-theme matplotlib helpers
│
├── acquire/              # Satellite & boundary data acquisition
│   ├── landsat.py        # Landsat 5/7/8/9 via Google Earth Engine
│   ├── sentinel.py       # Sentinel-2 via Copernicus Data Space Ecosystem
│   ├── glims.py          # Glacier outlines from NSIDC
│   └── dem.py            # Copernicus DEM GLO-30
│
├── analyze/              # Pure-function analysis modules
│   ├── ndsi.py           # Normalized Difference Snow Index
│   ├── ndwi.py           # Normalized Difference Water Index
│   ├── glacier_area.py   # Multi-temporal area change + trend fitting
│   ├── lake_area.py      # Proglacial lake time series
│   └── statistics.py     # Bootstrap CIs, Mann-Kendall, Welch's t-test
│
├── visualize/            # Instagram-ready dark theme visuals
│   ├── ghost_ice.py      # Translucent historical-extent overlay
│   ├── comparison_maps.py # Before/after side-by-side panels
│   ├── timelapse.py      # Multi-year animated frames + GIF
│   ├── global_dashboard.py # Robinson-projection world map
│   └── carousel.py       # 4-slide carousel + caption generator
│
├── glof/                 # Glacial Lake Outburst Flood risk
│   ├── lake_detection.py # Automated lake identification
│   ├── lake_timeseries.py # Growth rates + volume estimation
│   ├── proximity.py      # D8 flow routing for downstream zones
│   └── risk_classify.py  # Multi-factor risk scoring
│
└── pipelines/            # CLI entry points
    ├── run_single_glacier.py  # Analyze any glacier
    ├── run_global_overview.py # World dashboard
    ├── run_andes_glof.py      # GLOF paper pipeline
    └── run_social_post.py     # Quick Instagram content
```

## Design decisions

### Why Landsat first, Sentinel later?

Landsat provides 40 years of imagery (1984-present), giving us a multi-decade retreat record. Sentinel-2 only goes back to 2015 but offers 10m resolution. We build the full analysis on Landsat first for the temporal depth, then enhance with Sentinel for high-resolution recent visuals.

### Why CDSE direct API instead of `sentinelsat`?

`sentinelsat` targets the decommissioned Copernicus Open Access Hub. The Copernicus Data Space Ecosystem (CDSE) replaced it in 2023. We use the CDSE OData API directly via `requests` — about 200 lines of straightforward HTTP with OAuth2.

### Why raw `earthengine-api` instead of `geemap`?

`geemap` is great for Jupyter notebooks but pulls in heavy dependencies (`ipyleaflet`, `folium`, etc) and assumes interactive use. Our toolkit is script-based, so we use the raw `earthengine-api` directly.

### Cross-sensor harmonization

L5, L7, L8, and L9 have different spectral response functions. To produce a scientifically defensible 40-year time series, we apply Roy et al. 2016 harmonization coefficients in `acquire/landsat.py:HARMONIZATION_COEFFICIENTS` to convert L5/L7 reflectance to the L8 reference scale.

### Statistical consistency with the existing project

The bootstrap methodology (10,000 resamples, `seed=42`, percentile CIs) matches `plot_climate_shift.py:177-187` exactly. This ensures the climate shift and glacier projects produce comparable uncertainty estimates.

### Caching strategy

Every acquisition function checks for cached files before downloading, following the `ensure_data()` pattern from `plot_climate_maps.py:76-90`. Re-running analyses is free; only the first run hits the satellite APIs.

### Hemisphere-aware seasonality

Glacier area should be measured at the end of the melt season when seasonal snow is gone:

- **Northern Hemisphere**: JJA (June-August)
- **Southern Hemisphere**: DJF (December-February)
- **Tropical glaciers**: dry season per glacier (e.g. May-September for Cordillera Blanca, Jan-March for East Africa)

The registry encodes the correct season per glacier; custom locations get auto-detected based on latitude.

### Why pure functions in `analyze/`?

The `analyze/` modules accept NumPy arrays and return NumPy arrays. They have no I/O, no network calls, no side effects. This makes them:

- Easy to unit test (90 tests, no network required)
- Easy to compose (chain into custom pipelines)
- Easy to parallelize (no shared state)

The pipelines under `pipelines/` are where I/O lives.

## Statistical methods

| Method | Source | Where used |
|--------|--------|------------|
| NDSI | Dozier 1989 | `analyze/ndsi.py` |
| NDWI | McFeeters 1996 | `analyze/ndwi.py` |
| Cross-sensor harmonization | Roy et al. 2016 | `acquire/landsat.py` |
| Bootstrap CI (percentile) | Efron & Tibshirani 1993 | `analyze/statistics.py` |
| Mann-Kendall trend test | Kendall 1948 | `analyze/statistics.py` |
| Welch's t-test | Welch 1947 | `analyze/statistics.py` |
| Area uncertainty (boundary pixel) | Granshaw & Fountain 2006 | `analyze/ndsi.py` |
| Lake volume scaling | Huggel et al. 2002 | `glof/lake_timeseries.py` |
| GLOF dam classification | Emmer & Vilimek 2013 | `glof/lake_detection.py` |

## Extension points

### Adding a new acquisition source

Add a new module under `acquire/`. Convention:
- Lazy-import heavy dependencies inside functions
- Cache downloads to `glacier_data/<source>/`
- Return paths to local files (not raw data)

### Adding a new analysis method

Add a pure function under `analyze/`. Convention:
- Accept NumPy arrays as input
- Return NumPy arrays or simple dicts
- No file I/O, no network
- Add a corresponding `tests/test_<module>.py`

### Adding a new visualization

Add a new module under `visualize/`. Convention:
- Use the dark theme constants from `config.py`
- Use `style.add_title_zone()`, `style.add_source_line()` for consistency
- Output to `glacier_outputs/<category>/` (instagram/paper/global)
- Default to 1080x1350 @ 150 DPI for Instagram

### Adding a new pipeline

Add a CLI script under `pipelines/`. Convention:
- Use `argparse` for arguments
- Wrap business logic in `main()`
- Register in `pyproject.toml` under `[project.scripts]`
- Cache intermediate results to `glacier_data/outputs/<glacier>/`
