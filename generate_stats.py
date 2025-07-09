#!/usr/bin/env python3
"""
Generate stats JSON file from wheels JSON data
"""
import json
import os
from datetime import datetime

def main():
    # Read JSON data
    with open('data/wheels.json', 'r') as f:
        data = json.load(f)

    # Calculate statistics
    stats = {
        'last_updated': datetime.now().isoformat(),
        'total_sources': len(data.get('results', {})),
        'total_files': sum(len(files) for files in data.get('results', {}).values()),
        'total_wheels': 0,
        'source_counts': {
            'commits': 0,
            'github_releases': 0,
            'nightly': 0,
            'release_versions': 0
        },
        'python_versions': {},
        'platforms': {}
    }

    # Count by source type and collect metadata
    for source_key, files in data.get('results', {}).items():
        wheel_files = [f for f in files if f.get('type') == 'wheel']
        stats['total_wheels'] += len(wheel_files)
        
        if source_key.startswith('release_'):
            stats['source_counts']['github_releases'] += 1
        elif source_key.startswith('version_'):
            stats['source_counts']['release_versions'] += 1
        elif source_key == 'nightly':
            stats['source_counts']['nightly'] += 1
        else:
            stats['source_counts']['commits'] += 1
        
        # Count Python versions and platforms
        for file_info in wheel_files:
            py_tag = file_info.get('python_tag', 'unknown')
            platform_tag = file_info.get('platform_tag', 'unknown')
            
            stats['python_versions'][py_tag] = stats['python_versions'].get(py_tag, 0) + 1
            stats['platforms'][platform_tag] = stats['platforms'].get(platform_tag, 0) + 1

    # Write stats file
    os.makedirs('data', exist_ok=True)
    with open('data/stats.json', 'w') as f:
        json.dump(stats, f, indent=2)

    print(f'Generated stats: {stats["total_wheels"]} wheels from {stats["total_sources"]} sources')

if __name__ == '__main__':
    main() 