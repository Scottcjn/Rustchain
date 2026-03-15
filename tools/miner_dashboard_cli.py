#!/usr/bin/env python3
"""RustChain Miner Dashboard CLI — One-command status overview."""
import json, urllib.request, ssl, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def dashboard():
    h = api("/health"); e = api("/epoch"); m = api("/api/miners"); t = api("/headers/tip"); f = api("/api/fee_pool")
    ml = m if isinstance(m, list) else m.get("miners", [])
    
    print("┌─────────────────────────────────┐")
    print("│   RustChain Miner Dashboard     │")
    print("├─────────────────────────────────┤")
    print(f"│ Status:  {'ONLINE' if h.get('status')=='ok' else 'OFFLINE':>21} │")
    print(f"│ Version: {h.get('version','?'):>21} │")
    print(f"│ Epoch:   {e.get('epoch',e.get('current_epoch','?')):>21} │")
    print(f"│ Slot:    {e.get('slot','?'):>21} │")
    print(f"│ Height:  {t.get('height',t.get('slot','?')):>21} │")
    print(f"│ Miners:  {len(ml):>21} │")
    print(f"│ Pot:     {str(e.get('epoch_pot',e.get('reward_pot','?')))+' RTC':>21} │")
    print(f"│ Supply:  {str(e.get('total_supply','?'))+' RTC':>21} │")
    print(f"│ Fees:    {str(f.get('fee_pool',f.get('balance','?')))+' RTC':>21} │")
    print("└─────────────────────────────────┘")

if __name__ == "__main__":
    dashboard()
