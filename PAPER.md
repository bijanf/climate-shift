# Paper roadmap: Local warming explains global glacier retreat

> **Working title:** Local warming explains global glacier retreat: a unified satellite-climate analysis of 20 glaciers across 12 regions, 1985-2024

**Status**: Phase 1 — Building infrastructure
**Author**: Bijan Fallah
**Target journal**: *The Cryosphere* (Copernicus, open access, no APC)
**Backup journal**: *Remote Sensing* (MDPI, open access, fast review)

---

## 1. Scientific question

> **Does local annual maximum summer temperature, as measured by gridded climate observations, explain the rate of glacier retreat at each site, across 12 climatically distinct regions of the world?**

Falsifiable hypothesis:

- **H₀**: Local warming rate at each glacier location is *not* significantly correlated with the local glacier retreat rate.
- **H₁**: Local warming rate is significantly correlated with retreat rate, with a robust climate sensitivity (km² lost per °C of local warming) that varies systematically by glacier type and region.

If we find no correlation, that itself is publishable: it would mean global temperature drives global retreat but local effects (precipitation, debris cover, geometry, ice flow) decouple the local relationship. Either result is interesting.

---

## 2. Why this is novel

Most glacier remote-sensing papers cite "global warming" generically. Most climate papers don't measure glacier impact directly. **This project uniquely has both datasets in one open-source pipeline:**

| Existing in this repo | What it gives us |
|---|---|
| `plot_climate_maps.py` + CRU TS v4.09 | 1901-2024 global gridded temperature at 0.5° |
| `glacier_toolkit/` + Google Earth Engine | 1985-2024 satellite-derived glacier areas globally |
| Both together | First open-source pipeline coupling gridded climate to satellite glacier retreat at the per-glacier scale |

The methodological contribution is the **unified pipeline**. The scientific contribution is the **per-region climate sensitivity** numbers.

---

## 3. Methodology

### 3.1 Glacier area time series (already built)

For each of 20 glaciers in `glacier_toolkit/config.py:GLACIER_REGISTRY`:

1. Download Landsat 5/7/8/9 surface reflectance from Google Earth Engine for each summer (or hemisphere-appropriate dry season) from 1985 to 2024
2. Apply Roy et al. (2016) cross-sensor harmonization coefficients to L5/L7 → L8 reference
3. Compute median annual NDSI composite from cloud-masked scenes
4. Classify glacier ice with NDSI > 0.4 (Dozier 1989) plus connected-component filtering (min 0.01 km²)
5. Compute glacier area and Granshaw & Fountain (2006) boundary uncertainty
6. Validated for Columbia Glacier (Alaska): −70.8% loss 1986-2024, R² = 0.818, MK p < 0.001

### 3.2 Local climate time series (new — `analyze/climate_link.py`)

For each glacier coordinate `(lat, lon)`:

1. Extract a 1° × 1° box (2 × 2 CRU TS cells) centered on the glacier
2. Compute area-weighted mean of summer (or local melt-season) maximum temperature
3. Build annual time series 1985-2024
4. Fit linear trend with 10,000-sample bootstrap 95% CI
5. Mann-Kendall trend significance test

### 3.3 Climate-glacier coupling (new — `analyze/correlation.py`)

For each glacier:

1. Pearson and Spearman correlation between glacier area and local mean summer max temperature, year by year
2. Linear regression: `area_km² = α + β · T_local` where β is the **climate sensitivity in km² per °C**
3. Bootstrap CI on β
4. Statistical significance test

For all glaciers together:

1. Cross-glacier regression: warming rate (°C/decade) vs retreat rate (km²/year)
2. Per-region statistics (mean retreat, mean warming, mean sensitivity)
3. Identify outliers (glaciers with anomalous sensitivity — these become discussion points)

### 3.4 Validation (new — `validate/glims_validation.py`)

For 5-10 well-studied reference glaciers (Columbia, Aletsch, Mer de Glace, Pasterze, Gangotri, Khumbu):

1. Compare our computed areas in years where GLIMS has published outlines
2. Compute RMSE and bias
3. Document expected accuracy: ±5% for clean glaciers, ±15% for debris-covered

### 3.5 Sensitivity analysis (new)

To show robustness of the main results:

1. **NDSI threshold**: re-run with thresholds 0.35, 0.40, 0.45 — does the sensitivity β change?
2. **Compositing window**: re-run with single-year vs 3-year rolling composites
3. **Climate aggregation**: re-run with single nearest cell vs 1° box vs 2° box
4. **Trend fitting**: re-run with OLS vs Theil-Sen vs LOESS

A paper that survives all four sensitivity tests is publishable.

---

## 4. Deliverables for the paper

| # | Deliverable | Source | Status |
|---|---|---|---|
| **D1** | Glacier area time series for 20 glaciers, 1985-2024 | `pipelines/run_paper.py` | 1/20 done |
| **D2** | Local temperature time series for 20 glacier locations | `analyze/climate_link.py` | not started |
| **D3** | Per-glacier climate sensitivity (km²/°C) with CIs | `analyze/correlation.py` | not started |
| **D4** | Cross-region correlation analysis | `analyze/correlation.py` | not started |
| **D5** | GLIMS validation table for 5+ reference glaciers | `validate/glims_validation.py` | not started |
| **D6** | Multi-panel paper figures (publication quality) | `visualize/paper_figures.py` | not started |
| **D7** | Sensitivity analysis showing robustness | sensitivity script | not started |
| **D8** | Methods + results + discussion text | manual | not started |

---

## 5. Paper structure

### Abstract (250 words)

One paragraph on each of:
- Motivation (global glacier retreat, missing local-climate link)
- Methodology (open pipeline, 20 glaciers, 12 regions, 1985-2024, satellite + CRU TS)
- Result (climate sensitivity = X km² per °C, range Y-Z, R² = W)
- Implication (open methodology, reproducible, applicable to any glacier)

### 1. Introduction

- Glaciers are retreating worldwide (cite IPCC AR6, Hugonnet et al. 2021)
- Most studies use global mean temperature; few couple local climate to local retreat
- Open-source toolkits accelerate science (cite Open Science movement)
- We build the first unified open pipeline and apply it to 20 glaciers

### 2. Data

- 2.1 Satellite imagery: Landsat 5/7/8/9 via Google Earth Engine (1984-present)
- 2.2 Climate: CRU TS v4.09 (Harris et al. 2020), 0.5° gridded, 1901-2024
- 2.3 Reference glacier outlines: GLIMS (NSIDC)
- 2.4 Glacier registry: 20 glaciers, 12 regions (table)

### 3. Methods

- 3.1 Glacier area extraction (NDSI, Roy et al. 2016 harmonization)
- 3.2 Local climate aggregation (1° box, bootstrap CIs)
- 3.3 Statistical analysis (Pearson, Spearman, linear regression, Mann-Kendall)
- 3.4 Validation against GLIMS reference outlines
- 3.5 Open-source toolkit availability and reproducibility

### 4. Results

- 4.1 Glacier area time series (figure: 20-panel grid, time series with trend)
- 4.2 Local warming rates (figure: world map with warming rates as colors)
- 4.3 Climate-glacier correlations (figure: scatter plot, retreat rate vs warming rate)
- 4.4 Per-region climate sensitivity (table)
- 4.5 GLIMS validation (table)
- 4.6 Sensitivity analysis (figure: how β changes with NDSI threshold etc)

### 5. Discussion

- 5.1 Climate sensitivity by region (which regions are most sensitive?)
- 5.2 Outliers (debris-covered, calving, surge-type glaciers)
- 5.3 Comparison with published global studies (Hugonnet 2021, Zemp 2019, etc)
- 5.4 Limitations (CRU TS spatial resolution, NDSI in shadow, debris cover)
- 5.5 Implications for projecting future glacier loss under different warming scenarios

### 6. Conclusion

- We built the first open-source pipeline coupling gridded climate to satellite glacier areas
- Local warming explains X% of variance in retreat rate across 20 glaciers
- The toolkit and data are freely available for any glacier on Earth
- Future work: incorporate ERA5, debris-covered ice ML refinement, ground-truth campaigns

---

## 6. Milestones and timeline

| Phase | Milestone | Deliverable | Target |
|---|---|---|---|
| **1** | Build infrastructure | climate_link, correlation, validation, paper_figures, run_paper | 1 week |
| **2** | Run all 20 glaciers | Complete D1 (time series CSVs) | 2 weeks (background) |
| **3** | Statistical analysis | D2-D5 (sensitivities, correlations, validation table) | 1 week |
| **4** | Sensitivity analysis | D7 (robustness across NDSI thresholds, etc) | 1 week |
| **5** | Generate paper figures | D6 (final publication-quality figures) | 1 week |
| **6** | Write manuscript | D8 (full text, BibTeX) | 3 weeks |
| **7** | Internal review | Self-review + colleague review | 1 week |
| **8** | Submit to *The Cryosphere* | Submission package | — |
| **9** | Address reviewer comments | Revisions | 2 months |
| **10** | Publish | DOI! | — |

**Total time to submission: ~10 weeks** with focused weekend work.

---

## 7. Success criteria

The paper is successful if **any one** of the following holds:

1. **Strong positive result**: Climate sensitivity is statistically significant for most glaciers (β with p < 0.05 for ≥15 of 20 glaciers), with a clear regional pattern
2. **Weak positive result**: Cross-glacier regression shows significant correlation between warming rate and retreat rate (p < 0.05)
3. **Negative result with insight**: No simple climate-glacier coupling, but the analysis reveals what *does* explain retreat (precipitation, geometry, debris, calving)

All three are publishable in *The Cryosphere*. Result #1 is the strongest. Result #3 is the most scientifically interesting if it's well-argued.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| GEE downloads fail for some years/glaciers | Multi-year compositing fallback; document exclusions |
| CRU TS too coarse for small alpine glaciers | Validate against ERA5 in supplement; use 1° box average |
| Debris-covered glaciers misclassified by NDSI | Document limitation; exclude from main analysis or use HED-UNet ML mask |
| Reviewers want ground-truth validation | We have published GLIMS areas as reference; mention drone fieldwork as future work |
| Scoop risk (someone else publishes first) | This specific multi-region open-pipeline approach has not been published; act fast |

---

## 9. Open data and code policy

This paper will be **fully reproducible**:

- Code: `glacier_toolkit/` on GitHub at https://github.com/bijanf/climate-shift
- Data inputs: Landsat (USGS public domain), CRU TS (free, attribution), GLIMS (free)
- Data outputs: CSVs and JSON in `glacier_data/outputs/`
- Figures: regenerable from `pipelines/run_paper.py`
- Manuscript LaTeX source: `paper/` directory in this repo

Reviewers will be able to run `glacier-paper` and reproduce every figure and table.

---

## 10. Co-authors

- **Bijan Fallah** (lead, all sections)
- (TBD — solo first draft, invite collaborators after seeing the data)

---

## See also

- [README](README.md) — project overview
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — toolkit design
- [docs/QUICKSTART.md](docs/QUICKSTART.md) — running the pipeline
- [CHANGELOG.md](CHANGELOG.md) — what's been built
