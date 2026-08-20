#!/usr/bin/env python3
"""Validate local Markdown and HTML links without making network requests."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)")
HTML_LINK = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
SKIPPED_SCHEMES = ("http:", "https:", "mailto:", "tel:", "data:", "javascript:")


def files_under(root: Path, inputs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in inputs:
        path = (root / raw).resolve()
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob("*.md"))
            files.update(path.rglob("*.html"))
    return sorted(files)


def local_targets(document: Path) -> set[str]:
    text = document.read_text(encoding="utf-8")
    # HTML-looking snippets inside Markdown code fences are examples, not
    # links in the document itself. Only parse HTML attributes in real HTML.
    targets = set(MARKDOWN_LINK.findall(text))
    if document.suffix.lower() == ".html":
        targets |= set(HTML_LINK.findall(text))
    return targets


def check(root: Path, documents: list[Path]) -> list[str]:
    failures: list[str] = []
    root = root.resolve()
    for document in documents:
        for raw in local_targets(document):
            parsed = urlsplit(unquote(raw))
            if parsed.scheme or raw.startswith("#") or raw.startswith("/"):
                continue
            target = (document.parent / parsed.path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                failures.append(f"{document}: link escapes repository: {raw}")
                continue
            if not target.exists():
                failures.append(f"{document}: missing target: {raw}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files or directories to inspect")
    args = parser.parse_args()
    root = Path.cwd()
    documents = files_under(root, args.paths)
    failures = check(root, documents)
    if failures:
        print("Relative link check failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print(f"Checked {len(documents)} Markdown/HTML files; all local targets exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
