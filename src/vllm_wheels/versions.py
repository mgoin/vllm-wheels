"""PyPI release discovery with PEP 440 ordering."""

from __future__ import annotations

from packaging.version import InvalidVersion, Version

from .http import HttpClient


PYPI_PROJECT_URL = "https://pypi.org/pypi/vllm/json"


def sort_versions(versions: list[str]) -> list[str]:
    parsed: list[tuple[Version, str]] = []
    for version in versions:
        try:
            parsed.append((Version(version), version))
        except InvalidVersion:
            continue
    parsed.sort(key=lambda item: item[0], reverse=True)
    return [original for _, original in parsed]


def get_pypi_versions(client: HttpClient, limit: int | None = None) -> list[str]:
    payload = client.get_json(PYPI_PROJECT_URL)
    releases = payload.get("releases", {})
    versions = sort_versions(
        [version for version, files in releases.items() if files]
    )
    return versions[:limit] if limit else versions
