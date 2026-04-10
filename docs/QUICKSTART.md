# Quickstart — 5 minutes to your first glacier analysis

This guide gets you from zero to a published Instagram-ready glacier retreat slide in five minutes.

## 1. Install

```bash
git clone https://github.com/bijanf/climate-shift.git
cd climate-shift

# Install with all dependencies
pip install -e ".[geo,gee]"
```

If you only want the glacier toolkit (no satellite acquisition):

```bash
pip install -e ".[geo]"
```

## 2. Authenticate Google Earth Engine (one-time)

GEE is free for research and non-commercial use. Sign up at [earthengine.google.com](https://earthengine.google.com/signup/), then:

```bash
earthengine authenticate
```

This opens a browser for OAuth and stores credentials locally. You only need to do this once.

## 3. Analyze your first glacier

```bash
# Run the full pipeline on Columbia Glacier, Alaska (most dramatic 40-year retreat)
python -m glacier_toolkit.pipelines.run_single_glacier --name columbia
```

Or use the installed CLI command:

```bash
glacier-analyze --name columbia
```

This will:

1. **Download** Landsat NDSI composites from Google Earth Engine for 1985-2024 (cached locally)
2. **Compute** the glacier area time series with statistical uncertainty
3. **Fit** a linear trend with 10,000-sample bootstrap 95% CI
4. **Test** for significance with the Mann-Kendall trend test
5. **Generate** four Instagram-ready slides:
   - Ghost Ice overlay (signature visual)
   - Before/After comparison
   - Time series chart with trend line
   - Methodology + sources
6. **Auto-generate** an Instagram caption with hashtags

Output goes to `glacier_outputs/instagram/`.

## 4. Try other glaciers

```bash
# European Alps — accessible for fieldwork
glacier-analyze --name aletsch
glacier-analyze --name pasterze
glacier-analyze --name mer_de_glace

# Patagonia — dramatic calving
glacier-analyze --name grey
glacier-analyze --name upsala

# Himalayas — Source of the Ganges
glacier-analyze --name gangotri

# East Africa — extinction stories
glacier-analyze --name lewis        # Mt Kenya
glacier-analyze --name furtwangler  # Kilimanjaro

# Antarctica — fastest grounded retreat ever recorded
glacier-analyze --name hektoria
```

See the full registry: `python -c "from glacier_toolkit.config import GLACIER_REGISTRY; [print(f'{k:25s} {v[\"name\"]}') for k, v in GLACIER_REGISTRY.items()]"`

## 5. Analyze ANY glacier on Earth

For glaciers not in the built-in registry, pass coordinates:

```bash
glacier-analyze --lat -13.95 --lon -70.83 --glacier-name "Quelccaya Ice Cap"
```

The toolkit auto-detects the hemisphere and picks an appropriate season for the satellite composites.

## 6. Generate the global dashboard

After analyzing several glaciers:

```bash
glacier-global
```

This produces a Robinson-projection world map showing all tracked glaciers colored by percentage area lost.

## 7. Run the GLOF risk assessment

For the scientific paper pipeline (Andes targets):

```bash
glacier-glof
```

This analyzes Lake Palcacocha, Lake 513, and Pastoruri, producing a LaTeX-ready risk assessment table.

## What you should see

After step 3 you should have, in `glacier_outputs/instagram/`:

```
ghost_ice_columbia_glacier,_alaska_1986_2024.png
comparison_columbia_glacier,_alaska_1986_2024.png
timeseries_columbia_glacier,_alaska.png
methodology_columbia_glacier,_alaska.png
columbia_caption.txt
```

And the analysis CSV in `glacier_data/outputs/columbia_glacier/`:

```
area_timeseries.csv
analysis_results.json
```

## Troubleshooting

### "No cloud-free scenes for YYYY"

Some years (especially in Alaska, Iceland, Patagonia) have persistent cloud cover. The toolkit automatically falls back to other Landsat sensors for that year, but if all fail you'll see a warning. The analysis continues with the available years.

### "Google Earth Engine not authenticated"

Run `earthengine authenticate` once to set up credentials.

### "ModuleNotFoundError: No module named 'rioxarray'"

Install the geo extras: `pip install -e ".[geo]"`

### Tests fail with import errors

Install dev dependencies: `pip install -e ".[dev]"`

## Next steps

- Read [Architecture](ARCHITECTURE.md) to understand the module layout
- Browse the [tests](https://github.com/bijanf/climate-shift/tree/main/tests) for usage examples
- See [Contributing](contributing.md) to add new glaciers or features
