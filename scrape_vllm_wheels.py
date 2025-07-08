#!/usr/bin/env python3
"""
Standalone script to scrape all vLLM wheels from https://wheels.vllm.ai/

This script discovers all available packages and versions from the vLLM PyPI index.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request
from html.parser import HTMLParser
import json
import argparse
from datetime import datetime
import time


class PyPIIndexParser(HTMLParser):
    """Parser for PyPI simple index pages"""
    
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_tag = None
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current_tag = tag
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    self.links.append(attr_value)
    
    def handle_endtag(self, tag):
        self.current_tag = None


def fetch_url(url: str) -> str:
    """Fetch URL content with proper headers"""
    try:
        req = Request(url, headers={
            'User-Agent': 'vLLM-Wheel-Scraper/1.0'
        })
        with urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return ""


def parse_wheel_filename(filename: str) -> Dict[str, str]:
    """Parse wheel filename to extract metadata"""
    # Wheel filename format: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    wheel_pattern = r'^(.+?)-(.+?)(?:-(.+?))?-(.+?)-(.+?)-(.+?)\.whl$'
    match = re.match(wheel_pattern, filename)
    
    if not match:
        return {"filename": filename, "type": "unknown"}
    
    name, version, build_tag, python_tag, abi_tag, platform_tag = match.groups()
    
    return {
        "filename": filename,
        "type": "wheel",
        "name": name,
        "version": version,
        "build_tag": build_tag,
        "python_tag": python_tag,
        "abi_tag": abi_tag,
        "platform_tag": platform_tag,
    }


def get_recent_commits_from_github(repo: str = "vllm-project/vllm", max_commits: int = 100) -> List[str]:
    """Get recent commits from GitHub API"""
    print(f"Fetching recent commits from GitHub for {repo}")
    
    api_url = f"https://api.github.com/repos/{repo}/commits?per_page={min(max_commits, 100)}"
    
    try:
        req = Request(api_url, headers={
            'User-Agent': 'vLLM-Wheel-Scraper/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
        with urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        commits = [commit['sha'] for commit in data]
        print(f"Found {len(commits)} recent commits from GitHub")
        return commits
        
    except Exception as e:
        print(f"Error fetching commits from GitHub: {e}", file=sys.stderr)
        return []


def get_pypi_versions(package_name: str = "vllm", max_versions: int = 50) -> List[str]:
    """Get available versions from PyPI"""
    print(f"Fetching versions from PyPI for {package_name}")
    
    api_url = f"https://pypi.org/pypi/{package_name}/json"
    
    try:
        req = Request(api_url, headers={
            'User-Agent': 'vLLM-Wheel-Scraper/1.0'
        })
        with urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        versions = list(data['releases'].keys())
        # Sort versions in reverse order (newest first)
        # This is a simple sort - for proper semantic version sorting we'd need a library
        versions.sort(reverse=True)
        
        if max_versions and len(versions) > max_versions:
            versions = versions[:max_versions]
        
        print(f"Found {len(versions)} versions from PyPI")
        return versions
        
    except Exception as e:
        print(f"Error fetching versions from PyPI: {e}", file=sys.stderr)
        return []


def get_github_releases(repo: str = "vllm-project/vllm", max_releases: int = 20) -> List[Dict[str, Any]]:
    """Get releases from GitHub API"""
    print(f"Fetching releases from GitHub for {repo}")
    
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page={min(max_releases, 100)}"
    
    try:
        req = Request(api_url, headers={
            'User-Agent': 'vLLM-Wheel-Scraper/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
        with urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        releases = []
        for release in data:
            release_info = {
                'tag_name': release['tag_name'],
                'name': release['name'],
                'published_at': release['published_at'],
                'prerelease': release['prerelease'],
                'assets': []
            }
            
            # Filter for wheel assets
            for asset in release.get('assets', []):
                if asset['name'].endswith('.whl'):
                    asset_info = {
                        'name': asset['name'],
                        'download_url': asset['browser_download_url'],
                        'size': asset['size'],
                        'created_at': asset['created_at']
                    }
                    release_info['assets'].append(asset_info)
            
            if release_info['assets']:  # Only include releases with wheel assets
                releases.append(release_info)
        
        print(f"Found {len(releases)} releases with wheel assets from GitHub")
        return releases
        
    except Exception as e:
        print(f"Error fetching releases from GitHub: {e}", file=sys.stderr)
        return []


def discover_commits(base_url: str) -> List[str]:
    """Discover all commit hashes from the wheels server"""
    print(f"Discovering commits from {base_url}")
    
    # Try to get the root index page to find commit directories
    content = fetch_url(base_url)
    if not content:
        print("Could not fetch root index", file=sys.stderr)
        return []
    
    parser = PyPIIndexParser()
    parser.feed(content)
    
    commits = []
    commit_pattern = re.compile(r'^[a-f0-9]{40}/?$')  # 40 character hex string (commit hash)
    
    for link in parser.links:
        clean_link = link.rstrip('/')
        if commit_pattern.match(clean_link):
            commits.append(clean_link)
    
    print(f"Found {len(commits)} commits from wheels server")
    
    # If we didn't find many commits, try to get more from GitHub
    if len(commits) < 10:
        print("Found few commits from server, trying GitHub API...")
        github_commits = get_recent_commits_from_github()
        
        # Test which GitHub commits have wheels available
        available_commits = []
        for commit in github_commits[:50]:  # Test first 50 commits
            test_files = scrape_commit_files(base_url, commit)
            if test_files:
                available_commits.append(commit)
                print(f"  Found wheels for commit {commit[:8]}")
            else:
                print(f"  No wheels for commit {commit[:8]}")
                
            # Add a small delay to avoid overwhelming the server
            time.sleep(0.1)
        
        # Combine and deduplicate
        all_commits = list(dict.fromkeys(commits + available_commits))
        print(f"Total commits with wheels: {len(all_commits)}")
        return all_commits
    
    return commits


def discover_packages(base_url: str) -> List[str]:
    """Discover all packages from the PyPI index (legacy method)"""
    print(f"Discovering packages from {base_url}")
    
    # Try different common index paths
    index_paths = [
        "",  # Root
        "simple/",  # Standard PyPI simple index
        "nightly/",  # Known nightly path
        "cu118/",   # CUDA 11.8
        "cu121/",   # CUDA 12.1
        "cu124/",   # CUDA 12.4
        "cu126/",   # CUDA 12.6
        "cpu/",     # CPU only
    ]
    
    all_packages = set()
    
    for path in index_paths:
        index_url = urljoin(base_url, path)
        print(f"Checking index: {index_url}")
        
        content = fetch_url(index_url)
        if not content:
            continue
            
        parser = PyPIIndexParser()
        parser.feed(content)
        
        # Filter for package links (not files)
        packages = []
        for link in parser.links:
            # Skip if it's a file (ends with .whl, .tar.gz, etc.)
            if any(link.endswith(ext) for ext in ['.whl', '.tar.gz', '.zip']):
                continue
                
            # Clean up the package name
            package_name = link.rstrip('/')
            if package_name and not package_name.startswith(('http', 'https')):
                packages.append((package_name, index_url))
                all_packages.add(package_name)
        
        if packages:
            print(f"  Found {len(packages)} packages in {path}")
    
    return list(all_packages)


def scrape_commit_files(base_url: str, commit_hash: str) -> List[Dict[str, str]]:
    """Scrape all files for a specific commit"""
    
    # Try both the direct commit URL and the commit/vllm/ subdirectory
    possible_urls = [
        urljoin(base_url, f"{commit_hash}/"),
        urljoin(base_url, f"{commit_hash}/vllm/")
    ]
    
    all_files = []
    
    for commit_url in possible_urls:
        content = fetch_url(commit_url)
        if not content:
            continue
        
        parser = PyPIIndexParser()
        try:
            parser.feed(content)
        except Exception as e:
            print(f"Error parsing HTML for commit {commit_hash[:8]} at {commit_url}: {e}", file=sys.stderr)
            continue
        
        files = []
        for link in parser.links:
            # Extract filename from link - handle various formats
            filename = ""
            if link.startswith('http'):
                # Absolute URL
                filename = Path(urlparse(link).path).name
            else:
                # Relative URL
                filename = link.split('/')[-1].split('#')[0].split('?')[0]
            
            if not filename:
                continue
            
            # Skip parent directory and current directory links
            if filename in ['.', '..', '']:
                continue
            
            # If this is a directory link (like "vllm/"), recursively check it
            if filename.endswith('/') or (filename == 'vllm' and not filename.endswith('.whl')):
                subdir_url = urljoin(commit_url, link)
                if subdir_url not in possible_urls:  # Avoid infinite recursion
                    subdir_files = scrape_commit_files_from_url(base_url, commit_hash, subdir_url)
                    all_files.extend(subdir_files)
                continue
                
            if filename.endswith('.whl'):
                file_info = parse_wheel_filename(filename)
                if file_info.get('type') == 'wheel':  # Only add if parsing succeeded
                    file_info['url'] = urljoin(commit_url, link)
                    file_info['commit'] = commit_hash
                    files.append(file_info)
            elif filename.endswith(('.tar.gz', '.zip')):
                files.append({
                    'filename': filename,
                    'type': 'source',
                    'url': urljoin(commit_url, link),
                    'commit': commit_hash
                })
        
        all_files.extend(files)
    
    return all_files


def scrape_commit_files_from_url(base_url: str, commit_hash: str, url: str) -> List[Dict[str, str]]:
    """Helper function to scrape files from a specific URL"""
    
    content = fetch_url(url)
    if not content:
        return []
    
    parser = PyPIIndexParser()
    try:
        parser.feed(content)
    except Exception as e:
        print(f"Error parsing HTML for commit {commit_hash[:8]} at {url}: {e}", file=sys.stderr)
        return []
    
    files = []
    for link in parser.links:
        # Extract filename from link - handle various formats
        filename = ""
        if link.startswith('http'):
            # Absolute URL
            filename = Path(urlparse(link).path).name
        else:
            # Relative URL
            filename = link.split('/')[-1].split('#')[0].split('?')[0]
        
        if not filename:
            continue
        
        # Skip parent directory and current directory links
        if filename in ['.', '..', '']:
            continue
            
        if filename.endswith('.whl'):
            file_info = parse_wheel_filename(filename)
            if file_info.get('type') == 'wheel':  # Only add if parsing succeeded
                file_info['url'] = urljoin(url, link)
                file_info['commit'] = commit_hash
                files.append(file_info)
        elif filename.endswith(('.tar.gz', '.zip')):
            files.append({
                'filename': filename,
                'type': 'source',
                'url': urljoin(url, link),
                'commit': commit_hash
            })
    
    return files


def scrape_release_version_wheels(base_url: str, versions: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """Scrape wheels for specific release versions"""
    print(f"Scraping release version wheels for {len(versions)} versions...")
    
    all_version_files = {}
    
    for version in versions:
        print(f"  Checking version {version}...")
        
        # Try different version path structures
        version_paths = [
            urljoin(base_url, f"{version}/"),
            urljoin(base_url, f"{version}/vllm/"),
            urljoin(base_url, f"v{version}/"),
            urljoin(base_url, f"v{version}/vllm/"),
        ]
        
        version_files = []
        
        for version_url in version_paths:
            content = fetch_url(version_url)
            if not content:
                continue
                
            parser = PyPIIndexParser()
            try:
                parser.feed(content)
            except Exception as e:
                print(f"    Error parsing HTML for version {version} at {version_url}: {e}", file=sys.stderr)
                continue
            
            for link in parser.links:
                # Extract filename from link
                filename = ""
                if link.startswith('http'):
                    filename = Path(urlparse(link).path).name
                else:
                    filename = link.split('/')[-1].split('#')[0].split('?')[0]
                
                if not filename or filename in ['.', '..', '']:
                    continue
                
                if filename.endswith('.whl'):
                    file_info = parse_wheel_filename(filename)
                    if file_info.get('type') == 'wheel':
                        file_info['url'] = urljoin(version_url, link)
                        file_info['source'] = 'release_version'
                        file_info['version_directory'] = version
                        version_files.append(file_info)
                elif filename.endswith(('.tar.gz', '.zip')):
                    version_files.append({
                        'filename': filename,
                        'type': 'source',
                        'url': urljoin(version_url, link),
                        'source': 'release_version',
                        'version_directory': version
                    })
            
            if version_files:
                break  # Found files in this path structure, no need to try others
        
        if version_files:
            print(f"    Found {len(version_files)} files for version {version}")
            all_version_files[version] = version_files
        else:
            print(f"    No files found for version {version}")
    
    return all_version_files


def scrape_nightly_wheels(base_url: str) -> List[Dict[str, str]]:
    """Scrape nightly wheels"""
    print("Scraping nightly wheels...")
    
    # Try different nightly paths
    nightly_paths = [
        urljoin(base_url, "nightly/"),
        urljoin(base_url, "nightly/vllm/"),
        urljoin(base_url, "nightly/simple/vllm/"),
    ]
    
    for nightly_url in nightly_paths:
        content = fetch_url(nightly_url)
        if not content:
            continue
            
        parser = PyPIIndexParser()
        try:
            parser.feed(content)
        except Exception as e:
            print(f"Error parsing HTML for nightly at {nightly_url}: {e}", file=sys.stderr)
            continue
        
        files = []
        for link in parser.links:
            # Extract filename from link
            filename = ""
            if link.startswith('http'):
                filename = Path(urlparse(link).path).name
            else:
                filename = link.split('/')[-1].split('#')[0].split('?')[0]
            
            if not filename or filename in ['.', '..', '']:
                continue
            
            if filename.endswith('.whl'):
                file_info = parse_wheel_filename(filename)
                if file_info.get('type') == 'wheel':
                    file_info['url'] = urljoin(nightly_url, link)
                    file_info['source'] = 'nightly'
                    files.append(file_info)
            elif filename.endswith(('.tar.gz', '.zip')):
                files.append({
                    'filename': filename,
                    'type': 'source',
                    'url': urljoin(nightly_url, link),
                    'source': 'nightly'
                })
        
        if files:
            print(f"  Found {len(files)} nightly files")
            return files
    
    print("  No nightly wheels found")
    return []


def scrape_package_files(base_url: str, package_name: str) -> List[Dict[str, str]]:
    """Scrape all files for a specific package (legacy method)"""
    
    # Try different index structures
    possible_urls = [
        urljoin(base_url, f"simple/{package_name}/"),
        urljoin(base_url, f"nightly/{package_name}/"),
        urljoin(base_url, f"{package_name}/"),
        urljoin(base_url, f"simple/{package_name}"),
        urljoin(base_url, f"nightly/{package_name}"),
    ]
    
    for package_url in possible_urls:
        content = fetch_url(package_url)
        if not content:
            continue
            
        parser = PyPIIndexParser()
        parser.feed(content)
        
        files = []
        for link in parser.links:
            # Extract filename from link
            filename = Path(urlparse(link).path).name
            if not filename:
                filename = link.split('/')[-1].split('#')[0]
            
            if filename.endswith('.whl'):
                file_info = parse_wheel_filename(filename)
                file_info['url'] = urljoin(package_url, link)
                files.append(file_info)
            elif filename.endswith(('.tar.gz', '.zip')):
                files.append({
                    'filename': filename,
                    'type': 'source',
                    'url': urljoin(package_url, link)
                })
        
        if files:
            print(f"  Found {len(files)} files for {package_name}")
            return files
    
    return []


def main():
    parser = argparse.ArgumentParser(
        description='Scrape vLLM wheels from PyPI server and GitHub releases',
        epilog="""
Examples:
  # Scrape all commits (default mode)
  python scrape_vllm_wheels.py
  
  # Scrape specific commit
  python scrape_vllm_wheels.py --commit 33f460b17a54acb3b6cc0b03f4a17876cff5eafd
  
  # Scrape GitHub releases
  python scrape_vllm_wheels.py --github-releases
  
  # Scrape nightly wheels
  python scrape_vllm_wheels.py --nightly
  
  # Scrape all sources (commits, releases, nightly)
  python scrape_vllm_wheels.py --all-sources
  
  # Save results to JSON file
  python scrape_vllm_wheels.py --output wheels.json
  
  # Show only wheel files (no source distributions)
  python scrape_vllm_wheels.py --wheels-only
  
  # Use legacy mode for standard PyPI structure
  python scrape_vllm_wheels.py --legacy-mode
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--base-url', default='https://wheels.vllm.ai/',
                        help='Base URL of the PyPI server')
    parser.add_argument('--output', '-o', help='Output file (JSON format)')
    parser.add_argument('--commit', help='Scrape specific commit only')
    parser.add_argument('--github-releases', action='store_true',
                        help='Scrape GitHub releases for wheels')
    parser.add_argument('--nightly', action='store_true',
                        help='Scrape nightly wheels')
    parser.add_argument('--release-versions', action='store_true',
                        help='Scrape release version wheels from wheels server')
    parser.add_argument('--all-sources', action='store_true',
                        help='Scrape all sources (commits, releases, nightly, release versions)')
    parser.add_argument('--legacy-mode', action='store_true',
                        help='Use legacy package-based discovery mode')
    parser.add_argument('--wheels-only', action='store_true',
                        help='Only show wheel files, not source distributions')
    parser.add_argument('--latest-only', action='store_true',
                        help='Only show latest version of each package')
    parser.add_argument('--max-commits', type=int, default=50,
                        help='Maximum number of commits to check (default: 50)')
    parser.add_argument('--max-releases', type=int, default=20,
                        help='Maximum number of releases to check (default: 20)')
    parser.add_argument('--max-versions', type=int, default=20,
                        help='Maximum number of versions to fetch from PyPI (default: 20)')
    parser.add_argument('--use-github', action='store_true',
                        help='Force use of GitHub API to discover commits')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    base_url = args.base_url.rstrip('/') + '/'
    
    all_results = {}
    
    # Determine which sources to scrape
    scrape_commits = True
    scrape_releases = args.github_releases or args.all_sources
    scrape_nightly = args.nightly or args.all_sources
    scrape_release_versions = args.release_versions or args.all_sources
    
    if args.legacy_mode:
        # Legacy package-based discovery
        packages = discover_packages(base_url)
        
        if not packages:
            print("No packages found!", file=sys.stderr)
            sys.exit(1)
        
        print(f"\nFound {len(packages)} packages: {', '.join(packages)}")
        
        # Scrape files for each package
        for package in packages:
            print(f"\nScraping {package}...")
            files = scrape_package_files(base_url, package)
            
            if args.wheels_only:
                files = [f for f in files if f.get('type') == 'wheel']
            
            if files:
                all_results[package] = files
                
        scrape_commits = False  # Don't scrape commits in legacy mode
    
    # Scrape GitHub releases
    if scrape_releases:
        print("\n" + "="*50)
        print("SCRAPING GITHUB RELEASES")
        print("="*50)
        
        releases = get_github_releases(max_releases=args.max_releases)
        
        for release in releases:
            print(f"\nRelease: {release['tag_name']} ({release['name']})")
            print(f"  Published: {release['published_at']}")
            print(f"  Prerelease: {release['prerelease']}")
            
            release_files = []
            for asset in release['assets']:
                file_info = parse_wheel_filename(asset['name'])
                if file_info.get('type') == 'wheel':
                    file_info['url'] = asset['download_url']
                    file_info['source'] = 'github_release'
                    file_info['release_tag'] = release['tag_name']
                    file_info['size'] = asset['size']
                    release_files.append(file_info)
            
            if args.wheels_only:
                release_files = [f for f in release_files if f.get('type') == 'wheel']
            
            if release_files:
                all_results[f"release_{release['tag_name']}"] = release_files
                print(f"  Found {len(release_files)} wheel files")
    
    # Scrape nightly wheels
    if scrape_nightly:
        print("\n" + "="*50)
        print("SCRAPING NIGHTLY WHEELS")
        print("="*50)
        
        nightly_files = scrape_nightly_wheels(base_url)
        
        if args.wheels_only:
            nightly_files = [f for f in nightly_files if f.get('type') == 'wheel']
        
        if nightly_files:
            all_results['nightly'] = nightly_files
    
    # Scrape release version wheels
    if scrape_release_versions:
        print("\n" + "="*50)
        print("SCRAPING RELEASE VERSION WHEELS")
        print("="*50)
        
        # Get versions from PyPI
        versions = get_pypi_versions(max_versions=args.max_versions)
        
        if versions:
            version_files_dict = scrape_release_version_wheels(base_url, versions)
            
            for version, files in version_files_dict.items():
                if args.wheels_only:
                    files = [f for f in files if f.get('type') == 'wheel']
                
                if files:
                    all_results[f"version_{version}"] = files
    
    # Scrape commits
    if scrape_commits and not (args.github_releases or args.nightly) or args.all_sources:
        print("\n" + "="*50)
        print("SCRAPING COMMIT WHEELS")
        print("="*50)
        
        # Commit-based discovery
        if args.commit:
            commits = [args.commit]
        else:
            if args.use_github:
                # Use GitHub API only
                commits = get_recent_commits_from_github(max_commits=args.max_commits)
                # Filter to only commits that have wheels
                print("Testing commits for wheel availability...")
                available_commits = []
                for commit in commits:
                    test_files = scrape_commit_files(base_url, commit)
                    if test_files:
                        available_commits.append(commit)
                        print(f"  ✓ Found wheels for commit {commit[:8]}")
                    else:
                        print(f"  ✗ No wheels for commit {commit[:8]}")
                    time.sleep(0.1)
                commits = available_commits
            else:
                commits = discover_commits(base_url)
                if args.max_commits and len(commits) > args.max_commits:
                    print(f"Limiting to {args.max_commits} most recent commits")
                    commits = commits[:args.max_commits]
        
        if not commits:
            print("No commits found!", file=sys.stderr)
        else:
            print(f"\nFound {len(commits)} commits to check")
            
            # Scrape files for each commit
            for i, commit in enumerate(commits, 1):
                print(f"\nScraping commit {i}/{len(commits)}: {commit[:8]}...")
                files = scrape_commit_files(base_url, commit)
                
                if args.wheels_only:
                    files = [f for f in files if f.get('type') == 'wheel']
                
                if files:
                    all_results[commit] = files
                    print(f"  Found {len(files)} files for commit {commit[:8]}")
    
    # Display results
    print("\n" + "="*50)
    print("RESULTS SUMMARY")
    print("="*50)
    
    for key, files in all_results.items():
        if args.legacy_mode:
            print(f"\nPackage: {key}")
            # Group by version for display
            versions = {}
            for file_info in files:
                version = file_info.get('version', 'unknown')
                if version not in versions:
                    versions[version] = []
                versions[version].append(file_info)
            
            # Sort versions (rough sort)
            sorted_versions = sorted(versions.keys(), reverse=True)
            
            if args.latest_only and sorted_versions:
                sorted_versions = [sorted_versions[0]]
            
            for version in sorted_versions:
                print(f"  Version {version}:")
                for file_info in versions[version]:
                    if file_info.get('type') == 'wheel':
                        print(f"    {file_info['filename']} ({file_info.get('python_tag', 'unknown')}-{file_info.get('abi_tag', 'unknown')}-{file_info.get('platform_tag', 'unknown')})")
                    else:
                        print(f"    {file_info['filename']} ({file_info.get('type', 'unknown')})")
                    
                    if args.verbose:
                        print(f"      URL: {file_info.get('url', 'N/A')}")
        elif key.startswith('release_'):
            release_tag = key.replace('release_', '')
            print(f"\nGitHub Release: {release_tag}")
            for file_info in files:
                if file_info.get('type') == 'wheel':
                    print(f"  {file_info['filename']} ({file_info.get('python_tag', 'unknown')}-{file_info.get('abi_tag', 'unknown')}-{file_info.get('platform_tag', 'unknown')})")
                else:
                    print(f"  {file_info['filename']} ({file_info.get('type', 'unknown')})")
                
                if args.verbose:
                    print(f"    URL: {file_info.get('url', 'N/A')}")
                    print(f"    Size: {file_info.get('size', 'N/A')} bytes")
        elif key == 'nightly':
            print(f"\nNightly Wheels:")
            for file_info in files:
                if file_info.get('type') == 'wheel':
                    print(f"  {file_info['filename']} ({file_info.get('python_tag', 'unknown')}-{file_info.get('abi_tag', 'unknown')}-{file_info.get('platform_tag', 'unknown')})")
                else:
                    print(f"  {file_info['filename']} ({file_info.get('type', 'unknown')})")
                
                if args.verbose:
                    print(f"    URL: {file_info.get('url', 'N/A')}")
        elif key.startswith('version_'):
            version = key.replace('version_', '')
            print(f"\nRelease Version: {version}")
            for file_info in files:
                if file_info.get('type') == 'wheel':
                    print(f"  {file_info['filename']} ({file_info.get('python_tag', 'unknown')}-{file_info.get('abi_tag', 'unknown')}-{file_info.get('platform_tag', 'unknown')})")
                else:
                    print(f"  {file_info['filename']} ({file_info.get('type', 'unknown')})")
                
                if args.verbose:
                    print(f"    URL: {file_info.get('url', 'N/A')}")
        else:
            print(f"\nCommit: {key}")
            for file_info in files:
                if file_info.get('type') == 'wheel':
                    print(f"  {file_info['filename']} ({file_info.get('python_tag', 'unknown')}-{file_info.get('abi_tag', 'unknown')}-{file_info.get('platform_tag', 'unknown')})")
                else:
                    print(f"  {file_info['filename']} ({file_info.get('type', 'unknown')})")
                
                if args.verbose:
                    print(f"    URL: {file_info.get('url', 'N/A')}")
    
    # Summary
    total_files = sum(len(files) for files in all_results.values())
    wheel_files = sum(len([f for f in files if f.get('type') == 'wheel']) 
                      for files in all_results.values())
    
    # Count different source types
    commit_count = len([k for k in all_results.keys() if not k.startswith('release_') and k != 'nightly' and not k.startswith('version_')])
    github_release_count = len([k for k in all_results.keys() if k.startswith('release_')])
    nightly_count = 1 if 'nightly' in all_results else 0
    version_count = len([k for k in all_results.keys() if k.startswith('version_')])
    
    # Save results
    if args.output:
        mode = 'legacy' if args.legacy_mode else 'multi-source'
        if args.commit:
            mode = 'single-commit'
        elif args.github_releases and not args.all_sources:
            mode = 'github-releases'
        elif args.nightly and not args.all_sources:
            mode = 'nightly'
        
        output_data = {
            'scrape_time': datetime.now().isoformat(),
            'base_url': base_url,
            'mode': mode,
            'sources': {
                'commits': commit_count,
                'github_releases': github_release_count,
                'nightly': nightly_count,
                'release_versions': version_count
            },
            'results': all_results
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to {args.output}")
    
    print(f"\nSummary:")
    
    if args.legacy_mode:
        print(f"  Packages: {len(all_results)}")
    else:
        if commit_count > 0:
            print(f"  Commits: {commit_count}")
        if github_release_count > 0:
            print(f"  GitHub Releases: {github_release_count}")
        if nightly_count > 0:
            print(f"  Nightly Wheels: {nightly_count}")
        if version_count > 0:
            print(f"  Release Versions: {version_count}")
    
    print(f"  Total files: {total_files}")
    print(f"  Wheel files: {wheel_files}")
    print(f"  Source files: {total_files - wheel_files}")
    
    # Installation examples
    if wheel_files > 0:
        print(f"\nInstallation Examples:")
        
        # Example from nightly
        if 'nightly' in all_results:
            nightly_wheels = [f for f in all_results['nightly'] if f.get('type') == 'wheel']
            if nightly_wheels:
                print(f"  # Install nightly wheel:")
                print(f"  uv pip install vllm --extra-index-url https://wheels.vllm.ai/nightly --torch-backend auto")
        
        # Example from GitHub releases
        github_release_keys = [k for k in all_results.keys() if k.startswith('release_')]
        if github_release_keys:
            release_key = github_release_keys[0]
            release_wheels = [f for f in all_results[release_key] if f.get('type') == 'wheel']
            if release_wheels:
                example_wheel = release_wheels[0]
                release_tag = release_key.replace('release_', '')
                print(f"  # Install GitHub release wheel ({release_tag}):")
                print(f"  uv pip install {example_wheel['url']}")
        
        # Example from release versions
        version_keys = [k for k in all_results.keys() if k.startswith('version_')]
        if version_keys:
            version_key = version_keys[0]
            version_wheels = [f for f in all_results[version_key] if f.get('type') == 'wheel']
            if version_wheels:
                example_wheel = version_wheels[0]
                version = version_key.replace('version_', '')
                print(f"  # Install release version wheel ({version}):")
                print(f"  uv pip install -U vllm=={version} --extra-index-url https://wheels.vllm.ai/{version} --torch-backend auto")
        
        # Example from commits
        commit_keys = [k for k in all_results.keys() if not k.startswith('release_') and k != 'nightly' and not k.startswith('version_')]
        if commit_keys:
            commit_key = commit_keys[0]
            commit_wheels = [f for f in all_results[commit_key] if f.get('type') == 'wheel']
            if commit_wheels:
                example_wheel = commit_wheels[0]
                print(f"  # Install commit wheel ({commit_key[:8]}):")
                print(f"  export VLLM_COMMIT={commit_key}")
                print(f"  uv pip install vllm --extra-index-url https://wheels.vllm.ai/${{VLLM_COMMIT}} --torch-backend auto")


if __name__ == "__main__":
    main() 