#!/usr/bin/env python3
"""
Quick Instagram content generator for any glacier.

Generates a 4-slide carousel + caption in one command.

Usage:
  python -m glacier_toolkit.pipelines.run_social_post --name "aletsch"
  python -m glacier_toolkit.pipelines.run_social_post --name "columbia" --year-start 1985
"""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate Instagram carousel for a glacier"
    )
    parser.add_argument("--name", type=str, required=True,
                        help="Glacier registry key")
    parser.add_argument("--year-start", type=int, default=1985)
    parser.add_argument("--year-end", type=int, default=2024)
    args = parser.parse_args()

    # Delegate to the full pipeline
    import sys
    sys.argv = [
        "run_single_glacier",
        "--name", args.name,
        "--year-start", str(args.year_start),
        "--year-end", str(args.year_end),
    ]

    from glacier_toolkit.pipelines.run_single_glacier import main as run
    run()


if __name__ == "__main__":
    main()
