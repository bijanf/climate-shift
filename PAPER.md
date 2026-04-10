# Paper roadmap: Local warming explains global glacier retreat

> **Working title:** Local summer warming explains global glacier retreat for land-terminating glaciers but not for marine-terminating glaciers: an open-source satellite-climate analysis at scale.

**Status**: Phase 2 — Scaling to global (~200,000 glaciers)
**Author**: Bijan Fallah
**Target journal**: *Nature Geoscience*
**Backup journals**: *The Cryosphere*, *Geophysical Research Letters*, *Remote Sensing of Environment*

---

## 1. Scientific question

> **Does local summer maximum temperature, as measured by gridded climate observations, explain glacier retreat rate across the global glacier population, and how does this relationship vary by glacier terminus type, size, region, and elevation?**

Falsifiable hypotheses:

- **H₀**: Local warming rate at each glacier location is *not* significantly correlated with the local glacier area change rate.
- **H₁a**: For land-terminating glaciers, local warming rate is significantly correlated with retreat rate.
- **H₁b**: For marine and lake-terminating glaciers, local warming rate is *not* significantly correlated with retreat rate, because dynamic calving instability dominates over local climate forcing.

If we find no correlation overall but a strong correlation for land-terminating glaciers and no correlation for calving glaciers, that **dichotomy itself is the central paper finding** — it explains why prior global studies have produced inconsistent results.

---

## 2. Why this is novel

Three things make this paper unique:

1. **Per-glacier climate coupling at global scale**: Most glacier remote-sensing papers cite "global warming" generically. Most climate papers don't measure glacier impact directly. We compute the climate sensitivity of *every* glacier in the GLIMS database.

2. **Terminus-type stratification**: Prior studies pool calving and land glaciers, masking the dichotomy. We separate them.

3. **Open-source, reproducible pipeline**: Anyone can re-run the analysis from raw GLIMS + Landsat + CRU TS using our published toolkit. This is the highest standard of open science and reviewers will love it.

---

## 3. Data sources

| Dataset | Use | Source | Coverage |
|---|---|---|---|
| **GLIMS/current** | Glacier polygons | Google Earth Engine FeatureCollection | 786,906 outlines globally |
| **Landsat 5/7/8/9 SR** | NDSI computation | GEE `LANDSAT/LC0[5789]/C02/T1_L2` | 1984-present, 30m |
| **CRU TS v4.09** | Local climate (gridded T_max) | Harris et al. 2020 | 1901-2024, 0.5° global |
| **Hugonnet et al. 2021** (validation) | Per-glacier mass balance 2000-2019 | doi:10.6096/13 (SEDOO) | 217,175 glaciers |
| **18 case-study glaciers** | Methodology validation | this paper, Phase 1 | manually curated |

---

## 4. Methodology

### 4.1 Server-side GEE batch processing (Phase 2 — new)

Instead of downloading per-glacier GeoTIFFs, the production pipeline computes everything inside GEE using `ee.FeatureCollection.map()` and `ee.Reducer.sum()`. For each glacier polygon and each year:

1. Build the cloud-masked Landsat composite for the appropriate hemisphere season
2. Apply Roy et al. (2016) cross-sensor harmonization
3. Compute NDSI = (Green − SWIR1) / (Green + SWIR1)
4. Apply NDSI > 0.4 threshold (Dozier 1989) → binary ice mask
5. `reduceRegion(reducer=ee.Reducer.sum(), geometry=glacier_polygon)` → ice pixel count
6. Multiply by pixel area (30 m × 30 m) → glacier area in km² for that year

This produces a (n_glaciers × n_years) area matrix downloaded as a single CSV — no per-glacier raster downloads.

**Compute estimate**: ~200,000 glaciers × 40 years = 8M operations. With GEE's parallel infrastructure, this completes in hours, not weeks.

### 4.2 Local climate extraction (Phase 1 — already built)

For each glacier coordinate `(lat, lon)`:

1. Extract the 1° × 1° box (2 × 2 CRU TS cells) centered on the glacier
2. Compute the area-weighted mean of summer (or hemisphere-appropriate season) maximum temperature
3. Build the annual time series 1985-2024
4. Fit linear trend with bootstrap 95% CI

**Optimization for scale**: Group glaciers by CRU TS cell (resolution 0.5° → ~150,000 unique cells globally). Extract climate per *unique cell*, not per glacier — gives a ~10× speedup.

### 4.3 Climate-glacier coupling (Phase 1 — already built)

Per-glacier:
- Linear regression of area vs local T: slope = climate sensitivity (km²/°C)
- Bootstrap 95% CI on slope
- Statistical significance via Mann-Kendall and parametric tests

Cross-glacier:
- Pearson and Spearman correlation between warming rate and retreat rate
- Stratified by terminus type, region, size class, elevation
- OLS *and* Theil-Sen (robust) regression for sensitivity
- Multi-variate regression controlling for size, elevation, terminus

### 4.4 Validation (Phase 1 — already built, Phase 2 extension)

**Phase 1**: Six well-known reference glaciers (Aletsch, Pasterze, Mer de Glace, Gangotri, Khumbu, Columbia) validated against published areas to within ±15%.

**Phase 2**: Validate against Hugonnet et al. 2021 mass balance trends. For each glacier, our area trend should correlate with their mass balance trend (negative area trend ↔ negative mass balance).

### 4.5 Sensitivity analysis (already built)

7 methodology variants tested on the 18 case studies. Central finding (Spearman ρ = −0.85, p = 0.0002) is robust across all variants:

- ρ range: [−0.890, −0.676], mean = −0.810
- All variants p < 0.05
- All variants negative sign

---

## 5. Phase 1 (complete) → Phase 2 (in progress)

### Phase 1: Methodology validation (✓ done)

| Deliverable | Status |
|---|---|
| Open-source toolkit `glacier_toolkit/` | ✓ |
| 18 case-study glaciers analyzed | ✓ |
| GLIMS polygon clipping | ✓ |
| Climate-glacier coupling for 18 glaciers | ✓ |
| Terminus-type dichotomy discovered | ✓ |
| Sensitivity analysis (7 variants, all robust) | ✓ |
| Validation against published areas | ✓ |
| **Central finding**: Spearman ρ = −0.85 (p = 0.0002) for n = 13 land-terminating | ✓ |

### Phase 2: Scale to global (in progress)

| Deliverable | Target |
|---|---|
| Server-side GEE batch processor | ~3 days |
| Run on RGI region 11 (Central Europe, ~3,900 glaciers) | proof of concept |
| Run on RGI region 5 (Greenland Periphery, ~20,000 glaciers) | mid-scale |
| Run on all 19 RGI regions (~200,000 glaciers) | full global |
| Hugonnet 2021 validation cross-check | ~2 days |
| Hexbin density figures, regional summary boxplots | ~3 days |
| Multi-variate regression with size/elevation/region controls | ~3 days |
| **Central finding at global scale** | n ≈ 150,000 land-terminating |

### Phase 3: Paper writing (~2 months)

| Deliverable | Time |
|---|---|
| First draft (Abstract → Conclusion) | 4-6 weeks |
| Internal review + reference check | 2 weeks |
| Submit to *Nature Geoscience* | — |

---

## 6. Paper structure

### Abstract (250 words)
- Glaciers are retreating worldwide; the per-glacier climate sensitivity has not been measured systematically
- We built an open-source pipeline coupling gridded climate (CRU TS v4.09) to satellite-derived glacier areas (Landsat NDSI) for ~200,000 glaciers globally
- We find that local summer warming explains [X]% of variance in retreat rate for land-terminating glaciers (Spearman ρ = [Y], p < 10⁻⁵, n ≈ 150,000)
- Marine-terminating glaciers show no such relationship (ρ = [Z], p > 0.1, n ≈ 50,000), confirming that dynamic calving instability decouples them from local climate
- Implications: regional projections should treat the two types separately; global mean sensitivity is misleading

### 1. Introduction
- Glacier retreat is a leading indicator of climate change (cite IPCC AR6, Hugonnet 2021)
- Most studies use global mean temperature; few couple local climate to local retreat at scale
- Open-source toolkits accelerate science (Open Science movement)
- We build the first global, open-source, per-glacier climate-coupling pipeline

### 2. Data
- 2.1 GLIMS glacier polygons (NSIDC, 786k features)
- 2.2 Landsat 5/7/8/9 surface reflectance (USGS/NASA, 1984-present)
- 2.3 CRU TS v4.09 (Harris et al. 2020), 0.5° global
- 2.4 Hugonnet et al. 2021 mass balance (validation)
- 2.5 RGI v6.0 metadata for terminus-type and size classification

### 3. Methods
- 3.1 Server-side GEE batch processing (the technical innovation)
- 3.2 NDSI classification with cross-sensor harmonization (Roy et al. 2016)
- 3.3 Local climate aggregation by CRU TS cell
- 3.4 Per-glacier and cross-glacier statistics
- 3.5 Terminus type and size stratification
- 3.6 Validation against Hugonnet 2021

### 4. Results
- 4.1 Global glacier area trends (figure: world map with hexbin density)
- 4.2 Local warming rates (figure: world map with warming rates)
- 4.3 Per-glacier climate sensitivity distribution (figure: histogram)
- 4.4 Cross-glacier correlation by terminus type (figure: 2-panel scatter, like Phase 1)
- 4.5 Per-region statistics (table)
- 4.6 Multi-variate regression (controlling for size, elevation)
- 4.7 Hugonnet 2021 cross-validation (figure)
- 4.8 Sensitivity analysis showing robustness (figure: forest plot)

### 5. Discussion
- 5.1 The terminus-type dichotomy explains prior inconsistent global studies
- 5.2 Regional patterns: which regions are most temperature-sensitive?
- 5.3 Outliers and what they tell us (debris cover, surge-type, polar)
- 5.4 Comparison with Hugonnet 2021 and Zemp 2019
- 5.5 Limitations (CRU TS resolution, NDSI in shadow, debris cover)
- 5.6 Implications for projections: type-stratified climate sensitivity

### 6. Conclusion
- First open-source pipeline coupling gridded climate to satellite glacier areas at the global scale
- Local warming explains [X]% of variance for land-terminating glaciers, none for calving glaciers
- The per-glacier dataset is published for community use

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| GEE quota limits on 200k glacier batch | Tile by RGI region; use parallel exports |
| GLIMS polygon coverage gaps in polar regions | Document coverage per region; restrict global claim to covered regions |
| CRU TS too coarse for small alpine glaciers | Validate against ERA5 in supplement (~0.25°) |
| Debris-covered glaciers misclassified by NDSI | Stratify results by RGI debris-cover flag |
| Reviewers want ground-truth validation | Phase 1 case studies + Hugonnet 2021 cross-validation |
| Scoop risk | Phase 1 is publishable as a backup if scooped |

---

## 8. Open data and code policy

This paper will be **fully reproducible**:

- **Code**: `glacier_toolkit/` on GitHub at https://github.com/bijanf/climate-shift (MIT licensed)
- **Data inputs**: GLIMS (free), Landsat (USGS public domain), CRU TS (free)
- **Data outputs**: per-glacier results CSVs in the supplementary materials
- **Figures**: regenerable from `glacier-paper-global` CLI command
- **Manuscript LaTeX source**: `paper/` directory in this repo

Reviewers will be able to clone the repo and reproduce every figure and table.

---

## 9. Co-authors

- **Bijan Fallah** (lead, all sections)
- (TBD — solo first draft, invite collaborators after seeing the global data)

---

## See also

- [README](README.md) — project overview
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — toolkit design
- [CHANGELOG.md](CHANGELOG.md) — what's been built
