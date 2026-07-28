"""Orchestrate all wheel sources."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .http import FetchError, HttpClient
from .models import WheelRecord
from .sources import GitHubSource, WheelsIndexSource
from .versions import get_pypi_versions


@dataclass
class ScrapeResult:
    records: list[WheelRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, records: list[WheelRecord], warnings: list[str] | None = None) -> None:
        self.records.extend(records)
        if warnings:
            self.warnings.extend(warnings)


class Scraper:
    def __init__(
        self,
        client: HttpClient,
        *,
        workers: int = 8,
    ) -> None:
        self.client = client
        self.workers = workers
        self.github = GitHubSource(client)
        self.index = WheelsIndexSource(client)

    def run(
        self,
        *,
        include_index_releases: bool = True,
        include_github_releases: bool = True,
        include_nightly: bool = True,
        max_versions: int | None = None,
        max_github_releases: int | None = None,
        recent_commits: int = 0,
    ) -> ScrapeResult:
        result = ScrapeResult()

        if include_index_releases:
            print("Discovering release versions from PyPI…", file=sys.stderr)
            versions = get_pypi_versions(self.client, max_versions)
            print(
                f"Scraping {len(versions)} release versions from wheels.vllm.ai…",
                file=sys.stderr,
            )
            result.extend(*self._scrape_version_indexes(versions))

        if include_github_releases:
            print("Scraping GitHub release assets…", file=sys.stderr)
            try:
                result.records.extend(
                    self.github.scrape_releases(max_github_releases)
                )
            except FetchError as error:
                result.warnings.append(str(error))

        if include_nightly:
            print("Scraping nightly indexes…", file=sys.stderr)
            for family in ("main", "rocm"):
                result.extend(
                    *self.index.scrape_reference(
                        "nightly",
                        channel="nightly",
                        family=family,
                    )
                )

        if recent_commits:
            print(f"Scraping {recent_commits} recent commits…", file=sys.stderr)
            try:
                commits = self.github.recent_commits(recent_commits)
            except FetchError as error:
                result.warnings.append(str(error))
                commits = []
            for commit in commits:
                result.extend(
                    *self.index.scrape_reference(commit, channel="commit")
                )

        unique = {record.id: record for record in result.records}
        result.records = list(unique.values())
        return result

    def _scrape_version_indexes(
        self,
        versions: list[str],
    ) -> tuple[list[WheelRecord], list[str]]:
        records: list[WheelRecord] = []
        warnings: list[str] = []
        tasks: list[tuple[str, str]] = [
            (version, family)
            for version in versions
            for family in ("main", "rocm")
        ]
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_map = {
                executor.submit(
                    self.index.scrape_reference,
                    version,
                    channel="release",
                    family=family,
                ): (version, family)
                for version, family in tasks
            }
            completed_tasks = 0
            for future in as_completed(future_map):
                version, _ = future_map[future]
                try:
                    found, found_warnings = future.result()
                except Exception as error:  # preserve partial source results
                    warnings.append(f"{version}: {error}")
                    continue
                records.extend(found)
                warnings.extend(found_warnings)
                completed_tasks += 1
                if completed_tasks % 20 == 0:
                    print(
                        f"  checked {completed_tasks}/{len(tasks)} index roots",
                        file=sys.stderr,
                    )
        return records, warnings
