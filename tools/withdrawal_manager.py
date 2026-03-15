#!/usr/bin/env python3
"""RustChain Withdrawal Manager — Request and track RTC withdrawals."""
import json, urllib.request, os, ssl, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(method, path, data=None):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{NODE}{path}", body, {"Content-Type": "application/json"})
    req.method = method
    try: return json.loads(urllib.request.urlopen(req, timeout=10, context=ctx).read())
    except Exception as e: return {"error": str(e)}

def request_withdrawal(miner_id, amount, destination):
    print(f"Requesting withdrawal: {amount} RTC → {destination}")
    r = api("POST", "/withdraw/request", {"miner_id": miner_id, "amount": amount, "destination": destination})
    print(json.dumps(r, indent=2))

def check_status(withdrawal_id):
    r = api("GET", f"/withdraw/status/{withdrawal_id}")
    print(json.dumps(r, indent=2))

def history(miner_id):
    r = api("GET", f"/withdraw/history/{miner_id}")
    entries = r if isinstance(r, list) else r.get("withdrawals", r.get("history", []))
    print(f"Withdrawal History ({len(entries)} entries):")
    for w in entries:
        print(f"  {w.get('withdrawal_id', '?')[:12]}... | {w.get('amount', '?')} RTC | {w.get('status', '?')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python withdrawal_manager.py request <miner_id> <amount> <dest>")
        print("  python withdrawal_manager.py status <withdrawal_id>")
        print("  python withdrawal_manager.py history <miner_id>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "request": request_withdrawal(sys.argv[2], float(sys.argv[3]), sys.argv[4])
    elif cmd == "status": check_status(sys.argv[2])
    elif cmd == "history": history(sys.argv[2])
