# SPDX-License-Identifier: MIT
"""Enforce relative markdown links so docs can't silently rot again.

Checks every relative link (inline + reference style) in *.md files: target file
must exist and any #anchor must match a heading/HTML anchor in the target.
External http(s)/mailto links are skipped here (lychee CI reports those; they may
be flaky). Template placeholders like {{BASE_URL}} are skipped. Exit 1 on breakage.

Usage: python scripts/check_links.py [repo_root]
"""
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"!?\[[^\]]*\]\(<?([^)>\s]+)>?(?:\s+[\"'][^\"']*[\"'])?\)")
DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s+<?([^\s>]+)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
EXT_RE = re.compile(r"^(?:https?://|mailto:|data:)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
HTML_ANCHOR_RE = re.compile(r'<a\s+(?:name|id)="([^"]+)"')
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def slugify(text: str) -> str:
    """GitHub-style heading slug: lowercase; letters/digits/_/-/combining marks kept
    (GitHub keeps Unicode marks like U+FE0F and Devanagari matras); other punctuation
    dropped in place; spaces become hyphens. '## 🚀 Quick Start' -> '-quick-start',
    '## ⚙️ Configuration' -> '\uFE0F-configuration'."""
    return "".join(
        "-" if ch.isspace() else ch
        for ch in text.strip().lower()
        if ch.isspace() or ch.isalnum() or ch in "_-" or unicodedata.category(ch)[0] == "M"
    )


def anchors_of(md_path: Path, _cache: dict) -> set:
    """Heading slugs + explicit <a name/id> anchors of a markdown file."""
    if md_path not in _cache:
        found, counts = set(), {}
        try:
            for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = HEADING_RE.match(line)
                if m:
                    base = slugify(m.group(1))
                    n = counts.get(base, 0)
                    counts[base] = n + 1
                    found.add(base if n == 0 else f"{base}-{n}")
                found.update(HTML_ANCHOR_RE.findall(line))
        except OSError:
            found = set()
        _cache[md_path] = found
    return _cache[md_path]


def iter_md(root: Path):
    for path in sorted(root.rglob("*.md")):
        rel_parts = path.relative_to(root).parts[:-1]
        if any(part in SKIP_DIRS or (part.startswith(".") and part != ".") for part in rel_parts):
            continue
        yield path


def check_tree(root: Path) -> list:
    """Return ["file:line -> target (reason)", ...] for every broken relative link."""
    root = root.resolve()
    broken, anchor_cache = [], {}

    def resolve(md_path: Path, url: str):
        base = root / url.lstrip("/") if url.startswith("/") else md_path.parent / url
        return Path(unquote(str(base))).resolve()

    for md_path in iter_md(root):
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # unreadable file is itself a rot signal
            broken.append(f"{md_path.relative_to(root)}:1 -> <read error: {exc}>")
            continue
        fence = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if FENCE_RE.match(line):
                fence = not fence
                continue
            if fence or "{{" in line:  # skip fenced blocks and templated lines
                continue
            for url in LINK_RE.findall(line) + DEF_RE.findall(line):
                if EXT_RE.match(url) or "?" in url:
                    continue
                path_part, _, frag = url.partition("#")
                frag = unquote(frag)  # GitHub decodes percent-escaped fragments
                if not path_part:  # same-file anchor
                    if frag and frag.lower() not in {a.lower() for a in anchors_of(md_path, anchor_cache)}:
                        broken.append(f"{md_path.relative_to(root)}:{lineno} -> {url} (missing anchor)")
                    continue
                target = resolve(md_path, path_part)
                if not target.exists():
                    broken.append(f"{md_path.relative_to(root)}:{lineno} -> {url} (file not found)")
                elif frag and target.suffix == ".md" and target.is_file() and frag.lower() not in {
                    a.lower() for a in anchors_of(target, anchor_cache)
                }:
                    broken.append(f"{md_path.relative_to(root)}:{lineno} -> {url} (missing anchor)")
    return broken


def main(argv=None) -> int:
    root = Path(argv[1]) if argv and len(argv) > 1 else Path(__file__).resolve().parent.parent
    broken = check_tree(root)
    for item in broken:
        print(f"BROKEN LINK {item}")
    print(f"link gate: {len(broken)} broken relative link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
