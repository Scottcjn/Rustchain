#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
check_relative_links.py - Verify relative markdown links across the repository.

For every ``*.md`` file it checks that
  * ``[text](path)`` / ``![alt](path)`` links and ``<a href>`` / ``<img src>``
    attributes that are not external URLs point at a file that exists, and
  * the ``#fragment`` of a relative link matches a heading (or an ``id``/``name``
    anchor) in the target file, using GitHub's slug rules.

Fails with a non-zero exit code if any internal file, relative link or anchor is
missing, so CI (``ci.yml`` -> "Verify relative documentation links") blocks link
rot instead of only reporting it. External URLs are left to the lychee job.
"""

import os
import re
import sys
import unicodedata
import urllib.parse

# [text](target) and ![alt](target); angle-bracket destinations <a b> included.
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*(?:<([^>]*)>|([^\s)]+))")
HTML_ATTR = re.compile(r"""<(?:a|img)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
SKIP_PREFIXES = ("#", "http://", "https://", "mailto:", "//", "data:", "javascript:", "{{")
# Variation selectors and zero-width joiners are invisible inside a browser anchor,
# so they are ignored on both sides: the heading slug and the link fragment.
_INVISIBLE = "".join(chr(c) for c in range(0xFE00, 0xFE10)) \
    + "".join(chr(c) for c in range(0x200B, 0x2010)) + "\ufeff"


def split_link(link: str):
    """Return (path, fragment) for a raw link, ignoring query strings."""
    target = link.strip().split("?")[0].strip()
    path, _, fragment = target.partition("#")
    return path, urllib.parse.unquote(fragment)


def slug(heading: str) -> str:
    """GitHub's anchor slug: lowercase, punctuation dropped, and every remaining
    space becomes a hyphen - runs are not collapsed and hyphens are not trimmed,
    so '## 1. Network & Status' slugs as '1-network--status'. Letters, combining
    marks (Indic/CJK) and numbers survive."""
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    kept = [c for c in text if c not in _INVISIBLE
            and (c in " -_" or c.isalnum() or unicodedata.category(c)[0] in "MN")]
    return "".join(kept).replace(" ", "-")


def anchors(file_path: str) -> frozenset:
    """Every anchor a markdown renderer will generate for this file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    except OSError:
        return frozenset()

    found, in_code = set(), False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        setext = re.match(r"^\s*[=-]+\s*$", line)
        html_heading = re.match(r"<h[1-6][^>]*>(.*?)</h[1-6]>", line.strip(), re.IGNORECASE | re.DOTALL)
        summary = re.search(r"<summary>(.*?)</summary>", line, re.IGNORECASE)
        if heading:
            found.add(slug(heading.group(1)))
        elif setext and i and lines[i - 1].strip():
            found.add(slug(lines[i - 1]))
        elif html_heading:
            found.add(slug(html_heading.group(1)))
        elif summary:
            found.add(slug(summary.group(1)))
        for name in re.findall(r"<a[^>]*\b(?:name|id)\s*=\s*[\"']([^\"']+)", line, re.IGNORECASE) \
                + re.findall(r"\bid\s*=\s*[\"']([^\"']+)", line):
            found.add(slug(name))
    found.discard("")
    return frozenset(found)


def check_file(file_path: str, repo_root: str) -> list:
    broken = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Skip inside code blocks (``` ... ```) and inline `code` spans to avoid false
    # positives in templates and examples
    clean_content = re.sub(r"```[\s\S]*?```", "", content)
    clean_content = re.sub(r"`[^`\n]*`", "", clean_content)

    links = [a or b for a, b in MD_LINK.findall(clean_content)] + HTML_ATTR.findall(clean_content)
    file_dir = os.path.dirname(file_path)
    rel_file = os.path.relpath(file_path, repo_root)

    for link in links:
        # Ignore external URLs, mailto, and placeholder variables
        if link.strip().startswith(SKIP_PREFIXES):
            continue
        path, fragment = split_link(link)
        if not path:
            continue  # same-file anchor, checked below

        if path.startswith("/"):
            target_path = os.path.normpath(os.path.join(repo_root, path.lstrip("/")))
        else:
            target_path = os.path.normpath(os.path.join(file_dir, path))
        if not os.path.exists(target_path):
            broken.append((rel_file, link, f"{path} not found"))
            continue  # a missing file already explains a missing anchor

        if fragment and slug(fragment) not in anchors(target_path):
            broken.append((rel_file, link, f"{path}#{fragment}: no such heading"))

    # same-file anchors: [text](#section) must match a heading in this file
    local = anchors(file_path)
    for link in links:
        if not link.strip().startswith("#"):
            continue
        _, fragment = split_link(link)
        if fragment and slug(fragment) not in local:
            broken.append((rel_file, link, f"{link}: no such heading"))

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
                all_broken.extend(check_file(os.path.join(root, f), repo_root))

    if all_broken:
        print(f"\n[FAIL] {len(all_broken)} broken relative link(s):")
        for rel_file, link, why in all_broken:
            print(f"  - {rel_file}: {link} -> {why}")
        sys.exit(1)

    print("\n[OK] All relative links and anchors resolved successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
