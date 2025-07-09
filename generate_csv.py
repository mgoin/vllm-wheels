#!/usr/bin/env python3
"""
Generate CSV file from wheels JSON data
"""
import json
import csv
import os
from datetime import datetime

def main():
    # Read JSON data
    with open('data/wheels.json', 'r') as f:
        data = json.load(f)

    # Create CSV data
    csv_data = []
    for source_key, files in data.get('results', {}).items():
        if not files:
            continue
        
        for file_info in files:
            if file_info.get('type') != 'wheel':
                continue
                
            # Determine source type and metadata
            source_type = 'commit'
            source_info = source_key
            install_command = ''
            
            if source_key.startswith('release_'):
                source_type = 'github_release'
                source_info = source_key.replace('release_', '')
                install_command = f'uv pip install {file_info.get("url", "")} --torch-backend auto'
            elif source_key.startswith('version_'):
                source_type = 'release_version'
                source_info = source_key.replace('version_', '')
                install_command = f'uv pip install -U vllm=={source_info} --extra-index-url https://wheels.vllm.ai/{source_info} --torch-backend auto'
            elif source_key == 'nightly':
                source_type = 'nightly'
                source_info = 'nightly'
                install_command = 'uv pip install vllm --extra-index-url https://wheels.vllm.ai/nightly --torch-backend auto'
            else:
                # Regular commit
                install_command = f'uv pip install vllm --extra-index-url https://wheels.vllm.ai/{source_key} --torch-backend auto'
            
            csv_data.append({
                'filename': file_info.get('filename', ''),
                'source_type': source_type,
                'source_info': source_info,
                'version': file_info.get('version', ''),
                'python_tag': file_info.get('python_tag', ''),
                'abi_tag': file_info.get('abi_tag', ''),
                'platform_tag': file_info.get('platform_tag', ''),
                'url': file_info.get('url', ''),
                'install_command': install_command,
                'commit': file_info.get('commit', ''),
                'release_tag': file_info.get('release_tag', ''),
                'size': file_info.get('size', ''),
                'scraped_at': data.get('scrape_time', '')
            })

    # Write CSV file
    os.makedirs('data', exist_ok=True)
    with open('data/wheels.csv', 'w', newline='') as f:
        if csv_data:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        else:
            # Write empty CSV with headers
            writer = csv.writer(f)
            writer.writerow(['filename', 'source_type', 'source_info', 'version', 'python_tag', 'abi_tag', 'platform_tag', 'url', 'install_command', 'commit', 'release_tag', 'size', 'scraped_at'])

    print(f'Generated CSV with {len(csv_data)} wheel entries')

if __name__ == '__main__':
    main() 