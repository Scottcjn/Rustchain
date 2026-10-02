#!/usr/bin/env python3
"""Check relative links (and fragments) in Markdown files.

External URLs are *not* fetched: network checks are flaky in CI, so this
script only enforces the rules that must never rot silently:

* every local/relative link points at a file that exists in the repo;
* every ``#fragment`` resolves to a heading (or explicit anchor) in the
  target Markdown file.

Usage:
    python3 scripts/check_links.py [PATH ...]

PATH may be a file or a directory. Directories are scanned recursively for
``*.md`` files. With no arguments the whole repository is scanned.

Exit code is 0 when every relative link resolves, 1 otherwise.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

# Directories that never contain authored documentation we want to lint.
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "target",
    "build",
    "dist",
    ".next",
    "vendor",
}

# Schemes/prefixes that are not relative links.
EXTERNAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

# Markdown inline links/images: [text](target) and ![alt](target).
INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")

# Explicit HTML anchors: <a name="..."></a> / id="..."
HTML_ANCHOR_RE = re.compile(r"""<a\s+[^>]*(?:name|id)=["']([^"']+)["']""", re.IGNORECASE)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def github_slug(text: str) -> str:
    """Reproduce GitHub's heading -> anchor slug algorithm."""
    text = text.strip().lower()
    out = []
    for ch in text:
        if ch in (" ", "-"):
            out.append("-")
            continue
        # Keep letters, numbers and combining marks (Unicode aware, so
        # CJK/Devanagari/authors' scripts survive); drop symbols/emoji and
        # other punctuation, matching GitHub's slugger.
        if ch == "_" or unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch)
    return "".join(out)


def slugs_for(md_path: Path) -> set[str]:
    slugs: set[str] = set()
    try:
        content = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return slugs
    for line in content.splitlines():
        m = HEADING_RE.match(line)
        if m:
            slugs.add(github_slug(m.group(2)))
    for m in HTML_ANCHOR_RE.finditer(content):
        slugs.add(m.group(1).lower())
    return slugs


def is_external(target: str) -> bool:
    if target.startswith("//"):
        return True
    if target.startswith("#"):
        return False
    return bool(EXTERNAL_RE.match(target))


def iter_markdown(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for name in filenames:
                    if name.lower().endswith(".md"):
                        files.append(Path(dirpath) / name)
        elif p.suffix.lower() == ".md":
            files.append(p)
    return sorted(set(files))


def check_file(md_path: Path, repo_root: Path) -> list[str]:
    problems: list[str] = []
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{md_path}: cannot read ({exc})"]

    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in INLINE_LINK_RE.finditer(line):
            target = m.group(1).strip()
            if not target or is_external(target):
                continue

            split = urlsplit(target)
            link_path = unquote(split.path)
            fragment = unquote(split.fragment)

            if link_path:
                # GitHub resolves root-relative links (and, in practice,
                # most author intent here) against the repository root;
                # other relative links resolve against the file's folder.
                if link_path.startswith("/"):
                    resolved = (repo_root / link_path.lstrip("/")).resolve()
                else:
                    resolved = (md_path.parent / link_path).resolve()

                try:
                    resolved.relative_to(repo_root.resolve())
                except ValueError:
                    problems.append(
                        f"{md_path}:{lineno}: link escapes repo: {target}"
                    )
                    continue

                if not resolved.exists():
                    problems.append(
                        f"{md_path}:{lineno}: missing file: {target}"
                    )
                    continue
                target_file = resolved
            else:
                target_file = md_path

            if (
                fragment
                and target_file.suffix.lower() == ".md"
                and fragment not in slugs_for(target_file)
            ):
                problems.append(
                    f"{md_path}:{lineno}: missing anchor #{fragment} in "
                    f"{target_file.relative_to(repo_root)}"
                )
    return problems


def main(argv: list[str]) -> int:
    repo_root = Path.cwd().resolve()
    paths = argv[1:] or ["."]
    files = [f.resolve() for f in iter_markdown(paths)]
    if not files:
        print("check_links: no markdown files found", file=sys.stderr)
        return 0

    all_problems: list[str] = []
    for md in files:
        all_problems.extend(check_file(md, repo_root))

    if all_problems:
        print(f"check_links: {len(all_problems)} broken relative link(s):\n")
        for problem in all_problems:
            print(f"  {problem}")
        print("\nFix the link or remove it, then re-run: python3 scripts/check_links.py")
        return 1

    print(f"check_links: OK - checked {len(files)} markdown file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
