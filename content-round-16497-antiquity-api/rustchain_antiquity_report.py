#!/usr/bin/env python3
"""Print a small report from RustChain /api/miners JSON.

Usage:
  python rustchain_antiquity_report.py sample_miners.json

The script uses only the Python standard library and works with either a saved
/api/miners response or another JSON object containing a top-level `miners`
array with `miner`, `device_arch`, and `antiquity_multiplier` fields.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def load_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_report(payload: dict) -> str:
    miners = payload.get("miners", [])
    rows = []
    for miner in miners:
        rows.append(
            (
                str(miner.get("miner", "")),
                str(miner.get("device_arch", "?")),
                float(miner.get("antiquity_multiplier", 1.0)),
            )
        )

    rows.sort(key=lambda row: (-row[2], row[0]))
    lines = ["miner\tarch\tantiquity_multiplier"]
    lines.extend(f"{miner}\t{arch}\t{multiplier:.2f}x" for miner, arch, multiplier in rows)

    if rows:
        multipliers = [row[2] for row in rows]
        lines.append("")
        lines.append(
            "count={} average_multiplier={:.2f}x max_multiplier={:.2f}x".format(
                len(multipliers),
                statistics.fmean(multipliers),
                max(multipliers),
            )
        )
    else:
        lines.append("")
        lines.append("count=0")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python rustchain_antiquity_report.py <miners.json>", file=sys.stderr)
        return 2

    payload = load_payload(argv[1])
    print(build_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
