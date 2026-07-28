"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .http import FetchError, HttpClient
from .output import write_outputs
from .scraper import Scraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vllm-wheel-index",
        description="Build normalized JSON and CSV indexes of available vLLM wheels.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Directory for wheels.json, wheels.csv, stats.json, and schema.json.",
    )
    parser.add_argument(
        "--max-versions",
        type=int,
        default=0,
        help="Maximum PyPI versions to inspect; 0 means all versions.",
    )
    parser.add_argument(
        "--max-github-releases",
        type=int,
        default=0,
        help="Maximum GitHub releases to inspect; 0 means all releases.",
    )
    parser.add_argument(
        "--recent-commits",
        type=int,
        default=20,
        help="Number of recent main-branch commits to inspect; 0 disables commits.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent wheels.vllm.ai release requests.",
    )
    parser.add_argument("--skip-index-releases", action="store_true")
    parser.add_argument("--skip-github-releases", action="store_true")
    parser.add_argument("--skip-nightly", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = HttpClient(github_token=os.getenv("GITHUB_TOKEN"))
    scraper = Scraper(client, workers=max(1, args.workers))

    try:
        result = scraper.run(
            include_index_releases=not args.skip_index_releases,
            include_github_releases=not args.skip_github_releases,
            include_nightly=not args.skip_nightly,
            max_versions=args.max_versions or None,
            max_github_releases=args.max_github_releases or None,
            recent_commits=max(0, args.recent_commits),
        )
    except FetchError as error:
        print(f"Scrape failed: {error}", file=sys.stderr)
        return 1

    if not result.records:
        print("Scrape returned no wheels; existing output was not replaced.", file=sys.stderr)
        return 1

    stats = write_outputs(args.output_dir, result.records, result.warnings)
    print(
        "Wrote "
        f"{stats['total_records']} records / "
        f"{stats['unique_wheels']} unique wheels / "
        f"{stats['release_versions']} release versions.",
        file=sys.stderr,
    )
    if result.warnings:
        print(f"Completed with {len(set(result.warnings))} warnings.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

