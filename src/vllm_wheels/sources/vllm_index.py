"""Discover wheels from the structured indexes on wheels.vllm.ai."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from ..http import FetchError, HttpClient
from ..models import WheelRecord
from ..parsing import (
    architecture_from_platform,
    commit_from_url,
    direct_subdirectories,
    os_from_platform,
    parse_links,
)


class WheelsIndexSource:
    def __init__(
        self,
        client: HttpClient,
        base_url: str = "https://wheels.vllm.ai/",
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/") + "/"

    def scrape_reference(
        self,
        reference: str,
        *,
        channel: str,
        family: str = "main",
    ) -> tuple[list[WheelRecord], list[str]]:
        root_url = self._root_url(reference, family)
        try:
            links = parse_links(self.client.get_text(root_url))
        except FetchError as error:
            if error.status == 404:
                return [], []
            return [], [str(error)]

        directories = direct_subdirectories(links)
        indexes: list[tuple[str, str]] = []
        if "vllm" in directories:
            indexes.append(("default", root_url.rstrip("/")))
        for directory in directories:
            if directory != "vllm":
                indexes.append((directory, urljoin(root_url, f"{directory}/").rstrip("/")))

        records: list[WheelRecord] = []
        warnings: list[str] = []
        for index_variant, index_url in indexes:
            metadata_url = f"{index_url}/vllm/metadata.json"
            try:
                payload = self.client.get_json(metadata_url)
            except FetchError as error:
                if error.status != 404:
                    warnings.append(str(error))
                continue
            if not isinstance(payload, list):
                warnings.append(f"unexpected metadata shape: {metadata_url}")
                continue
            records.extend(
                self._metadata_records(
                    payload,
                    reference=reference,
                    channel=channel,
                    family=family,
                    index_variant=index_variant,
                    index_url=index_url,
                    metadata_url=metadata_url,
                )
            )

        unique = {record.id: record for record in records}
        return list(unique.values()), warnings

    def _root_url(self, reference: str, family: str) -> str:
        if family == "rocm":
            return urljoin(self.base_url, f"rocm/{reference}/")
        return urljoin(self.base_url, f"{reference}/")

    def _metadata_records(
        self,
        payload: list[dict[str, Any]],
        *,
        reference: str,
        channel: str,
        family: str,
        index_variant: str,
        index_url: str,
        metadata_url: str,
    ) -> list[WheelRecord]:
        records: list[WheelRecord] = []
        package_url = metadata_url.rsplit("metadata.json", 1)[0]
        for item in payload:
            if item.get("package_name") != "vllm":
                continue
            platform = str(item["platform_tag"])
            download_url = urljoin(package_url, item["path"])
            release = reference if channel == "release" else None
            commit = reference if channel == "commit" else commit_from_url(download_url)
            records.append(
                WheelRecord(
                    source="wheels.vllm.ai",
                    channel=channel,
                    filename=item["filename"],
                    version=item["version"],
                    release=release,
                    commit=commit,
                    build_tag=item.get("build_tag"),
                    python_tag=item["python_tag"],
                    abi_tag=item["abi_tag"],
                    platform_tag=platform,
                    architecture=architecture_from_platform(platform),
                    operating_system=os_from_platform(platform),
                    index_family=family,
                    index_variant=index_variant,
                    wheel_variant=item.get("variant"),
                    index_url=index_url,
                    download_url=download_url,
                    source_url=index_url,
                )
            )
        return records

