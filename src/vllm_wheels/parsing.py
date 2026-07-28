"""Parsing helpers shared by wheel sources."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

from packaging.utils import InvalidWheelFilename, parse_wheel_filename


COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VARIANT_PATTERN = re.compile(r"^(?:cpu|cu\d+|rocm\d+|xpu[\w.-]*)$", re.IGNORECASE)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self.links.extend(value for name, value in attrs if name == "href" and value)


def parse_links(html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def direct_subdirectories(links: list[str]) -> list[str]:
    directories: set[str] = set()
    for link in links:
        path = urlparse(link).path
        if not path.endswith("/"):
            continue
        segment = unquote(path.rstrip("/").rsplit("/", 1)[-1])
        if segment and segment not in {".", ".."}:
            directories.add(segment)
    return sorted(directories)


def parse_github_wheel(filename: str) -> dict[str, str | None]:
    try:
        _, version, build, tags = parse_wheel_filename(filename)
    except InvalidWheelFilename:
        return {}

    tag = sorted(tags, key=str)[0]
    return {
        "version": str(version),
        "build_tag": ".".join(str(part) for part in build) if build else None,
        "python_tag": tag.interpreter,
        "abi_tag": tag.abi,
        "platform_tag": tag.platform,
        "wheel_variant": variant_from_version(str(version)),
    }


def variant_from_version(version: str) -> str | None:
    local = version.split("+", 1)[1] if "+" in version else ""
    for part in reversed(local.split(".")):
        if VARIANT_PATTERN.fullmatch(part):
            return part.lower()
    return None


def architecture_from_platform(platform: str) -> str:
    lowered = platform.lower()
    for architecture in ("x86_64", "aarch64", "arm64", "s390x", "ppc64le"):
        if lowered.endswith(architecture):
            return architecture
    if lowered in {"any", "none"}:
        return "any"
    return lowered.rsplit("_", 1)[-1]


def os_from_platform(platform: str) -> str:
    lowered = platform.lower()
    if "macosx" in lowered:
        return "macOS"
    if "win" in lowered:
        return "Windows"
    if "linux" in lowered:
        return "Linux"
    if lowered == "any":
        return "Any"
    return "Other"


def commit_from_url(url: str) -> str | None:
    for segment in urlparse(url).path.split("/"):
        if COMMIT_PATTERN.fullmatch(segment):
            return segment
    return None
