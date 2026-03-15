#!/usr/bin/env python3
"""RustChain Alert Rules Engine — Configurable alerting based on thresholds."""
import json, urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
RULES = [
    {"name": "node_down", "check": lambda h: h.get("status") != "ok", "msg": "Node is DOWN"},
    {"name": "low_miners", "check": lambda e: int(e.get("enrolled_miners", 99)) < 2, "msg": "Miner count below 2"},
    {"name": "empty_pot", "check": lambda e: float(e.get("epoch_pot", e.get("reward_pot", 1))) == 0, "msg": "Epoch pot is empty"},
]
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def evaluate():
    h = api("/health"); e = api("/epoch")
    alerts = []
    for rule in RULES:
        try:
            data = h if "node" in rule["name"] else e
            if rule["check"](data):
                alerts.append(rule["msg"])
                print(f"  ALERT: {rule['msg']}")
        except: pass
    if not alerts: print("  All clear - no alerts triggered")
    return alerts
if __name__ == "__main__":
    print("Alert Rules Check\n" + "=" * 40)
    evaluate()
