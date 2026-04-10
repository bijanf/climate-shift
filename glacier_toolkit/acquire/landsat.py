"""
Landsat satellite imagery acquisition via Google Earth Engine.

Supports Landsat 5 (1984–2012), 7 (1999–present), 8 (2013–present),
and 9 (2021–present) for 40+ years of glacier retreat analysis.

Requires a Google Earth Engine account (free for research/non-commercial):
  https://earthengine.google.com/signup/

First-time setup:
  pip install earthengine-api
  earthengine authenticate
"""

import warnings
from pathlib import Path

from ..config import LANDSAT_DIR

# ══════════════════════════════════════════════════════════════════════════════
# GEE initialization
# ══════════════════════════════════════════════════════════════════════════════

_ee = None  # lazy-loaded earth engine module


def _get_ee():
    """Lazy-import and initialize the Earth Engine API."""
    global _ee
    if _ee is not None:
        return _ee

    try:
        import ee
    except ImportError:
        raise ImportError(
            "Google Earth Engine API not installed. Run:\n"
            "  pip install earthengine-api\n"
            "  earthengine authenticate"
        )

    try:
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
    except Exception:
        print("  GEE not authenticated. Running ee.Authenticate() ...")
        ee.Authenticate()
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")

    _ee = ee
    print("  Google Earth Engine initialized.")
    return ee


# ══════════════════════════════════════════════════════════════════════════════
# Landsat collection definitions
# ══════════════════════════════════════════════════════════════════════════════

# Collection IDs and band mappings for each Landsat sensor
LANDSAT_COLLECTIONS = {
    "L5": {
        "collection": "LANDSAT/LT05/C02/T1_L2",
        "green": "SR_B2",
        "red": "SR_B3",
        "nir": "SR_B4",
        "swir1": "SR_B5",
        "swir2": "SR_B7",
        "qa": "QA_PIXEL",
        "scale_factor": 0.0000275,
        "scale_offset": -0.2,
        "years": (1984, 2012),
    },
    "L7": {
        "collection": "LANDSAT/LE07/C02/T1_L2",
        "green": "SR_B2",
        "red": "SR_B3",
        "nir": "SR_B4",
        "swir1": "SR_B5",
        "swir2": "SR_B7",
        "qa": "QA_PIXEL",
        "scale_factor": 0.0000275,
        "scale_offset": -0.2,
        "years": (1999, 2024),
    },
    "L8": {
        "collection": "LANDSAT/LC08/C02/T1_L2",
        "green": "SR_B3",
        "red": "SR_B4",
        "nir": "SR_B5",
        "swir1": "SR_B6",
        "swir2": "SR_B7",
        "qa": "QA_PIXEL",
        "scale_factor": 0.0000275,
        "scale_offset": -0.2,
        "years": (2013, 2026),
    },
    "L9": {
        "collection": "LANDSAT/LC09/C02/T1_L2",
        "green": "SR_B3",
        "red": "SR_B4",
        "nir": "SR_B5",
        "swir1": "SR_B6",
        "swir2": "SR_B7",
        "qa": "QA_PIXEL",
        "scale_factor": 0.0000275,
        "scale_offset": -0.2,
        "years": (2021, 2026),
    },
}

# Cross-sensor harmonization coefficients (L5/L7 → L8 reference)
# Source: Roy et al. 2016, "Characterization of Landsat-7 to Landsat-8
# reflective wavelength and normalized difference vegetation index continuity"
HARMONIZATION_COEFFICIENTS = {
    "green": {"slope": 0.9785, "intercept": -0.0095},
    "red": {"slope": 0.9785, "intercept": -0.0016},
    "nir": {"slope": 0.9833, "intercept": -0.0012},
    "swir1": {"slope": 0.9088, "intercept": 0.0003},
    "swir2": {"slope": 0.9103, "intercept": -0.0015},
}


# ══════════════════════════════════════════════════════════════════════════════
# Cloud masking
# ══════════════════════════════════════════════════════════════════════════════


def _mask_clouds_landsat(image):
    """Apply QA_PIXEL cloud/shadow mask to a Landsat image."""
    _get_ee()  # ensure GEE is initialized
    qa = image.select("QA_PIXEL")
    # Bit 3 = cloud shadow, Bit 4 = cloud
    cloud_shadow = qa.bitwiseAnd(1 << 3).eq(0)
    cloud = qa.bitwiseAnd(1 << 4).eq(0)
    return image.updateMask(cloud_shadow).updateMask(cloud)


def _apply_scale_factors(image, sensor_key):
    """Apply Collection 2 scale factors to convert to surface reflectance."""
    _get_ee()  # ensure GEE is initialized
    info = LANDSAT_COLLECTIONS[sensor_key]
    sf = info["scale_factor"]
    off = info["scale_offset"]

    optical_bands = [info["green"], info["red"], info["nir"], info["swir1"], info["swir2"]]
    scaled = image.select(optical_bands).multiply(sf).add(off)
    return image.addBands(scaled, overwrite=True)


def _harmonize_to_l8(image, sensor_key):
    """Harmonize L5/L7 surface reflectance to L8 reference.

    Uses Roy et al. 2016 coefficients so NDSI values are comparable
    across the 40-year Landsat record.
    """
    if sensor_key in ("L8", "L9"):
        return image  # already L8-compatible

    _get_ee()  # ensure GEE is initialized
    info = LANDSAT_COLLECTIONS[sensor_key]

    for band_key in ("green", "red", "nir", "swir1", "swir2"):
        band_name = info[band_key]
        coeff = HARMONIZATION_COEFFICIENTS[band_key]
        harmonized = (
            image.select(band_name)
            .multiply(coeff["slope"])
            .add(coeff["intercept"])
            .rename(band_name)
        )
        image = image.addBands(harmonized, overwrite=True)

    return image


# ══════════════════════════════════════════════════════════════════════════════
# Collection building
# ══════════════════════════════════════════════════════════════════════════════


def _best_sensor_for_year(year):
    """Pick the best Landsat sensor available for a given year."""
    if year >= 2021:
        return "L9"
    elif year >= 2013:
        return "L8"
    elif year >= 1999:
        return "L7"
    elif year >= 1984:
        return "L5"
    else:
        raise ValueError(f"No Landsat data before 1984 (requested {year})")


def _fallback_sensors_for_year(year):
    """Return list of sensors to try in order for a given year."""
    sensors = []
    if year >= 2021:
        sensors.extend(["L9", "L8"])
    if 2013 <= year <= 2024 and "L8" not in sensors:
        sensors.append("L8")
    if 1999 <= year <= 2024:
        sensors.append("L7")
    if 1984 <= year <= 2012:
        sensors.append("L5")
    return sensors if sensors else ["L8"]


def get_collection(bbox, year, season_months, sensor_key=None, cloud_cover_max=50):
    """Get a cloud-masked, harmonized Landsat collection for one season.

    Parameters
    ----------
    bbox : tuple
        (west, south, east, north) bounding box in degrees.
    year : int
        Target year.
    season_months : list of int
        Months to include (e.g. [6, 7, 8] for Northern Hemisphere summer).
    sensor_key : str, optional
        Force a specific sensor ("L5", "L7", "L8", "L9"). Auto-selects if None.
    cloud_cover_max : int
        Max scene-level cloud cover percentage.

    Returns
    -------
    ee.ImageCollection
        Cloud-masked, scaled, harmonized Landsat images.
    """
    ee = _get_ee()

    if sensor_key is None:
        sensor_key = _best_sensor_for_year(year)

    info = LANDSAT_COLLECTIONS[sensor_key]
    w, s, e, n = bbox
    aoi = ee.Geometry.Rectangle([w, s, e, n])

    # Handle seasons that cross year boundary (e.g. DJF for SH)
    if any(m <= 2 for m in season_months) and any(m >= 10 for m in season_months):
        # Southern Hemisphere: Dec of previous year through Feb of this year
        start_date = f"{year - 1}-{min(m for m in season_months if m >= 10):02d}-01"
        end_date = f"{year}-{max(m for m in season_months if m <= 6):02d}-28"
    else:
        start_date = f"{year}-{min(season_months):02d}-01"
        end_month = max(season_months)
        end_date = f"{year}-{end_month:02d}-28" if end_month < 12 else f"{year}-12-31"

    collection = (
        ee.ImageCollection(info["collection"])
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", cloud_cover_max))
    )

    # Apply processing chain
    collection = (
        collection.map(lambda img: _apply_scale_factors(img, sensor_key))
        .map(_mask_clouds_landsat)
        .map(lambda img: _harmonize_to_l8(img, sensor_key))
    )

    return collection


def compute_annual_composite(bbox, year, season_months, sensor_key=None, bands=None):
    """Create a cloud-free median composite for one summer season.

    Parameters
    ----------
    bbox : tuple
        (west, south, east, north).
    year : int
    season_months : list of int
    sensor_key : str, optional
    bands : list of str, optional
        Band names to include. Defaults to green, red, nir, swir1, swir2.

    Returns
    -------
    ee.Image
        Median composite with standardized band names:
        'green', 'red', 'nir', 'swir1', 'swir2'.
    """
    _get_ee()  # ensure GEE is initialized

    if sensor_key is None:
        sensor_key = _best_sensor_for_year(year)
    info = LANDSAT_COLLECTIONS[sensor_key]

    collection = get_collection(bbox, year, season_months, sensor_key)

    # Check if collection has images
    n_images = collection.size().getInfo()
    if n_images == 0:
        raise ValueError(f"No cloud-free scenes for {year} (season {season_months})")

    # Select and rename to standard names
    original_bands = [info["green"], info["red"], info["nir"], info["swir1"], info["swir2"]]
    standard_names = ["green", "red", "nir", "swir1", "swir2"]

    composite = collection.select(original_bands, standard_names).median()

    if bands:
        composite = composite.select(bands)

    return composite


def compute_ndsi(composite):
    """Compute NDSI from a standardized Landsat composite.

    NDSI = (green - swir1) / (green + swir1)
    Values > 0.4 indicate snow/ice (Dozier 1989).

    Parameters
    ----------
    composite : ee.Image
        Must have 'green' and 'swir1' bands.

    Returns
    -------
    ee.Image
        Single-band image named 'ndsi', range [-1, 1].
    """
    return composite.normalizedDifference(["green", "swir1"]).rename("ndsi")


def compute_ndwi(composite):
    """Compute NDWI from a standardized Landsat composite.

    NDWI = (green - nir) / (green + nir)
    Values > 0.3 indicate water (McFeeters 1996).

    Parameters
    ----------
    composite : ee.Image
        Must have 'green' and 'nir' bands.

    Returns
    -------
    ee.Image
        Single-band image named 'ndwi', range [-1, 1].
    """
    return composite.normalizedDifference(["green", "nir"]).rename("ndwi")


def export_to_geotiff(image, bbox, output_path, scale=30, crs="EPSG:4326"):
    """Export a GEE image to a local GeoTIFF file.

    Uses getDownloadURL for small regions or ee.batch.Export for large ones.

    Parameters
    ----------
    image : ee.Image
        The image to export.
    bbox : tuple
        (west, south, east, north).
    output_path : str or Path
        Local path for the output GeoTIFF.
    scale : int
        Resolution in meters (30 for Landsat).
    crs : str
        Output coordinate reference system.

    Returns
    -------
    Path
        Path to the saved GeoTIFF.
    """
    ee = _get_ee()
    import requests

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    w, s, e, n = bbox
    region = ee.Geometry.Rectangle([w, s, e, n])

    url = image.getDownloadURL(
        {
            "scale": scale,
            "crs": crs,
            "region": region.getInfo()["coordinates"],
            "format": "GEO_TIFF",
            "filePerBand": False,
        }
    )

    print(f"  Downloading GeoTIFF: {output_path.name} ...")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(resp.content)

    print(f"  Saved: {output_path}")
    return output_path


def export_annual_ndsi(glacier_config, year, output_dir=None):
    """Export an annual NDSI GeoTIFF for a glacier.

    Parameters
    ----------
    glacier_config : dict
        Glacier entry from GLACIER_REGISTRY.
    year : int
    output_dir : Path, optional
        Defaults to LANDSAT_DIR / glacier_name.

    Returns
    -------
    Path
        Path to the saved NDSI GeoTIFF.
    """
    name = glacier_config["name"].replace(" ", "_").replace("/", "-").lower()
    bbox = glacier_config["bbox"]
    season = glacier_config["season"]

    if output_dir is None:
        output_dir = LANDSAT_DIR / name
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / f"ndsi_{name}_{year}.tif"
    if out_path.exists():
        print(f"  Using cached: {out_path.name}")
        return out_path

    # Try sensors in priority order (fallback if primary has no data)
    sensors = _fallback_sensors_for_year(year)
    last_error = None
    for sensor in sensors:
        try:
            composite = compute_annual_composite(bbox, year, season, sensor_key=sensor)
            ndsi = compute_ndsi(composite)
            return export_to_geotiff(ndsi, bbox, out_path)
        except Exception as exc:
            last_error = exc
            continue

    raise last_error


def export_annual_rgb(glacier_config, year, output_dir=None):
    """Export an annual true-color RGB GeoTIFF for visualization.

    Parameters
    ----------
    glacier_config : dict
        Glacier entry from GLACIER_REGISTRY.
    year : int
    output_dir : Path, optional

    Returns
    -------
    Path
        Path to the saved RGB GeoTIFF.
    """
    name = glacier_config["name"].replace(" ", "_").replace("/", "-").lower()
    bbox = glacier_config["bbox"]
    season = glacier_config["season"]

    if output_dir is None:
        output_dir = LANDSAT_DIR / name
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / f"rgb_{name}_{year}.tif"
    if out_path.exists():
        print(f"  Using cached: {out_path.name}")
        return out_path

    composite = compute_annual_composite(bbox, year, season, bands=["red", "green", "nir"])

    return export_to_geotiff(composite, bbox, out_path)


def export_timeseries(
    glacier_config, year_start=1985, year_end=2025, output_dir=None, skip_existing=True
):
    """Export NDSI GeoTIFFs for a range of years.

    Parameters
    ----------
    glacier_config : dict
    year_start, year_end : int
    output_dir : Path, optional
    skip_existing : bool

    Returns
    -------
    dict
        {year: Path} mapping of exported files.
    """
    results = {}
    for year in range(year_start, year_end + 1):
        try:
            path = export_annual_ndsi(glacier_config, year, output_dir)
            results[year] = path
        except Exception as exc:
            warnings.warn(f"  Skipping {year}: {exc}", stacklevel=2)
    return results
