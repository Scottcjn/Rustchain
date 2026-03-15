#!/usr/bin/env python3
"""RustChain Governance Tracker — Monitor proposals and voting."""
import json, urllib.request, os, ssl

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def main():
    proposals = api("/governance/proposals")
    prop_list = proposals if isinstance(proposals, list) else proposals.get("proposals", [])
    
    print("RustChain Governance Tracker")
    print("=" * 60)
    print(f"Active Proposals: {len(prop_list)}")
    print()
    
    for p in prop_list:
        pid = p.get("id", p.get("proposal_id", "?"))
        title = p.get("title", p.get("description", "?"))[:50]
        status = p.get("status", "?")
        yes = p.get("votes_yes", p.get("yes", 0))
        no = p.get("votes_no", p.get("no", 0))
        total = yes + no
        pct = (yes / total * 100) if total > 0 else 0
        
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        print(f"  [{status:^10}] #{pid}")
        print(f"  {title}")
        print(f"  {bar} {pct:.0f}% ({yes} yes / {no} no)")
        print()

if __name__ == "__main__":
    main()
