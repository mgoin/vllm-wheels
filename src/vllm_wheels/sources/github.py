"""GitHub release assets and commit discovery."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from ..http import HttpClient
from ..models import WheelRecord
from ..parsing import architecture_from_platform, os_from_platform, parse_github_wheel


class GitHubSource:
    def __init__(
        self,
        client: HttpClient,
        repo: str = "vllm-project/vllm",
    ) -> None:
        self.client = client
        self.repo = repo
        self.api_base = f"https://api.github.com/repos/{repo}"

    def scrape_releases(self, limit: int | None = None) -> list[WheelRecord]:
        records: list[WheelRecord] = []
        fetched = 0
        page = 1

        while True:
            remaining = limit - fetched if limit else 100
            per_page = min(100, remaining) if limit else 100
            query = urlencode({"per_page": per_page, "page": page})
            releases = self.client.get_json(
                f"{self.api_base}/releases?{query}",
                github_api=True,
            )
            if not releases:
                break

            for release in releases:
                records.extend(self._release_records(release))

            fetched += len(releases)
            if len(releases) < per_page or (limit and fetched >= limit):
                break
            page += 1

        return records

    def recent_commits(self, limit: int) -> list[str]:
        commits: list[str] = []
        page = 1
        while len(commits) < limit:
            per_page = min(100, limit - len(commits))
            query = urlencode({"per_page": per_page, "page": page})
            payload = self.client.get_json(
                f"{self.api_base}/commits?{query}",
                github_api=True,
            )
            if not payload:
                break
            commits.extend(item["sha"] for item in payload)
            if len(payload) < per_page:
                break
            page += 1
        return commits[:limit]

    def _release_records(self, release: dict[str, Any]) -> list[WheelRecord]:
        records: list[WheelRecord] = []
        release_version = release["tag_name"].removeprefix("v")
        source_url = release.get("html_url") or (
            f"https://github.com/{self.repo}/releases/tag/{release['tag_name']}"
        )

        for asset in release.get("assets", []):
            filename = asset.get("name", "")
            if not filename.endswith(".whl"):
                continue
            metadata = parse_github_wheel(filename)
            if not metadata:
                continue
            platform = str(metadata["platform_tag"])
            variant = metadata.get("wheel_variant")
            records.append(
                WheelRecord(
                    source="github",
                    channel="release",
                    filename=filename,
                    version=str(metadata["version"]),
                    release=release_version,
                    build_tag=metadata.get("build_tag"),
                    python_tag=str(metadata["python_tag"]),
                    abi_tag=str(metadata["abi_tag"]),
                    platform_tag=platform,
                    architecture=architecture_from_platform(platform),
                    operating_system=os_from_platform(platform),
                    index_family="github",
                    index_variant=str(variant or "default"),
                    wheel_variant=str(variant) if variant else None,
                    download_url=asset["browser_download_url"],
                    source_url=source_url,
                    published_at=release.get("published_at"),
                    size=asset.get("size"),
                )
            )
        return records
