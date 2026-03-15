#!/usr/bin/env python3
"""RustChain Badge Generator — Create SVG badges for miner achievements."""
BADGE_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20">
<rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{rw}" height="20" fill="{color}"/>
<text x="{ltx}" y="14" fill="#fff" font-family="monospace" font-size="11">{label}</text>
<text x="{rtx}" y="14" fill="#fff" font-family="monospace" font-size="11">{value}</text>
</svg>'''

def badge(label, value, color="#8b5cf6"):
    lw = len(label) * 7 + 12; rw = len(str(value)) * 7 + 12; w = lw + rw
    return BADGE_TEMPLATE.format(w=w, lw=lw, rw=rw, color=color, label=label, value=value,
                                  ltx=lw//2, rtx=lw + rw//2)

def generate_miner_badges(miner_id, blocks=0, mult=1.0, uptime=0):
    badges = [
        badge("miner", miner_id[:12]),
        badge("blocks", str(blocks), "#22c55e" if blocks > 100 else "#eab308"),
        badge("multiplier", f"{mult}x", "#8b5cf6"),
        badge("uptime", f"{uptime:.0f}%", "#22c55e" if uptime > 95 else "#ef4444"),
    ]
    for i, b in enumerate(badges):
        fname = f"badge_{miner_id[:8]}_{i}.svg"
        with open(fname, "w") as f: f.write(b)
    print(f"Generated {len(badges)} badges for {miner_id[:12]}")

if __name__ == "__main__":
    import sys
    generate_miner_badges(sys.argv[1] if len(sys.argv) > 1 else "test-miner", 42, 2.5, 98.5)
