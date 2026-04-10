# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-10

### Added

#### Climate shift analysis (existing, ported into the repo)
- `plot_climate_shift.py` — GHCN station-based summer temperature shift analysis (1930-1959 vs 1995-2024) with bootstrap CIs and Welch's t-test
- `plot_climate_maps.py` — CRU TS / E-OBS gridded climate maps for Europe with Instagram-ready dark theme
- 45+ generated visualizations (carousels, slides, regional warming maps)

#### Glacier toolkit (new)
- **Package structure** — `glacier_toolkit/` with 5 modules: `acquire`, `analyze`, `visualize`, `glof`, `pipelines`
- **Global glacier registry** — 20 glaciers across all glaciated regions: Alaska, Greenland, Patagonia, Andes, European Alps, Norway, Iceland, Himalayas, Pamir, East Africa, Antarctica, New Zealand
- **Custom locations** — Analyze any glacier on Earth via `--lat` / `--lon` flags
- **Hemisphere-aware seasonality** — JJA (Northern), DJF (Southern), custom dry-season for tropical glaciers
- **Satellite acquisition**:
  - `acquire/landsat.py` — Landsat 5/7/8/9 via Google Earth Engine with cross-sensor harmonization (Roy et al. 2016)
  - `acquire/sentinel.py` — Sentinel-2 via Copernicus Data Space Ecosystem OData API
  - `acquire/glims.py` — GLIMS glacier boundaries from NSIDC (200,000+ glaciers)
  - `acquire/dem.py` — Copernicus DEM GLO-30 (free, global, 30m)
- **Analysis**:
  - `analyze/ndsi.py` — NDSI snow/ice classification (Dozier 1989) with connected-component filtering
  - `analyze/ndwi.py` — NDWI water body detection (McFeeters 1996) with proglacial lake filtering
  - `analyze/glacier_area.py` — Multi-temporal area change with bootstrap trend CIs
  - `analyze/lake_area.py` — Proglacial lake time series and growth rate
  - `analyze/statistics.py` — Bootstrap CIs (10k samples, seed=42), Mann-Kendall trend test, Welch's t-test, area uncertainty (Granshaw & Fountain 2006)
- **Visualization** (Instagram-ready, dark theme matching `plot_climate_shift.py`):
  - `visualize/ghost_ice.py` — "Ghost Ice" overlay showing where ice used to be
  - `visualize/comparison_maps.py` — Before/after side-by-side panels
  - `visualize/global_dashboard.py` — World map with all tracked glaciers
  - `visualize/timelapse.py` — Animated GIF generation
  - `visualize/carousel.py` — 4-slide Instagram carousel with auto-generated captions
- **GLOF risk assessment**:
  - `glof/lake_detection.py` — Automated glacial lake identification with dam-type classification (moraine/ice/bedrock)
  - `glof/lake_timeseries.py` — Growth rate analysis and volume estimation (Huggel et al. 2002 scaling)
  - `glof/proximity.py` — Downstream settlement exposure via D8 flow routing
  - `glof/risk_classify.py` — Multi-factor risk scoring (LOW / MODERATE / HIGH / VERY HIGH) with LaTeX-ready table export
- **Pipelines** (CLI entry points):
  - `pipelines/run_single_glacier.py` — `glacier-analyze --name aletsch`
  - `pipelines/run_global_overview.py` — `glacier-global` for the world dashboard
  - `pipelines/run_andes_glof.py` — `glacier-glof` for the Andes paper
  - `pipelines/run_social_post.py` — `glacier-social --name columbia`

#### Repository tooling
- `pyproject.toml` — Modern Python packaging with optional dependency groups (`geo`, `gee`, `dev`, `all`)
- `tests/` — 90 pytest tests covering config, statistics, NDSI, NDWI, GLOF, glacier area
- `.github/workflows/ci.yml` — Lint + format + type-check + test on Python 3.10/3.11/3.12
- `.github/workflows/codeql.yml` — Security scanning
- `.pre-commit-config.yaml` — Auto-format on commit
- `LICENSE` — MIT
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- GitHub issue templates (bug, feature, new glacier) and PR template
- `.editorconfig` for cross-editor consistency
- `docs/ARCHITECTURE.md` and `docs/QUICKSTART.md`

### Validated
- Columbia Glacier, Alaska — **−70.8% ice area loss** (1986 → 2024), trend −81.5 km²/year (R² = 0.818, n = 8 years)
- Generated 4-slide Instagram carousel + auto-caption end-to-end

[Unreleased]: https://github.com/bijanf/climate-shift/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bijanf/climate-shift/releases/tag/v0.1.0
