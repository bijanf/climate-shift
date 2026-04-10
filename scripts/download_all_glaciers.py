#!/usr/bin/env python3
"""
Download Landsat NDSI time series for all 20 glaciers in the registry.

Long-running script (~10 hours total). Checks for cached files so it can
be safely interrupted and resumed. Logs progress to a JSON file.

Usage:
    python scripts/download_all_glaciers.py
    python scripts/download_all_glaciers.py --year-start 1985 --year-end 2024
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Download all 20 registry glaciers")
    parser.add_argument("--year-start", type=int, default=1985)
    parser.add_argument("--year-end", type=int, default=2024)
    parser.add_argument(
        "--log-file",
        type=str,
        default="glacier_data/outputs/download_progress.json",
    )
    args = parser.parse_args()

    from glacier_toolkit.acquire.landsat import export_annual_ndsi
    from glacier_toolkit.config import GLACIER_REGISTRY, LANDSAT_DIR

    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing progress
    if log_path.exists():
        with open(log_path) as f:
            progress = json.load(f)
    else:
        progress = {"started": datetime.utcnow().isoformat(), "glaciers": {}}

    n_glaciers = len(GLACIER_REGISTRY)
    n_years = args.year_end - args.year_start + 1
    total = n_glaciers * n_years
    done = 0
    failed = 0

    print(f"Downloading {n_glaciers} glaciers x {n_years} years = {total} tiles")
    print(f"Year range: {args.year_start}-{args.year_end}")
    print(f"Log file: {log_path}")
    print("=" * 70)

    start_time = time.time()

    for gi, (key, glacier) in enumerate(GLACIER_REGISTRY.items(), 1):
        glacier_log = progress["glaciers"].setdefault(
            key,
            {"name": glacier["name"], "region": glacier["region"], "years": {}},
        )
        glacier_dir = LANDSAT_DIR / glacier["name"].replace(" ", "_").replace("/", "-").lower()

        print(f"\n[{gi}/{n_glaciers}] {glacier['name']} ({glacier['region']})")

        for year in range(args.year_start, args.year_end + 1):
            year_key = str(year)
            if glacier_log["years"].get(year_key) == "ok":
                done += 1
                continue
            if glacier_log["years"].get(year_key) == "no_data":
                done += 1
                continue

            try:
                path = export_annual_ndsi(glacier, year, output_dir=glacier_dir)
                glacier_log["years"][year_key] = "ok"
                done += 1
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta_min = (total - done) / rate / 60 if rate > 0 else 0
                print(f"  {year}: OK  ({done}/{total}, ETA {eta_min:.0f}min)")
            except Exception as exc:
                msg = str(exc)[:80]
                if "No cloud-free scenes" in msg or "No data" in msg:
                    glacier_log["years"][year_key] = "no_data"
                    done += 1
                else:
                    glacier_log["years"][year_key] = f"error: {msg}"
                    failed += 1
                print(f"  {year}: SKIP ({msg})")

            # Save progress after each year
            with open(log_path, "w") as f:
                json.dump(progress, f, indent=2)

    progress["finished"] = datetime.utcnow().isoformat()
    progress["total_tiles"] = total
    progress["successful"] = done - failed
    progress["failed"] = failed

    with open(log_path, "w") as f:
        json.dump(progress, f, indent=2)

    print("=" * 70)
    print(f"Complete: {done - failed}/{total} successful, {failed} failed")
    print(f"Total time: {(time.time() - start_time) / 60:.1f} minutes")


if __name__ == "__main__":
    main()
