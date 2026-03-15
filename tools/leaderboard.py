#!/usr/bin/env python3
"""RustChain Miner Leaderboard — Rank miners by performance metrics."""
import json, urllib.request, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def main():
    miners = api("/api/miners")
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    
    print("RustChain Miner Leaderboard")
    print("=" * 70)
    print(f"{'Rank':<5} {'Miner':<20} {'Hardware':<12} {'Mult':<6} {'Blocks':<8} {'Score'}")
    print("-" * 70)
    
    scored = []
    for m in miner_list:
        mid = str(m.get("miner_id", m.get("id", "?")))[:18]
        hw = m.get("hardware", m.get("cpu_arch", "?"))[:10]
        mult = m.get("antiquity_multiplier", m.get("multiplier", 1.0))
        blocks = m.get("blocks_mined", m.get("total_blocks", 0))
        uptime = m.get("uptime", m.get("uptime_pct", 0))
        score = (blocks * mult) + (uptime * 0.1)
        scored.append((score, mid, hw, mult, blocks))
    
    for rank, (score, mid, hw, mult, blocks) in enumerate(sorted(scored, reverse=True), 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"{medal}{rank:<3} {mid:<20} {hw:<12} {mult:<6.1f} {blocks:<8} {score:.1f}")
    
    # Generate markdown
    with open("LEADERBOARD.md", "w") as f:
        f.write("# RustChain Miner Leaderboard\n\n| Rank | Miner | Hardware | Multiplier | Score |\n|------|-------|----------|------------|-------|\n")
        for rank, (score, mid, hw, mult, blocks) in enumerate(sorted(scored, reverse=True), 1):
            f.write(f"| {rank} | {mid} | {hw} | {mult:.1f}x | {score:.1f} |\n")
    print("\nLeaderboard saved to LEADERBOARD.md")

if __name__ == "__main__":
    main()
