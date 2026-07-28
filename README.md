# vLLM Wheel Explorer

A searchable, developer-friendly index of vLLM wheels from:

- release and nightly indexes on [wheels.vllm.ai](https://wheels.vllm.ai/)
- CUDA, CPU, and ROCm variant sub-indexes
- official [GitHub release assets](https://github.com/vllm-project/vllm/releases)
- a bounded window of recent main-branch commit builds

The hosted browser is designed for people. The generated JSON, CSV, and JSON
Schema are designed for scripts.

## Why this exists

vLLM publishes wheels through several channels and index layouts. The official
[getting started](https://vllm.ai/#quick-start) and
[previous releases](https://vllm.ai/releases) pages cover common installation
paths. This project complements them with the complete, filterable wheel-level
inventory: source, version, index variant, Python and ABI tags, platform,
architecture, download URL, and an exact install command.

## Refresh the index

Install the package and run the scraper:

```bash
python -m pip install .
python -m vllm_wheels
```

By default, this inspects every PyPI release, every GitHub release, current
nightly indexes, and 20 recent commits. Useful limits:

```bash
python -m vllm_wheels \
  --max-versions 10 \
  --max-github-releases 10 \
  --recent-commits 5
```

`GITHUB_TOKEN` is optional, but recommended for higher GitHub API limits.

The command writes:

- `data/wheels.json` — normalized schema v2 dataset
- `data/wheels.csv` — flat export
- `data/stats.json` — summary counts
- `data/schema.json` — JSON Schema for consumers

## Build the site

The site intentionally has no runtime framework or package-manager dependency:

```bash
python scripts/build_site.py
python -m http.server 8000 --directory dist/client
```

The build copies the static application and current data into `dist/client` and
creates the small worker entry point used by the production host.

## Project structure

```text
src/vllm_wheels/
├── cli.py
├── http.py
├── models.py
├── output.py
├── parsing.py
├── scraper.py
├── versions.py
└── sources/
    ├── github.py
    └── vllm_index.py
site/
├── assets/
├── index.html
└── og.png
scripts/
└── build_site.py
tests/
data/
```

The source adapters emit one `WheelRecord` model. The frontend therefore reads
explicit fields such as `channel`, `source`, `index_variant`, and `index_url`
instead of inferring meaning from result-key prefixes.

## Tests

```bash
python -m pip install .
python -m unittest discover -v
```

Tests cover PEP 440 version ordering, nested variants, default
aliases, ROCm indexes, URL encoding, install commands, and output generation.

## Automation

- `Refresh wheel index` runs daily, tests the scraper, refreshes all data, and
  commits changes.
- `Deploy static site` publishes `dist/client` through GitHub Pages whenever the
  site or data changes.

This is a community project and is not an official vLLM property.
