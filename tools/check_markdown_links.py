#!/usr/bin/env python3
"""
Markdown Link Verification Script for Rustchain.
Scans every markdown document for broken relative file links and malformed paths.
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# Vendored and generated trees are not documentation we own.
EXCLUDED_DIRS = {".git", "target", "node_modules", "vendor", ".venv", "venv"}

def markdown_files():
    files = []
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        files.append(path)
    return sorted(files)

def check_markdown_links():
    md_files = markdown_files()
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
                # Placeholder and template links are not filesystem paths.
                if clean_url in {"url", "URL", "link", "your-link", "..."} or "{{" in clean_url:
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
