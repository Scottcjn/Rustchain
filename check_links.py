# SPDX-License-Identifier: MIT
"""Link checker for RustChain documentation."""

import re
import requests
from urllib.parse import urljoin, urlparse
import os

def check_links_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all markdown links [text](url)
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    links = re.findall(link_pattern, content)
    
    # Also find raw URLs
    url_pattern = r'https?://[^\s\)>\]]+'
    raw_urls = re.findall(url_pattern, content)
    
    print(f"Found {len(links)} markdown links and {len(raw_urls)} raw URLs")
    print("\n=== Checking markdown links ===")
    
    broken = []
    for text, url in links:
        if url.startswith('#'):
            continue  # Skip anchor links
        if url.startswith('mailto:'):
            continue
        
        # Check if it's a relative file link
        if not url.startswith('http'):
            # Check if file exists
            if os.path.exists(url):
                print(f"✅ {text} -> {url} (local file exists)")
            else:
                print(f"❌ {text} -> {url} (local file NOT found)")
                broken.append((text, url))
            continue
        
        # Check HTTP links
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                print(f"✅ {text} -> {url} ({resp.status_code})")
            else:
                print(f"❌ {text} -> {url} ({resp.status_code})")
                broken.append((text, url))
        except Exception as e:
            print(f"⚠️  {text} -> {url} (Error: {e})")
            broken.append((text, url))
    
    print(f"\n=== Summary ===")
    print(f"Broken links found: {len(broken)}")
    for text, url in broken:
        print(f"  - [{text}]({url})")
    
    return broken

if __name__ == "__main__":
    broken = check_links_in_file("README.md")
