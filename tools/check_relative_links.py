#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
check_relative_links.py — Verify relative markdown and HTML links across repository.
Fails with non-zero exit code if any internal file or relative link is missing.
"""

import os
import re
import sys
import glob

def check_file(file_path: str, repo_root: str) -> list:
    broken = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Skip inside code blocks (``` ... ```)
    # Replace triple-backtick code blocks with empty strings to avoid false positives in templates/examples
    clean_content = re.sub(r"```[\s\S]*?```", "", content)

    # Match standard markdown links: [text](link)
    md_links = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", clean_content)
    file_dir = os.path.dirname(file_path)

    for text, link in md_links:
        link = link.strip()
        # Ignore external URLs, anchors, mailto, and placeholder variables
        if link.startswith(("#", "http://", "https://", "mailto:", "{{")):
            continue
        # Strip anchor or query params
        target = link.split("#")[0].split("?")[0].strip()
        if not target:
            continue

        # Check path relative to current markdown file
        target_path = os.path.normpath(os.path.join(file_dir, target))
        if not os.path.exists(target_path):
            rel_file = os.path.relpath(file_path, repo_root)
            broken.append((rel_file, text, link, target))

    return broken

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Scanning markdown files in {repo_root} for broken relative links...")

    all_broken = []
    for root, dirs, files in os.walk(repo_root):
        # Skip .git, venv, and node_modules directories
        dirs[:] = [d for d in dirs if d not in (".git", "venv", ".venv", "node_modules", "__pycache__")]
        for f in files:
            if f.endswith(".md"):
                p = os.path.join(root, f)
                broken = check_file(p, repo_root)
                all_broken.extend(broken)

    if all_broken:
        print(f"\n❌ Found {len(all_broken)} broken relative link(s):")
        for rel_file, text, link, target in all_broken:
            print(f"  • {rel_file}: [{text}]({link}) -> '{target}' not found")
        sys.exit(1)

    print("\n✅ All relative links resolved successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
