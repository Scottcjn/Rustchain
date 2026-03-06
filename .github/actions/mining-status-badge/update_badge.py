#!/usr/bin/env python3
"""Update README mining status badge."""
import os
import sys
from pathlib import Path

def main():
    readme_path = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    wallet = os.environ.get("WALLET", "frozen-factorio-ryan")
    style = os.environ.get("STYLE", "flat-square")
    readme = Path(readme_path)
    if not readme.exists():
        print(f"README not found: {readme_path}")
        sys.exit(1)
    text = readme.read_text(encoding="utf-8")
    start = "<!-- rustchain-mining-badge-start -->"
    end = "<!-- rustchain-mining-badge-end -->"
    badge_url = f"https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/{wallet}&style={style}"
    block = f"{start}\n![RustChain Mining Status]({badge_url})\n{end}"
    start_idx = text.find(start)
    end_idx = text.find(end)
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        new = text[:start_idx] + block + text[end_idx + len(end):]
    else:
        new = text.rstrip() + "\n\n## Mining Status\n" + block + "\n"
    readme.write_text(new, encoding="utf-8")
    print(f"Updated {readme_path} with mining badge for wallet: {wallet}")

if __name__ == "__main__":
    main()
