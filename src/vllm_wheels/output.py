"""Stable JSON, CSV, stats, and schema outputs."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from packaging.version import InvalidVersion, Version

from .models import WheelRecord


CSV_FIELDS = [
    "id",
    "channel",
    "source",
    "release",
    "version",
    "index_family",
    "effective_variant",
    "wheel_variant",
    "python_tag",
    "abi_tag",
    "operating_system",
    "architecture",
    "platform_tag",
    "filename",
    "index_url",
    "download_url",
    "install_command",
    "commit",
    "published_at",
    "size",
]


def _version_key(record: WheelRecord) -> Version:
    candidate = record.release or record.version
    try:
        return Version(candidate)
    except InvalidVersion:
        return Version("0")


def sort_records(records: Iterable[WheelRecord]) -> list[WheelRecord]:
    result = sorted(
        records,
        key=lambda record: (
            record.channel,
            record.source,
            record.effective_variant,
            record.platform_tag,
            record.filename,
        ),
    )
    result.sort(key=_version_key, reverse=True)
    return result


def build_stats(records: list[WheelRecord], generated_at: str) -> dict[str, object]:
    releases = {
        record.release
        for record in records
        if record.channel == "release" and record.release
    }
    stable_versions: list[Version] = []
    for release in releases:
        try:
            parsed = Version(release)
        except InvalidVersion:
            continue
        if not parsed.is_prerelease and not parsed.is_devrelease:
            stable_versions.append(parsed)

    return {
        "schema_version": 2,
        "generated_at": generated_at,
        "total_records": len(records),
        "unique_wheels": len({record.download_url for record in records}),
        "release_versions": len(releases),
        "latest_release": str(max(stable_versions)) if stable_versions else None,
        "channels": _count(record.channel for record in records),
        "sources": _count(record.source for record in records),
        "variants": _count(record.effective_variant for record in records),
        "architectures": _count(record.architecture for record in records),
        "python_tags": _count(record.python_tag for record in records),
    }


def write_outputs(
    output_dir: Path,
    records: Iterable[WheelRecord],
    warnings: list[str],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_records = sort_records(records)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    stats = build_stats(sorted_records, generated_at)
    dataset = {
        "schema_version": 2,
        "generated_at": generated_at,
        "stats": stats,
        "warnings": sorted(set(warnings)),
        "wheels": [record.to_dict() for record in sorted_records],
    }

    (output_dir / "wheels.json").write_text(
        json.dumps(dataset, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "stats.json").write_text(
        json.dumps(stats, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "wheels.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(record.to_dict() for record in sorted_records)
    (output_dir / "schema.json").write_text(
        json.dumps(json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
    return stats


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def json_schema() -> dict[str, object]:
    nullable_string = {"type": ["string", "null"]}
    wheel_properties = {
        "id": {"type": "string"},
        "source": {"type": "string"},
        "channel": {"enum": ["release", "nightly", "commit"]},
        "filename": {"type": "string"},
        "version": {"type": "string"},
        "release": nullable_string,
        "commit": nullable_string,
        "build_tag": nullable_string,
        "python_tag": {"type": "string"},
        "abi_tag": {"type": "string"},
        "platform_tag": {"type": "string"},
        "architecture": {"type": "string"},
        "operating_system": {"type": "string"},
        "index_family": nullable_string,
        "index_variant": nullable_string,
        "wheel_variant": nullable_string,
        "effective_variant": {"type": "string"},
        "index_url": nullable_string,
        "download_url": {"type": "string", "format": "uri"},
        "source_url": {"type": "string", "format": "uri"},
        "install_command": {"type": "string"},
        "published_at": nullable_string,
        "size": {"type": ["integer", "null"]},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://mgoin.github.io/vllm-wheels/data/schema.json",
        "title": "vLLM wheel index",
        "type": "object",
        "required": ["schema_version", "generated_at", "stats", "warnings", "wheels"],
        "properties": {
            "schema_version": {"const": 2},
            "generated_at": {"type": "string", "format": "date-time"},
            "stats": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "wheels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": sorted(wheel_properties),
                    "properties": wheel_properties,
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }
