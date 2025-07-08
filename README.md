# vLLM Wheel Scraper

A standalone script to scrape all available vLLM wheels from the PyPI server at https://wheels.vllm.ai/

## Overview

This script can discover and list all available vLLM wheel files from the vLLM wheel server. The server organizes wheels by commit hash, with each commit having its own directory structure.

## Usage

### Basic Usage

```bash
# Discover wheels for recent commits using GitHub API
python3 scrape_vllm_wheels.py --use-github --max-commits 10

# Get wheels for a specific commit
python3 scrape_vllm_wheels.py --commit 33f460b17a54acb3b6cc0b03f4a17876cff5eafd

# Scrape GitHub releases for official wheels
python3 scrape_vllm_wheels.py --github-releases --max-releases 10

# Scrape nightly wheels
python3 scrape_vllm_wheels.py --nightly

# Scrape release version wheels
python3 scrape_vllm_wheels.py --release-versions

# Scrape all sources (commits, releases, nightly, and release versions)
python3 scrape_vllm_wheels.py --all-sources

# Save results to JSON file
python3 scrape_vllm_wheels.py --github-releases --output wheels.json

# Show only wheel files (no source distributions)
python3 scrape_vllm_wheels.py --github-releases --wheels-only
```

### Wheel Sources

The script can discover wheels from multiple sources:

#### 1. Commit-based Wheels
Wheels built from specific commits, organized by commit hash:
```bash
# Example URL structure
https://wheels.vllm.ai/{commit_hash}/vllm-1.0.0.dev-cp38-abi3-manylinux1_x86_64.whl
```

#### 2. GitHub Releases
Official releases with precompiled wheels for different CUDA versions:
```bash
# Example for CUDA 11.8
https://github.com/vllm-project/vllm/releases/download/v0.6.1.post1/vllm-0.6.1.post1+cu118-cp312-cp312-manylinux1_x86_64.whl

# Example for CUDA 12.6
https://github.com/vllm-project/vllm/releases/download/v0.6.1.post1/vllm-0.6.1.post1+cu126-cp312-cp312-manylinux1_x86_64.whl
```

#### 3. Nightly Wheels
Development builds updated regularly:
```bash
# Example URL structure
https://wheels.vllm.ai/nightly/vllm-1.0.0.dev-cp38-abi3-manylinux1_x86_64.whl
```

#### 4. Release Version Wheels
Release versions hosted directly on the wheels server:
```bash
# Example URL structure
https://wheels.vllm.ai/0.9.2/vllm-0.9.2-cp38-abi3-manylinux1_x86_64.whl

# Install using extra index URL
uv pip install -U vllm==0.9.2 --extra-index-url https://wheels.vllm.ai/0.9.2 --torch-backend auto
```

### Installation Examples

Once you find a wheel from the script output, you can install it using pip:

```bash
# Install from a specific commit
export VLLM_COMMIT=33f460b17a54acb3b6cc0b03f4a17876cff5eafd
uv pip install vllm --extra-index-url https://wheels.vllm.ai/${VLLM_COMMIT} --torch-backend auto

# Install using extra index URL for nightly builds
uv pip install vllm --extra-index-url https://wheels.vllm.ai/nightly --torch-backend auto

# Install from GitHub releases with specific CUDA version
export VLLM_VERSION=0.6.1.post1
export PYTHON_VERSION=312
uv pip install https://github.com/vllm-project/vllm/releases/download/v${VLLM_VERSION}/vllm-${VLLM_VERSION}+cu118-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}-manylinux1_x86_64.whl --extra-index-url https://download.pytorch.org/whl/cu118
```

### Command Line Options

- `--base-url`: Base URL of the PyPI server (default: https://wheels.vllm.ai/)
- `--commit`: Scrape specific commit only
- `--github-releases`: Scrape GitHub releases for official wheels
- `--nightly`: Scrape nightly wheels
- `--release-versions`: Scrape release version wheels from wheels server
- `--all-sources`: Scrape all sources (commits, releases, nightly, and release versions)
- `--use-github`: Use GitHub API to discover recent commits (recommended)
- `--max-commits`: Maximum number of commits to check (default: 50)
- `--max-releases`: Maximum number of releases to check (default: 20)
- `--max-versions`: Maximum number of versions to fetch from PyPI (default: 20)
- `--wheels-only`: Only show wheel files, not source distributions
- `--output`: Output file in JSON format
- `--verbose`: Show detailed URLs and debug information
- `--legacy-mode`: Use legacy package-based discovery mode

## Architecture

The vLLM wheel server has the following structure:
- `https://wheels.vllm.ai/{commit_hash}/` - Contains a link to the `vllm/` subdirectory
- `https://wheels.vllm.ai/{commit_hash}/vllm/` - Contains the actual wheel files

The script handles this nested structure automatically.

## Output Format

The script outputs information about each commit and its available wheels:

```
Commit: baba0389f7e810a361fff5229ce20c2d5a2b1fac
  vllm-0.9.2rc2.dev86%2Bgbaba0389f-cp38-abi3-manylinux1_x86_64.whl (cp38-abi3-manylinux1_x86_64)

Summary:
  Commits: 10
  Total files: 10
  Wheel files: 10
  Source files: 0
```

## JSON Output

When using `--output`, the script saves detailed information in JSON format:

```json
{
  "scrape_time": "2024-01-01T12:00:00.000000",
  "base_url": "https://wheels.vllm.ai/",
  "mode": "commit",
  "results": {
    "commit_hash": [
      {
        "filename": "vllm-0.9.2rc2.dev86%2Bgbaba0389f-cp38-abi3-manylinux1_x86_64.whl",
        "type": "wheel",
        "name": "vllm",
        "version": "0.9.2rc2.dev86+gbaba0389f",
        "python_tag": "cp38",
        "abi_tag": "abi3",
        "platform_tag": "manylinux1_x86_64",
        "url": "https://wheels.vllm.ai/commit_hash/vllm-0.9.2rc2.dev86%2Bgbaba0389f-cp38-abi3-manylinux1_x86_64.whl",
        "commit": "commit_hash"
      }
    ]
  }
}
```

## Requirements

- Python 3.6+
- Standard library only (no external dependencies)

## Tips

1. **Use GitHub API mode**: The `--use-github` flag is recommended as it can discover recent commits even when the server doesn't provide a directory listing.

2. **Limit commits**: Use `--max-commits` to avoid overwhelming the server and speed up execution.

3. **Filter by wheels only**: Use `--wheels-only` to focus on installable wheel files.

4. **Save results**: Use `--output` to save results for later analysis or automation.

## Known Limitations

- The script relies on HTML parsing of directory listings, which may break if the server format changes
- GitHub API rate limiting may affect large queries
- The script includes a small delay between requests to avoid overwhelming the server 