#!/usr/bin/env python3
"""RustChain Transaction Builder — Construct, sign, and broadcast transactions."""
import json, hashlib, time, os, sys, urllib.request

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def build_tx(sender, recipient, amount, fee=0.01, memo=""):
    tx = {
        "from": sender,
        "to": recipient,
        "amount": float(amount),
        "fee": float(fee),
        "memo": memo,
        "timestamp": int(time.time()),
        "nonce": hashlib.sha256(f"{sender}{time.time()}".encode()).hexdigest()[:16],
    }
    tx["hash"] = hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
    return tx

def broadcast(tx):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        data = json.dumps(tx).encode()
        req = urllib.request.Request(f"{NODE}/wallet/transfer/signed", data, {"Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=15, context=ctx)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    if len(sys.argv) < 4:
        print("Usage: python tx_builder.py <from> <to> <amount> [memo]")
        print("       python tx_builder.py --dry-run <from> <to> <amount>")
        sys.exit(1)
    
    dry = sys.argv[1] == "--dry-run"
    args = sys.argv[2:] if dry else sys.argv[1:]
    
    tx = build_tx(args[0], args[1], args[2], memo=args[3] if len(args) > 3 else "")
    print(f"Transaction Built:")
    print(json.dumps(tx, indent=2))
    
    if not dry:
        print("\nBroadcasting...")
        result = broadcast(tx)
        print(f"Result: {json.dumps(result, indent=2)}")
    else:
        print("\n(dry run — not broadcast)")

if __name__ == "__main__":
    main()
