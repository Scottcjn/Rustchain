#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
check_relative_links.py — Verify relative markdown and HTML links across repository.
Fails with non-zero exit code if any internal file or relative link is missing.

Closes: Scottcjn/Rustchain#7910, #7908, #7886, #7885, #7792 (Bounty #16248).
"""

import argparse
import os
import re
import sys
from typing import List, Tuple

IGNORE_PREFIXES = ("#", "http://", "https://", "mailto:", "tel:", "data:", "javascript:", "{{")


def strip_code_regions(content: str) -> str:
    """Remove fenced code blocks and inline code spans to avoid template false positives."""
    no_fenced = re.sub(r"```[\s\S]*?```", "", content)
    no_inline = re.sub(r"`[^`\n]+`", "", no_fenced)
    return no_inline


def extract_links_from_markdown(clean_content: str) -> List[Tuple[str, str]]:
    """Extract both Markdown `[text](link)` and HTML `href`/`src` links."""
    links: List[Tuple[str, str]] = []
    for text, link in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", clean_content):
        links.append((text, link.strip()))
    for attr, link in re.findall(r'\b(href|src)=["\']([^"\']+)["\']', clean_content, flags=re.IGNORECASE):
        links.append((f"<{attr}>", link.strip()))
    return links


def check_file(file_path: str, repo_root: str) -> List[Tuple[str, str, str, str]]:
    broken: List[Tuple[str, str, str, str]] = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    clean_content = strip_code_regions(content)
    links = extract_links_from_markdown(clean_content)
    file_dir = os.path.dirname(file_path)

    for text, link in links:
        if not link or link.startswith(IGNORE_PREFIXES):
            continue
        # Strip optional title in markdown link: `path/to/file.md "Title"`
        raw_target = link.split()[0] if " " in link and not os.path.exists(os.path.join(file_dir, link)) else link
        target = raw_target.split("#")[0].split("?")[0].strip()
        if not target:
            continue

        if target.startswith("/"):
            target_path = os.path.normpath(os.path.join(repo_root, target.lstrip("/")))
        else:
            target_path = os.path.normpath(os.path.join(file_dir, target))
        if not os.path.exists(target_path):
            rel_file = os.path.relpath(file_path, repo_root)
            broken.append((rel_file, text, link, target))

    return broken


def scan_repository(repo_root: str, target_paths: List[str] | None = None) -> List[Tuple[str, str, str, str]]:
    all_broken: List[Tuple[str, str, str, str]] = []
    if target_paths:
        for rel_p in target_paths:
            full_p = os.path.abspath(os.path.join(repo_root, rel_p))
            if os.path.isfile(full_p):
                all_broken.extend(check_file(full_p, repo_root))
        return all_broken

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in (".git", "venv", ".venv", "node_modules", "__pycache__")]
        for f in files:
            if f.endswith(".md"):
                p = os.path.join(root, f)
                all_broken.extend(check_file(p, repo_root))
    return all_broken


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify relative markdown and HTML links across repository.")
    parser.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), help="Repository root directory")
    parser.add_argument("paths", nargs="*", help="Optional specific markdown files to check")
    args = parser.parse_args(argv)

    repo_root = os.path.abspath(args.root)
    print(f"Scanning markdown files in {repo_root} for broken relative links...")
    all_broken = scan_repository(repo_root, args.paths or None)

    if all_broken:
        print(f"\nFound {len(all_broken)} broken relative link(s):")
        for rel_file, text, link, target in all_broken:
            print(f"  - {rel_file}: [{text}]({link}) -> '{target}' not found")
        return 1

    print("\nAll relative links resolved successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
