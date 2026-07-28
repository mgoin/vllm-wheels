"""Normalized wheel record used by every source and output."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class WheelRecord:
    source: str
    channel: str
    filename: str
    version: str
    python_tag: str
    abi_tag: str
    platform_tag: str
    architecture: str
    operating_system: str
    download_url: str
    source_url: str
    index_url: str | None = None
    index_family: str | None = None
    index_variant: str | None = None
    wheel_variant: str | None = None
    release: str | None = None
    commit: str | None = None
    build_tag: str | None = None
    published_at: str | None = None
    size: int | None = None

    @property
    def id(self) -> str:
        identity = "|".join(
            (
                self.source,
                self.channel,
                self.index_url or "",
                self.download_url,
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    @property
    def effective_variant(self) -> str:
        return self.index_variant or self.wheel_variant or "default"

    @property
    def install_command(self) -> str:
        backend = "cpu" if self.effective_variant == "cpu" else "auto"
        if self.source == "github":
            return f'uv pip install "{self.download_url}" --torch-backend {backend}'

        package = "vllm"
        if self.channel == "release" and self.release:
            package = f"vllm=={self.release}"
        upgrade = "-U " if self.channel in {"nightly", "commit"} else ""
        command = f'uv pip install {upgrade}"{package}"'
        if self.index_url:
            command += f' --extra-index-url "{self.index_url}"'
        if self.effective_variant == "cpu":
            command += " --index-strategy first-index"
        command += f" --torch-backend {backend}"
        return command

    def to_dict(self) -> dict[str, object]:
        record = asdict(self)
        record["id"] = self.id
        record["effective_variant"] = self.effective_variant
        record["install_command"] = self.install_command
        return record
