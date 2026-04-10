"""
Sentinel-2 imagery acquisition via Copernicus Data Space Ecosystem (CDSE).

Provides 10m resolution imagery from 2015–present, complementing Landsat's
40-year archive with higher spatial detail for recent years.

CDSE replaced the old Copernicus Open Access Hub (SciHub) in 2023.
Registration: https://dataspace.copernicus.eu

Note: sentinelsat is NOT used — it targets the decommissioned SciHub.
We use CDSE's OData API directly via requests.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

from ..config import SENTINEL_DIR

# CDSE API endpoints
CDSE_AUTH_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
CDSE_ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1"
CDSE_DOWNLOAD_URL = "https://zipper.dataspace.copernicus.eu/odata/v1"


class CDSEClient:
    """Client for the Copernicus Data Space Ecosystem API."""

    def __init__(self, username=None, password=None):
        """Initialize with CDSE credentials.

        If not provided, looks for CDSE_USERNAME and CDSE_PASSWORD
        environment variables.
        """
        import os

        self.username = username or os.environ.get("CDSE_USERNAME")
        self.password = password or os.environ.get("CDSE_PASSWORD")
        self._token = None
        self._token_expiry = None

        if not self.username or not self.password:
            raise ValueError(
                "CDSE credentials required. Either pass username/password or set "
                "CDSE_USERNAME and CDSE_PASSWORD environment variables.\n"
                "Register free at: https://dataspace.copernicus.eu"
            )

    def _get_token(self):
        """Obtain or refresh OAuth2 access token."""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        resp = requests.post(
            CDSE_AUTH_URL,
            data={
                "client_id": "cdse-public",
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        self._token = data["access_token"]
        self._token_expiry = datetime.now() + timedelta(seconds=data["expires_in"] - 60)
        return self._token

    def search(self, bbox, date_start, date_end, cloud_cover_max=20, product_type="S2MSI2A"):
        """Search for Sentinel-2 products.

        Parameters
        ----------
        bbox : tuple
            (west, south, east, north) in degrees.
        date_start, date_end : str
            ISO format dates (e.g. "2024-06-01").
        cloud_cover_max : int
            Maximum cloud cover percentage.
        product_type : str
            "S2MSI2A" for Level-2A (surface reflectance, recommended).

        Returns
        -------
        list of dict
            Product metadata sorted by cloud cover.
        """
        w, s, e, n = bbox
        footprint = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

        filter_parts = [
            "Collection/Name eq 'SENTINEL-2'",
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq '{product_type}')",
            f"OData.CSC.Intersects(area=geography'SRID=4326;{footprint}')",
            f"ContentDate/Start ge {date_start}T00:00:00.000Z",
            f"ContentDate/Start le {date_end}T23:59:59.999Z",
            f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {cloud_cover_max})",
        ]

        filter_str = " and ".join(filter_parts)
        url = f"{CDSE_ODATA_URL}/Products?$filter={quote(filter_str)}&$orderby=ContentDate/Start asc&$top=100"

        resp = requests.get(url)
        resp.raise_for_status()

        products = resp.json().get("value", [])
        print(f"  Found {len(products)} Sentinel-2 scenes")
        return products

    def download_product(self, product_id, output_dir=None):
        """Download a Sentinel-2 product as a ZIP file.

        Parameters
        ----------
        product_id : str
            Product UUID from search results.
        output_dir : Path, optional
            Download directory. Defaults to SENTINEL_DIR.

        Returns
        -------
        Path
            Path to the downloaded ZIP file.
        """
        if output_dir is None:
            output_dir = SENTINEL_DIR
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        out_path = output_dir / f"{product_id}.zip"
        if out_path.exists():
            print(f"  Using cached: {out_path.name}")
            return out_path

        token = self._get_token()
        url = f"{CDSE_DOWNLOAD_URL}/Products({product_id})/$value"

        print(f"  Downloading Sentinel-2 product: {product_id[:12]}...")
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=600
        )
        resp.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  Saved: {out_path.name}")
        return out_path


def search_sentinel2(bbox, date_start, date_end, cloud_cover_max=20):
    """Convenience function to search without creating a client.

    Returns product metadata. Requires CDSE_USERNAME/CDSE_PASSWORD env vars.
    """
    client = CDSEClient()
    return client.search(bbox, date_start, date_end, cloud_cover_max)


def download_sentinel2(
    bbox, date_start, date_end, output_dir=None, cloud_cover_max=20, max_products=5
):
    """Search and download Sentinel-2 products.

    Parameters
    ----------
    bbox : tuple
    date_start, date_end : str
    output_dir : Path, optional
    cloud_cover_max : int
    max_products : int
        Maximum number of products to download.

    Returns
    -------
    list of Path
        Downloaded ZIP file paths.
    """
    client = CDSEClient()
    products = client.search(bbox, date_start, date_end, cloud_cover_max)

    paths = []
    for product in products[:max_products]:
        pid = product["Id"]
        path = client.download_product(pid, output_dir)
        paths.append(path)
        time.sleep(1)  # Rate limiting

    return paths
