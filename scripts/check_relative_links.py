#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check_markdown_links():
    errors = []
    checked_count = 0
    md_files = list(ROOT.glob("*.md")) + list(ROOT.glob("docs/**/*.md"))
    
    link_regex = re.compile(r'\[([^\]]+)\]\(([^)#?]+)(?:#[^)]*)?\)')

    for md in md_files:
        if ".git" in str(md):
            continue
        try:
            with open(md, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            for text, link in link_regex.findall(content):
                link = link.strip()
                # Skip external protocols, mailto, anchor only
                if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:") or link.startswith("#") or not link:
                    continue
                
                checked_count += 1
                target = (md.parent / link).resolve()
                if not target.exists():
                    # check relative to repo root
                    target_root = (ROOT / link.lstrip("/")).resolve()
                    if not target_root.exists():
                        errors.append(f"{md.relative_to(ROOT)}: Broken link [{text}]({link})")
        except Exception as e:
            print(f"Error checking {md}: {e}")

    print(f"Link check complete: {checked_count} relative links validated across {len(md_files)} markdown documents.")
    if errors:
        print(f"FAILED: {len(errors)} broken relative link(s) found:")
        for err in errors[:10]:
            print(f"  - {err}")
        return False
    else:
        print("SUCCESS: All relative markdown links resolve successfully.")
        return True

if __name__ == "__main__":
    success = check_markdown_links()
    if not success:
        sys.exit(1)
