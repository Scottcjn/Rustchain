import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
#!/usr/bin/env python3
"""
Markdown Link Verification Script for Rustchain.
Scans all markdown documents for broken relative file links and malformed paths.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check_markdown_links():
    md_files = list(ROOT.glob("*.md")) + list(ROOT.glob(".github/**/*.md")) + list(ROOT.glob("docs/**/*.md"))
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    broken_links = []
    checked_count = 0

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Error reading {md_file}: {e}")
            continue

        for lineno, line in enumerate(content.splitlines(), 1):
            matches = link_pattern.findall(line)
            for text, url in matches:
                checked_count += 1
                # Skip external links and internal page anchors
                if url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:") or url.startswith("#"):
                    continue
                clean_url = url.split("#")[0].split("?")[0].strip()
                if not clean_url:
                    continue
                target = (md_file.parent / clean_url).resolve()
                if not target.exists():
                    broken_links.append((md_file.relative_to(ROOT), lineno, text, url))

    print(f"Checked {checked_count} links across {len(md_files)} markdown files.")
    if broken_links:
        print(f"\n[FAIL] Found {len(broken_links)} broken relative link(s):")
        for file_path, lineno, text, url in broken_links:
            print(f"  {file_path}:{lineno}: [{text}]({url})")
        return 1

    print("[PASS] All relative markdown links are valid and resolve successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(check_markdown_links())
